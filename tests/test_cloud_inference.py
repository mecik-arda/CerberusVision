import pytest
from pydantic import ValidationError

from app.config import settings
from app.llm.cloud_inference import REVIEW_SYSTEM_PROMPT, build_review_payload
from app.llm.local_audit import assess_local_result
from app.models import CloudAuditResponse
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import check_mandatory_fields, validate_xml_against_xsd
from tests.test_validator import create_complete_si


def test_review_payload_contains_only_flagged_values_and_limited_ocr():
    local = create_complete_si()
    local.equipment_list[0].equipment_reference = "BAD-CONTAINER"
    xml = shipping_instruction_to_xml(local)
    valid, errors = validate_xml_against_xsd(xml)
    ocr_text = "CONTAINER BAD-CONTAINER\nUNRELATED PRIVATE LINE"
    assessment = assess_local_result(
        local,
        ocr_text,
        valid,
        errors,
        check_mandatory_fields(local),
    )
    payload = build_review_payload(local, assessment, ocr_text)

    assert payload["task"] == "audit_only_no_corrections"
    assert "equipment_list[0].equipment_reference" in payload["critical_values"]
    assert "parties" not in payload["critical_values"]
    assert "document_context" not in payload
    assert "UNRELATED PRIVATE LINE" not in payload["limited_ocr_excerpt"]
    assert "JSON Schema" not in str(payload)


def test_review_prompt_forbids_corrections_and_generation():
    prompt = REVIEW_SYSTEM_PROMPT.casefold()
    assert "never correct" in prompt
    assert "never" in prompt and "generate" in prompt
    assert "two short sentences" in prompt


def test_cloud_response_rejects_corrected_values():
    with pytest.raises(ValidationError):
        CloudAuditResponse.model_validate({
            "score": 80,
            "summary": "Review required.",
            "suspicious_fields": [],
            "corrected_values": {"carrier_booking_reference": "NEW"},
        })


def test_ocr_excerpt_respects_configured_limit(monkeypatch):
    monkeypatch.setattr(settings.deepseek, "max_ocr_excerpt_chars", 200)
    local = create_complete_si()
    local.equipment_list[0].equipment_reference = "BAD-CONTAINER"
    xml = shipping_instruction_to_xml(local)
    valid, errors = validate_xml_against_xsd(xml)
    ocr_text = "\n".join(["CONTAINER BAD-CONTAINER DETAILS"] * 30)
    assessment = assess_local_result(
        local, ocr_text, valid, errors, check_mandatory_fields(local)
    )
    payload = build_review_payload(local, assessment, ocr_text)
    assert len(payload["limited_ocr_excerpt"]) <= 200
