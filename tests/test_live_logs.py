import logging

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.utils.live_logs import (
    LiveLogBuffer,
    LiveLogHandler,
    live_log_buffer,
    redact_log_message,
)


def test_sensitive_values_are_redacted():
    message = (
        "Authorization: Bearer server-token api_key=deepseek-secret "
        "request?token=query-secret"
    )

    redacted = redact_log_message(message)

    assert "server-token" not in redacted
    assert "deepseek-secret" not in redacted
    assert "query-secret" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_live_log_buffer_is_bounded_and_monotonic():
    buffer = LiveLogBuffer(max_entries=2)

    first = buffer.publish("info", "test", "first")
    second = buffer.publish("warning", "test", "second")
    third = buffer.publish("error", "test", "third")

    assert [entry["message"] for entry in buffer.snapshot()] == ["second", "third"]
    assert first["id"] < second["id"] < third["id"]


def test_logging_handler_captures_standard_records():
    buffer = LiveLogBuffer()
    handler = LiveLogHandler(buffer)
    record = logging.LogRecord(
        "cerberus.test",
        logging.INFO,
        __file__,
        1,
        "processing %s",
        ("started",),
        None,
    )
    handler.emit(record)

    assert buffer.snapshot()[0]["message"] == "processing started"


def test_log_api_requires_auth_and_can_clear(monkeypatch):
    monkeypatch.setattr(settings.server, "api_key", "test-secret")
    live_log_buffer.clear()
    live_log_buffer.publish("INFO", "cerberus.test", "visible entry")
    client = TestClient(app)

    assert client.get("/api/logs").status_code == 401
    response = client.get(
        "/api/logs",
        headers={"Authorization": "Bearer test-secret"},
    )

    assert response.status_code == 200
    assert response.json()["entries"][-1]["message"] == "visible entry"
    cleared = client.delete(
        "/api/logs",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] >= 1
