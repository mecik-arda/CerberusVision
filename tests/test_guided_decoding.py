import json
import pytest
from app.models import ShippingInstruction
from app.llm.inference import _extract_json, parse_llm_output, get_json_schema


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