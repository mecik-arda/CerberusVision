from __future__ import annotations
import ast
import json
import logging
from pathlib import Path
import re
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple
from app.config import settings
from app.models import ShippingInstruction


_llm_pipeline = None
logger = logging.getLogger(__name__)
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
    "dangerous_goods_list), document_references, customs_information, remarks. "
    "Apply these mapping rules strictly: free-text port and place names belong in location_name; only populate "
    "un_location_code when the source contains a valid five-character UN/LOCODE. POL means port of loading and "
    "POD means port of discharge. Values marked KG/KGM are weights; values marked M3/CBM are volumes. Gross "
    "weight belongs in equipment cargo_gross_weight and net cargo weight belongs in cargo_items.weight. Parse "
    "European-formatted quantities such as 26.080,00 as 26080.00 and 28,16 as 28.16. Extract city and country "
    "from party addresses when explicitly present. Equipment/container references normally contain four letters "
    "followed by seven digits; preserve them in equipment_reference and link matching cargo equipment references. "
    "Only populate place_of_issue when the document explicitly labels a place of issue; V.DAIRESI, VERGI DAIRESI, "
    "and TAX OFFICE are tax-office labels and must never become place_of_issue. A contact name must be a person's "
    "name; a telephone label or phone number belongs only in phone_number."
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
            "Run scripts/wsl_model_setup.sh or set QWEN_MODEL_PATH to an OpenVINO model."
        )
    pipeline_config = {
        "CACHE_DIR": settings.model.cache_dir,
        "CACHE_MODE": "OPTIMIZE_SIZE",
        "PERFORMANCE_HINT": "LATENCY",
    }
    weights_path = model_path / "openvino_model.bin"
    if weights_path.exists():
        pipeline_config["WEIGHTS_PATH"] = str(weights_path)
    if settings.model.kv_cache_precision:
        pipeline_config["KV_CACHE_PRECISION"] = settings.model.kv_cache_precision
    _llm_pipeline = openvino_genai.LLMPipeline(
        str(model_path), settings.model.device, pipeline_config
    )
    return _llm_pipeline


@lru_cache(maxsize=1)
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
    config.do_sample = False
    structured_output_mode = _configure_structured_output(
        config,
        openvino_genai,
        json.dumps(get_json_schema()),
    )
    logger.debug("OpenVINO structured output mode: %s", structured_output_mode)
    return config


def _configure_structured_output(config, openvino_genai, schema_json: str) -> Optional[str]:
    """Use the newest supported OpenVINO JSON constraint without breaking older builds."""
    structured_config_type = getattr(openvino_genai, "StructuredOutputConfig", None)
    if structured_config_type is not None and hasattr(config, "structured_output_config"):
        structured_config = structured_config_type()
        structured_config.json_schema = schema_json
        config.structured_output_config = structured_config
        return "structured_output_config"

    for attribute in ("structured_generation", "guided_decoding", "json_schema"):
        if hasattr(config, attribute):
            setattr(config, attribute, schema_json)
            return attribute
    return None


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


def _repair_json(text: str) -> str:
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = re.sub(r"([{,])\s*'([^']*)'\s*:", r'\1"\2":', text)
    return text


def _parse_json_with_fallback(text: str) -> Dict[str, Any]:
    repaired = _repair_json(text)
    try:
        data = json.loads(repaired)
    except json.JSONDecodeError:
        data = ast.literal_eval(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output must contain a JSON object")
    return data


def run_inference_with_fallback(ocr_text: str) -> Tuple[ShippingInstruction, str]:
    raw_output = run_guided_inference(ocr_text)
    try:
        return parse_llm_output(raw_output), raw_output
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        return ShippingInstruction.model_validate(data), raw_output
