from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import settings
from app.models import ShippingInstruction


_llm_pipeline = None
_system_prompt = (
    "You are a shipping instruction document parser. "
    "Extract structured data from the OCR text of a shipping instruction / bill of lading document. "
    "Return ONLY valid JSON matching the provided schema. "
    "If a field is not present in the document, set it to null. "
    "Do not fabricate data. Map field names as follows: "
    "shipping_instruction_reference, document_status_code, shipping_instruction_date_time, "
    "carrier_booking_reference, transport_document_type, freight_payment_term_code, issue_date, "
    "place_of_issue (with un_location_code, location_name), export_declaration_number, "
    "service_contract_reference, parties (list of party with party_role_code SHI/CON/NTF, party_id, "
    "party_name, address with street/city/postal_code/country_code, contact_details with name/email/phone_number, "
    "same_as_consignee), transport_plans (leg_sequence_number, transport_mode, port_of_loading, port_of_discharge, "
    "place_of_receipt, place_of_delivery, carrier_voyage_number, vessel_imo_number), "
    "equipment_list (equipment_reference, iso_equipment_code, is_shipper_owned, cargo_gross_weight, "
    "verified_gross_mass, seals, tare_weight), cargo_items (package_quantity, package_kind_code, "
    "description_of_goods, shipping_marks, commodity_code, weight, volume, equipment_references, "
    "dangerous_goods_list), document_references, customs_information, remarks."
)


def get_llm_pipeline():
    global _llm_pipeline
    if _llm_pipeline is not None:
        return _llm_pipeline
    import openvino_genai

    model_path = Path(settings.model.model_path)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. "
            f"Download Qwen-2.5-14B-Instruct-INT4 and set QWEN_MODEL_PATH environment variable."
        )
    _llm_pipeline = openvino_genai.LLMPipeline(str(model_path), device=settings.model.device)
    return _llm_pipeline


def get_json_schema() -> Dict[str, Any]:
    schema = ShippingInstruction.model_json_schema()
    return schema


def build_prompt(ocr_text: str) -> str:
    schema = get_json_schema()
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    prompt = (
        f"System: {_system_prompt}\n\n"
        f"JSON Schema:\n{schema_str}\n\n"
        f"OCR Text (layout-preserved):\n{ocr_text}\n\n"
        f"Extract the shipping instruction data as JSON:"
    )
    return prompt


def run_guided_inference(ocr_text: str) -> str:
    pipe = get_llm_pipeline()
    prompt = build_prompt(ocr_text)
    config = _build_generation_config()
    result = pipe.generate(prompt, config)
    return str(result)


def _build_generation_config():
    import openvino_genai

    config = openvino_genai.GenerationConfig()
    config.max_new_tokens = settings.model.max_new_tokens
    config.temperature = 0.1
    config.top_p = 0.9
    config.do_sample = True
    schema = get_json_schema()
    try:
        config.structured_generation = json.dumps(schema)
    except (AttributeError, TypeError):
        try:
            config.guided_decoding = json.dumps(schema)
        except (AttributeError, TypeError):
            config.json_schema = json.dumps(schema)
    return config


def parse_llm_output(raw_output: str) -> ShippingInstruction:
    cleaned = _extract_json(raw_output)
    data = json.loads(cleaned)
    return ShippingInstruction.model_validate(data)


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in LLM output")
    return text[start:end+1]


def run_inference_with_fallback(ocr_text: str) -> ShippingInstruction:
    raw_output = run_guided_inference(ocr_text)
    try:
        return parse_llm_output(raw_output), raw_output
    except Exception:
        cleaned = _extract_json(raw_output)
        data = json.loads(cleaned)
        return ShippingInstruction.model_validate(data), raw_output