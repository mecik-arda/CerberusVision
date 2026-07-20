import io
import json

import pytest
from fastapi import UploadFile

from app.config import settings
from app.models import (
    CloudAuditResponse,
    ProcessingResult,
    ProcessingStatus,
    SaveInstructionRequest,
)
from app.ocr.line_grouper import TextBox
from app.routes import processing
from tests.test_validator import create_complete_si


@pytest.fixture(autouse=True)
def isolate_qwen_post_processing(monkeypatch):
    monkeypatch.setattr(settings.model, "refinement_enabled", False)
    monkeypatch.setattr(
        processing,
        "translate_instruction_content",
        lambda instruction, output_language: (instruction, ""),
    )


def test_copy_upload_enforces_streaming_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(processing, "_MAX_UPLOAD_SIZE", 10)
    destination = tmp_path / "too-large.pdf"
    upload = UploadFile(filename="sample.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 10))

    with pytest.raises(processing.UploadTooLargeError):
        processing._copy_upload_to_path(upload, destination)

    assert not destination.exists()


def test_copy_upload_rejects_non_pdf_content(tmp_path):
    destination = tmp_path / "invalid.pdf"
    upload = UploadFile(filename="sample.pdf", file=io.BytesIO(b"not-a-pdf"))

    with pytest.raises(ValueError, match="not a valid PDF"):
        processing._copy_upload_to_path(upload, destination)

    assert not destination.exists()


@pytest.mark.asyncio
async def test_pipeline_runs_short_cloud_review_and_keeps_local_as_source(tmp_path, monkeypatch):
    local = create_complete_si()
    local.equipment_list[0].equipment_reference = "INVALID"
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    queue = processing.asyncio.Queue()

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "risk_threshold", 30)
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda path, language: (
            "OCR text",
            [[TextBox(text="SI-1", x_min=0, y_min=0, x_max=10, y_max=10)]],
        ),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text, document_language, output_language: (
            local,
            "```json\n{broken-wrapper}\n```",
        ),
    )
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(processing, "run_deepseek_review", lambda instruction, assessment, text: (
        CloudAuditResponse(
            score=82,
            summary="Container reference should be reviewed.",
            suspicious_fields=["equipment_list[0].equipment_reference"],
        ),
        '{"score":82}',
        {"task": "audit_only_no_corrections"},
    ))

    await processing.process_pdf_pipeline(pdf_path, "consensus-test", "source.pdf", queue)

    events = []
    while True:
        item = queue.get_nowait()
        if item is None:
            break
        events.append(json.loads(item))

    assert ProcessingStatus.CLOUD_REVIEW.value in [event["status"] for event in events]
    final_event = events[-1]
    assert final_event["status"] == ProcessingStatus.COMPLETED.value
    assert final_event["data"]["audit_confidence_score"] == 82
    assert final_event["data"]["cloud_review_used"] is True
    assert final_event["data"]["audit_summary"] == "Container reference should be reviewed."
    assert "equipment_list[0].equipment_reference" in final_event["data"]["suspicious_fields"]
    assert json.loads(final_event["data"]["raw_llm_json"])["carrier_booking_reference"] == "CBR-12345"
    assert not pdf_path.exists()
    assert (tmp_path / "logs" / "consensus-test" / "ocr_boxes.json").exists()

    processing._processing_store.pop("consensus-test", None)
    processing._session_models.pop("consensus-test", None)


@pytest.mark.asyncio
async def test_pipeline_skips_cloud_review_when_local_risk_is_low(tmp_path, monkeypatch):
    local = create_complete_si()
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    queue = processing.asyncio.Queue()

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda path, language: ("OCR " * 40, []),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text, document_language, output_language: (local, local.model_dump_json()),
    )
    monkeypatch.setattr(
        processing,
        "run_deepseek_review",
        lambda *args: (_ for _ in ()).throw(AssertionError("DeepSeek should not be called")),
    )

    await processing.process_pdf_pipeline(pdf_path, "low-risk-test", "source.pdf", queue)
    events = []
    while True:
        item = queue.get_nowait()
        if item is None:
            break
        events.append(json.loads(item))

    assert ProcessingStatus.CLOUD_REVIEW.value not in [event["status"] for event in events]
    final_data = events[-1]["data"]
    assert final_data["cloud_review_used"] is False
    assert final_data["local_risk_score"] == 0
    assert final_data["audit_confidence_score"] == 100
    assert "DeepSeek cagrilmadi" in final_data["audit_summary"]
    assert final_data["document_language"] == "en"
    assert final_data["output_language"] == "en"

    processing._processing_store.pop("low-risk-test", None)
    processing._session_models.pop("low-risk-test", None)


def test_processing_language_validation_accepts_only_supported_values():
    assert processing._validate_processing_languages(" TR ", "en") == ("tr", "en")
    with pytest.raises(ValueError, match="Document language"):
        processing._validate_processing_languages("de", "en")
    with pytest.raises(ValueError, match="Output language"):
        processing._validate_processing_languages("tr", "de")


