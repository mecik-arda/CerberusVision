import json
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.llm.inference import _parse_json_with_fallback, get_json_schema
from app.main import _get_openvino_devices, app
from app.ocr.spatial_ocr import render_pdf_pages_to_images
from app.routes import processing
from app.security import SlidingWindowRateLimiter, require_api_key
from app.utils.audit_logger import cleanup_expired_sessions


@pytest.mark.asyncio
async def test_optional_api_key_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setattr(settings.server, "api_key", "secret-key")
    with pytest.raises(HTTPException) as error:
        await require_api_key(None, None)
    assert error.value.status_code == 401
    await require_api_key("Bearer secret-key", None)
    await require_api_key(None, "secret-key")


def test_api_router_enforces_configured_key(monkeypatch):
    monkeypatch.setattr(settings.server, "api_key", "secret-key")
    client = TestClient(app)
    assert client.get("/api/status/20260720_000000_000000").status_code == 401
    response = client.get(
        "/api/status/20260720_000000_000000",
        headers={"Authorization": "Bearer secret-key"},
    )
    assert response.status_code == 404


def test_root_html_disables_browser_cache():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"


@pytest.mark.asyncio
async def test_upload_rate_limiter_uses_sliding_window():
    limiter = SlidingWindowRateLimiter()
    assert await limiter.check("client", 2, 60, now=100) is None
    assert await limiter.check("client", 2, 60, now=110) is None
    assert await limiter.check("client", 2, 60, now=120) == 40
    assert await limiter.check("client", 2, 60, now=161) is None


@pytest.mark.asyncio
async def test_active_pipeline_limit_is_bounded(monkeypatch):
    processing._active_pipeline_sessions.clear()
    monkeypatch.setattr(settings.server, "max_active_pipelines", 1)
    assert await processing._reserve_pipeline_slot("first") is True
    assert await processing._reserve_pipeline_slot("second") is False
    await processing._release_pipeline_slot("first")
    assert await processing._reserve_pipeline_slot("second") is True
    await processing._release_pipeline_slot("second")


def test_completed_orphan_stream_queue_expires(monkeypatch):
    processing._stream_queues.clear()
    processing._stream_queue_created_at.clear()
    processing._stream_queue_completed_at.clear()
    processing._stream_consumers.clear()
    processing._active_pipeline_sessions.clear()
    monkeypatch.setattr(settings.server, "stream_queue_ttl_seconds", 30)
    processing._get_or_create_queue("orphan")
    processing._stream_queue_completed_at["orphan"] = 10
    processing._prune_stream_queues(now=41)
    assert "orphan" not in processing._stream_queues


@pytest.mark.asyncio
async def test_unknown_stream_does_not_allocate_queue():
    processing._stream_queues.clear()
    response = await processing.stream_status("20260720_000000_000000")
    assert response.status_code == 404
    assert processing._stream_queues == {}


def test_pdf_document_closes_when_rendering_fails(tmp_path, monkeypatch):
    state = {"closed": False}

    class Page:
        def get_pixmap(self, matrix):
            raise RuntimeError("render failed")

    class Document:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            state["closed"] = True

        def __iter__(self):
            return iter([Page()])

    fake_fitz = SimpleNamespace(
        open=lambda path: Document(),
        Matrix=lambda x, y: (x, y),
    )
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    with pytest.raises(RuntimeError, match="render failed"):
        render_pdf_pages_to_images(tmp_path / "sample.pdf")
    assert state["closed"] is True


def test_single_quoted_json_values_use_safe_literal_fallback():
    assert _parse_json_with_fallback("{'key': 'value'}") == {"key": "value"}


def test_json_schema_is_cached():
    get_json_schema.cache_clear()
    assert get_json_schema() is get_json_schema()


def test_openvino_device_discovery_is_cached(monkeypatch):
    import openvino

    calls = {"count": 0}

    class Core:
        @property
        def available_devices(self):
            calls["count"] += 1
            return ["CPU", "GPU"]

    monkeypatch.setattr(openvino, "Core", Core)
    _get_openvino_devices.cache_clear()
    assert _get_openvino_devices() == ("CPU", "GPU")
    assert _get_openvino_devices() == ("CPU", "GPU")
    assert calls["count"] == 1
    _get_openvino_devices.cache_clear()


def test_audit_cleanup_removes_only_expired_session_directories(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    old_session = logs_dir / "20200101_000000_000001"
    current_session = logs_dir / "20260101_000000_000002"
    unrelated = logs_dir / "manual-notes"
    old_session.mkdir(parents=True)
    current_session.mkdir()
    unrelated.mkdir()
    now = 100 * 86400
    os.utime(old_session, (0, 0))
    os.utime(current_session, (now, now))
    os.utime(unrelated, (0, 0))
    monkeypatch.setattr(settings, "logs_dir", logs_dir)
    monkeypatch.setattr(settings.server, "log_retention_days", 30)
    assert cleanup_expired_sessions(now=now) == 1
    assert not old_session.exists()
    assert current_session.exists()
    assert unrelated.exists()


def test_ocr_language_is_environment_configurable(monkeypatch):
    monkeypatch.setenv("OCR_LANG", "tr")
    assert Settings().ocr_lang == "tr"


def test_wsl_launcher_requires_auth_for_remote_binding():
    script = (settings.base_dir / "scripts" / "wsl_run.sh").read_text(encoding="utf-8")
    assert 'HOST="${CERBERUS_HOST:-127.0.0.1}"' in script
    assert "CERBERUS_API_KEY is required when listening on a non-loopback host." in script
