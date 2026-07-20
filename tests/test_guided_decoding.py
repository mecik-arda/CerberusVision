import json
import pytest
from app.models import ShippingInstruction
from app.llm.inference import (
    _configure_structured_output,
    _extract_json,
    _parse_json_with_fallback,
    get_json_schema,
    build_prompt,
    normalize_extracted_instruction,
    parse_llm_output,
)


VALID_LLM_OUTPUT = {
    "shipping_instruction_reference": "SI-2026-001",
    "document_status_code": "DRF",
    "shipping_instruction_date_time": "2026-01-15T10:00:00",
    "carrier_booking_reference": "CBR-12345",
    "transport_document_type": "B/L",
    "freight_payment_term_code": "PPD",
    "issue_date": "2026-01-15",
    "place_of_issue": {
        "un_location_code": "TRALI",
        "location_name": "ALIAGA",
    },
    "parties": [
        {
            "party_role_code": "SHI",
            "party_name": "FORENTIS GLOBAL",
            "address": {
                "street": "YESILYURT MAH NO:3",
                "city": "ANTALYA",
                "country_code": "TR",
            },
        },
        {
            "party_role_code": "CON",
            "party_name": "SHAHEEN PLASTIC",
            "address": {
                "street": "OFF # 15",
                "city": "KARACHI",
                "country_code": "PK",
            },
        },
    ],
    "transport_plans": [
        {
            "leg_sequence_number": 1,
            "transport_mode": "SEA",
            "port_of_loading": {"location_name": "TCEGE ALIAGA"},
            "port_of_discharge": {"location_name": "KARACHI"},
        }
    ],
    "equipment_list": [
        {
            "equipment_reference": "MSKU1875698",
            "cargo_gross_weight": {"weight": 26080.00, "unit": "KGM"},
        }
    ],
    "cargo_items": [
        {
            "package_quantity": 32,
            "package_kind_code": "PALLET",
            "description_of_goods": "MDF-LAMINATE FLOOR",
            "commodity_code": "4418.9910",
            "weight": {"weight_value": 26080.00, "unit": "KGM"},
            "volume": {"volume_value": 28.16, "unit": "CBM"},
        }
    ],
}


OUTPUT_WITH_PREFIX = f"Here is the extracted data:\n{json.dumps(VALID_LLM_OUTPUT)}\n\nDone."


OUTPUT_WITH_NESTED_BRACES = '{"parties": [{"party_role_code": "SHI", "address": {"street": "NO:3"}}]}'


class TestExtractJson:
    def test_extract_clean_json(self):
        json_str = json.dumps(VALID_LLM_OUTPUT)
        result = _extract_json(json_str)
        parsed = json.loads(result)
        assert parsed["shipping_instruction_reference"] == "SI-2026-001"

    def test_extract_with_prefix(self):
        result = _extract_json(OUTPUT_WITH_PREFIX)
        parsed = json.loads(result)
        assert parsed["carrier_booking_reference"] == "CBR-12345"

    def test_extract_nested_braces(self):
        result = _extract_json(OUTPUT_WITH_NESTED_BRACES)
        parsed = json.loads(result)
        assert parsed["parties"][0]["address"]["street"] == "NO:3"

    def test_extract_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json("no json here")

    def test_extract_json_with_escaped_quotes(self):
        text = '{"description": "MDF \\"LAMINATE\\" FLOOR"}'
        result = _extract_json(text)
        parsed = json.loads(result)
        assert parsed["description"] == 'MDF "LAMINATE" FLOOR'


class TestParseLlmOutput:
    def test_parse_valid_output(self):
        raw = json.dumps(VALID_LLM_OUTPUT)
        si = parse_llm_output(raw)
        assert isinstance(si, ShippingInstruction)
        assert si.shipping_instruction_reference == "SI-2026-001"
        assert si.parties[0].party_name == "FORENTIS GLOBAL"

    def test_parse_output_with_text_prefix(self):
        si = parse_llm_output(OUTPUT_WITH_PREFIX)
        assert si.carrier_booking_reference == "CBR-12345"
        assert si.cargo_items[0].package_quantity == 32

    def test_parse_minimal_output(self):
        raw = '{"parties": [], "transport_plans": [], "equipment_list": [], "cargo_items": []}'
        si = parse_llm_output(raw)
        assert isinstance(si, ShippingInstruction)
        assert len(si.parties) == 0

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_llm_output("{invalid json}")

    def test_parse_with_null_fields(self):
        raw = '{"shipping_instruction_reference": null, "parties": [], "transport_plans": [], "equipment_list": [], "cargo_items": []}'
        si = parse_llm_output(raw)
        assert si.shipping_instruction_reference is None

    def test_parse_preserves_nested_objects(self):
        si = parse_llm_output(json.dumps(VALID_LLM_OUTPUT))
        assert si.place_of_issue.location_name == "ALIAGA"
        assert si.equipment_list[0].cargo_gross_weight.weight == 26080.00
        assert si.cargo_items[0].volume.volume_value == 28.16

    def test_safe_fallback_parses_single_quoted_keys_and_values(self):
        assert _parse_json_with_fallback("{'carrier_booking_reference': 'CBR-1'}") == {
            "carrier_booking_reference": "CBR-1"
        }


