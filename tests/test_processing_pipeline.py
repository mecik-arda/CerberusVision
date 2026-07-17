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
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda path: (
            "OCR text",
            [[TextBox(text="SI-1", x_min=0, y_min=0, x_max=10, y_max=10)]],
        ),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text: (local, "```json\n{broken-wrapper}\n```"),
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
    monkeypatch.setattr(processing, "process_pdf_with_spatial_ocr", lambda path: ("OCR " * 40, []))
    monkeypatch.setattr(processing, "run_inference_with_fallback", lambda text: (local, local.model_dump_json()))
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

    processing._processing_store.pop("low-risk-test", None)
    processing._session_models.pop("low-risk-test", None)


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