@pytest.mark.asyncio
async def test_runtime_settings_update_never_returns_api_key(monkeypatch):
    monkeypatch.setattr(settings.deepseek, "api_key", None)
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(settings.deepseek, "risk_threshold", 30)
    monkeypatch.setattr(processing, "discover_local_models", lambda *args: [])
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(
            deepseek_api_key="secret-key",
            deepseek_review_mode="manual",
            deepseek_risk_threshold=45,
        )
    )
    data = json.loads(response.body)

    assert response.status_code == 200
    assert data["deepseek"]["configured"] is True
    assert data["deepseek"]["review_mode"] == "manual"
    assert data["deepseek"]["risk_threshold"] == 45
    assert "api_key" not in data["deepseek"]


@pytest.mark.asyncio
async def test_runtime_settings_selects_one_openvino_model(tmp_path, monkeypatch):
    model_path = tmp_path / "Qwen-7B"
    model_path.mkdir()
    (model_path / "openvino_model.xml").write_text("<xml/>", encoding="utf-8")
    resets = []
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)
    monkeypatch.setattr(processing, "reset_llm_pipeline", lambda: resets.append(True))
    monkeypatch.setattr(
        processing,
        "discover_local_models",
        lambda *args: [{
            "name": "Qwen-7B",
            "path": str(model_path.resolve()),
            "source": "Test",
            "format": "OpenVINO",
            "active": False,
            "selectable": True,
        }],
    )

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(local_model_path=str(model_path))
    )

    assert response.status_code == 200
    assert settings.model.model_path == str(model_path.resolve())
    assert resets == [True]


@pytest.mark.asyncio
async def test_draft_and_approval_regenerate_xml(tmp_path, monkeypatch):
    session_id = "save-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")

    edited = instruction.model_copy(deep=True)
    edited.carrier_booking_reference = "EDITED-BOOKING"
    request = SaveInstructionRequest(shipping_instruction=edited)

    draft_response = await processing._save_instruction(session_id, request, approve=False)
    draft_data = json.loads(draft_response.body)
    assert draft_response.status_code == 200
    assert draft_data["status"] == ProcessingStatus.DRAFT.value
    assert "EDITED-BOOKING" in draft_data["xml_content"]
    assert draft_data["structured_data"]["document_status_code"] == "DRF"
    assert (tmp_path / "logs" / session_id / "draft_shipping_instruction.xml").exists()

    approval_response = await processing._save_instruction(session_id, request, approve=True)
    approval_data = json.loads(approval_response.body)
    assert approval_response.status_code == 200
    assert approval_data["status"] == ProcessingStatus.COMPLETED.value
    assert approval_data["structured_data"]["document_status_code"] == "FNL"
    assert (tmp_path / "logs" / session_id / "approved_shipping_instruction.xml").exists()

    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)


@pytest.mark.asyncio
async def test_manual_cloud_review_returns_short_comment_without_changing_data(tmp_path, monkeypatch):
    session_id = "manual-review-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = ProcessingResult(
        status=ProcessingStatus.COMPLETED,
        raw_ocr_text="OCR " * 40,
        structured_data=instruction.model_dump(mode="json"),
    )
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "manual")
    calls = {"count": 0}

    def fake_review(*args):
        calls["count"] += 1
        return (
            CloudAuditResponse(score=94, summary="Local extraction appears consistent.", suspicious_fields=[]),
            '{"score":94}',
            {"task": "audit_only_no_corrections"},
        )

    monkeypatch.setattr(processing, "run_deepseek_review", fake_review)

    response = await processing.run_manual_cloud_review(session_id)
    data = json.loads(response.body)

    assert response.status_code == 200
    assert data["cloud_review_used"] is True
    assert data["audit_confidence_score"] == 94
    assert data["structured_data"]["carrier_booking_reference"] == "CBR-12345"
    assert (tmp_path / "logs" / session_id / "manual_cloud_review_report.json").exists()
    cached_response = await processing.run_manual_cloud_review(session_id)
    assert cached_response.status_code == 200
    assert calls["count"] == 1

    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)


@pytest.mark.asyncio
async def test_save_waits_for_same_session_cloud_review(tmp_path, monkeypatch):
    session_id = "session-lock-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = ProcessingResult(
        status=ProcessingStatus.COMPLETED,
        raw_ocr_text="OCR " * 40,
        structured_data=instruction.model_dump(mode="json"),
    )
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "manual")
    review_started = processing.asyncio.Event()
    release_review = processing.asyncio.Event()

    async def fake_execute(*args):
        review_started.set()
        await release_review.wait()
        return {
            "audit_confidence_score": 90,
            "audit_summary": "Reviewed.",
            "cloud_review_used": True,
            "cloud_review_available": True,
            "local_risk_score": 0,
            "local_warnings": [],
            "suspicious_fields": [],
        }, None

    monkeypatch.setattr(processing, "_execute_cloud_review", fake_execute)
    review_task = processing.asyncio.create_task(
        processing.run_manual_cloud_review(session_id)
    )
    await review_started.wait()
    edited = instruction.model_copy(deep=True)
    edited.carrier_booking_reference = "LOCKED-SAVE"
    save_task = processing.asyncio.create_task(
        processing._save_instruction(
            session_id,
            SaveInstructionRequest(shipping_instruction=edited),
            approve=False,
        )
    )
    await processing.asyncio.sleep(0)
    assert save_task.done() is False
    release_review.set()
    assert (await review_task).status_code == 200
    save_response = await save_task
    assert save_response.status_code == 200
    assert json.loads(save_response.body)["structured_data"]["carrier_booking_reference"] == "LOCKED-SAVE"
    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)
    processing._session_locks.pop(session_id, None)
