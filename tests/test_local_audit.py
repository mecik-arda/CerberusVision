from app.llm.local_audit import assess_local_result, should_run_automatic_cloud_review
from app.models import WeightUnit
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import check_mandatory_fields, validate_xml_against_xsd
from tests.test_validator import create_complete_si, create_incomplete_si


def assess(instruction, ocr_text="OCR " * 40, threshold=30):
    xml = shipping_instruction_to_xml(instruction)
    is_valid, errors = validate_xml_against_xsd(xml)
    missing = check_mandatory_fields(instruction)
    return assess_local_result(
        instruction,
        ocr_text,
        is_valid,
        errors,
        missing,
        threshold=threshold,
    )


def test_complete_instruction_stays_local():
    result = assess(create_complete_si())
    assert result.risk_score == 0
    assert result.confidence_score == 100
    assert result.requires_cloud_review is False


def test_invalid_container_and_short_ocr_trigger_review():
    instruction = create_complete_si()
    instruction.equipment_list[0].equipment_reference = "BAD-CONTAINER"
    result = assess(instruction, ocr_text="short")
    codes = [finding.code for finding in result.findings]
    assert "invalid_container_check_digit" in codes
    assert "short_ocr_text" in codes
    assert result.requires_cloud_review is True


def test_weight_total_mismatch_is_flagged():
    instruction = create_complete_si()
    instruction.cargo_items[0].weight.weight_value = 1000
    result = assess(instruction)
    assert "weight_total_mismatch" in [finding.code for finding in result.findings]


def test_weight_totals_are_compared_in_same_unit():
    instruction = create_complete_si()
    instruction.cargo_items[0].weight.weight_value = 26.08
    instruction.cargo_items[0].weight.unit = WeightUnit.TON
    result = assess(instruction)
    assert "weight_total_mismatch" not in [finding.code for finding in result.findings]


def test_incomplete_instruction_accumulates_local_risk():
    result = assess(create_incomplete_si())
    assert result.risk_score >= 30
    assert result.requires_cloud_review is True


def test_review_modes_and_api_key_control_cloud_usage():
    high_risk = assess(create_incomplete_si())
    assert should_run_automatic_cloud_review(high_risk, "key", "risk") is True
    assert should_run_automatic_cloud_review(high_risk, "key", "manual") is False
    assert should_run_automatic_cloud_review(high_risk, "key", "off") is False
    assert should_run_automatic_cloud_review(high_risk, None, "always") is False
    assert should_run_automatic_cloud_review(assess(create_complete_si()), "key", "always") is True