class TestJsonSchema:
    def test_schema_is_valid_dict(self):
        schema = get_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_schema_contains_required_fields(self):
        schema = get_json_schema()
        props = schema["properties"]
        assert "shipping_instruction_reference" in props
        assert "parties" in props
        assert "transport_plans" in props
        assert "equipment_list" in props
        assert "cargo_items" in props

    def test_schema_has_party_definition(self):
        schema = get_json_schema()
        defs = schema.get("$defs", schema.get("definitions", {}))
        party_def = defs["Party"]
        assert "party_role_code" in party_def["properties"]

    def test_schema_is_serializable(self):
        schema = get_json_schema()
        json_str = json.dumps(schema)
        reparsed = json.loads(json_str)
        assert reparsed == schema

    def test_schema_conformance_simulation(self):
        schema = get_json_schema()
        si = ShippingInstruction.model_validate(VALID_LLM_OUTPUT)
        dumped = si.model_dump(mode="json")
        json.dumps(dumped)
        assert dumped["shipping_instruction_reference"] == "SI-2026-001"

    def test_openvino_structured_output_config_is_used_when_available(self):
        class StructuredOutputConfig:
            json_schema = ""

        class Module:
            pass

        class Config:
            structured_output_config = None

        Module.StructuredOutputConfig = StructuredOutputConfig
        config = Config()
        selected = _configure_structured_output(config, Module, '{"type":"object"}')

        assert selected == "structured_output_config"
        assert config.structured_output_config.json_schema == '{"type":"object"}'

    def test_unsupported_openvino_version_falls_back_without_error(self):
        selected = _configure_structured_output(object(), object(), '{"type":"object"}')
        assert selected is None


def test_prompt_applies_document_and_output_languages_without_translating_identifiers():
    prompt = build_prompt("V.NO: 3881946820", "tr", "en")
    assert "document language is Turkish" in prompt
    assert "requested XML content language is English" in prompt
    assert "Never alter proper names" in prompt
    assert "dedicated translation pass" in prompt
    assert "V.NO" in prompt
    assert "party_id" in prompt


def test_deterministic_normalization_moves_plain_date_and_removes_name_as_id():
    instruction = ShippingInstruction.model_validate(VALID_LLM_OUTPUT)
    instruction.issue_date = None
    instruction.shipping_instruction_date_time = "2026-01-15"
    instruction.parties[0].party_id = instruction.parties[0].party_name

    normalized = normalize_extracted_instruction(
        instruction,
        "DATE: 2026-01-15",
    )

    assert normalized.issue_date == "2026-01-15"
    assert normalized.shipping_instruction_date_time is None
    assert normalized.parties[0].party_id is None
    assert instruction.parties[0].party_id == instruction.parties[0].party_name


def test_deterministic_normalization_extracts_labeled_control_fields():
    instruction = ShippingInstruction.model_validate(
        {
            "place_of_issue": {"location_name": "ANTALYA KURUMLAR"},
            "parties": [],
            "transport_plans": [],
            "equipment_list": [],
            "cargo_items": [],
        }
    )
    ocr_text = (
        "SI NO: SI/TR-900\n"
        "BKG REF: BK-12345\n"
        "SHIPPING INSTRUCTION DATE/TIME: 20.07.2026 14:35\n"
        "ISSUE DATE: 19/07/2026\n"
        "V.DAIRESI: ANTALYA KURUMLAR"
    )

    normalized = normalize_extracted_instruction(instruction, ocr_text)

    assert normalized.shipping_instruction_reference == "SI/TR-900"
    assert normalized.document_status_code == "DRF"
    assert normalized.carrier_booking_reference == "BK-12345"
    assert normalized.shipping_instruction_date_time == "2026-07-20T14:35:00"
    assert normalized.issue_date == "2026-07-19"
    assert normalized.place_of_issue is None


def test_deterministic_normalization_does_not_invent_absent_references_or_dates():
    instruction = ShippingInstruction()

    normalized = normalize_extracted_instruction(
        instruction,
        "POL: ALIAGA\nPOD: KARACHI\nCONTAINER: MSKU1875698",
    )

    assert normalized.document_status_code == "DRF"
    assert normalized.shipping_instruction_reference is None
    assert normalized.carrier_booking_reference is None
    assert normalized.shipping_instruction_date_time is None
    assert normalized.issue_date is None


def test_deterministic_normalization_removes_leading_package_words():
    instruction = ShippingInstruction.model_validate(
        {
            "cargo_items": [
                {
                    "package_quantity": 32,
                    "package_kind_code": "PALLET",
                    "description_of_goods": "32 PALLETS MDF LAMINATE FLOOR",
                }
            ]
        }
    )

    normalized = normalize_extracted_instruction(instruction)

    assert normalized.cargo_items[0].description_of_goods == "MDF LAMINATE FLOOR"
