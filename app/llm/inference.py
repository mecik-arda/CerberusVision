from __future__ import annotations
import ast
from datetime import datetime
import json
import logging
from pathlib import Path
import re
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple
from app.config import settings
from app.models import DocumentStatusCode, ShippingInstruction


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
    "Apply these mapping rules strictly: "
    "--- PARTIES --- "
    "SHIPPER=exporter/seller. CONSIGNEE=receiver/buyer. NOTIFY PARTY must be a company or person name, "
    "never a reference number, export code, or file number. "
    "Carrier headquarters address in the document letterhead (e.g. 'Hapag-Lloyd, Hamburg') is NOT the shipper "
    "address; shipper city/country come from the SHIPPER block only. "
    "--- REFERENCES --- "
    "shipping_instruction_reference: only SI No, SI Reference, Talimat No. "
    "Never put B/L No, container number, port name, or customs declaration (DU-E) here. If absent, set null. "
    "carrier_booking_reference: only Booking No, BKG Ref, Rezervasyon No. Never put B/L No here. "
    "B/L numbers go in document_references with type_code='BL'. "
    "--- LOCATIONS --- "
    "Free-text port and place names belong in location_name; only populate un_location_code when the source "
    "contains a valid five-character UN/LOCODE. POL means port of loading and POD means port of discharge. "
    "Clean OCR artifacts from port names: extract only the recognizable city/port name. "
    "Only populate place_of_issue when the document explicitly labels a place of issue; V.DAIRESI, VERGI DAIRESI, "
    "and TAX OFFICE are tax-office labels and must never become place_of_issue. "
    "--- VESSEL --- "
    "vessel_imo_number is a 7-digit IMO number. A vessel name (e.g. 'JAZAN') is NOT an IMO number. "
    "--- WEIGHTS --- "
    "Values marked KG/KGM are weights; values marked M3/CBM are volumes. Gross "
    "weight belongs in equipment cargo_gross_weight and net cargo weight belongs in cargo_items.weight. Parse "
    "European-formatted quantities such as 26.080,00 as 26080.00 and 28,16 as 28.16. "
    "--- CONTACT --- "
    "A contact name must be a person's name; a telephone label or phone number belongs only in phone_number. "
    "--- TAX --- "
    "For a shipper, labels such as V.NO, VKN, VERGI NO, TAX ID, CPF, CNPJ, and VAT NO map to that party's party_id. "
    "Never copy party_name into party_id when an explicit tax or party identifier label is absent. "
    "On a comma-separated SHIPPER or CONSIGNEE line, party_name "
    "contains only the company or person before the first comma; city and two-letter country components belong in "
    "address. "
    "--- DATES --- "
    "ISSUE DATE, DATE OF ISSUE, DATE, and TARIH map to issue_date. "
    "Populate shipping_instruction_date_time only when the source "
    "explicitly identifies an instruction date-time or includes a time. "
    "--- CARGO --- "
    "description_of_goods contains only the goods "
    "description and must exclude leading package quantities and package-kind words such as PALLETS, CARTONS, BOXES, "
    "or CRATES, and must exclude wood packaging statements, marks prefixes, and freight clauses. "
    "Equipment/container references normally contain four letters "
    "followed by seven digits; preserve them in equipment_reference and link matching cargo equipment references. "
    "Preserve company names, personal names, "
    "addresses, identifiers, codes, port names, and numeric values exactly as found in the source."
)

_language_names = {
    "auto": "mixed Turkish and English",
    "tr": "Turkish",
    "en": "English",
}


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


def reset_llm_pipeline() -> None:
    global _llm_pipeline
    _llm_pipeline = None


@lru_cache(maxsize=1)
def get_json_schema() -> Dict[str, Any]:
    schema = ShippingInstruction.model_json_schema()
    return schema


def build_prompt(
    ocr_text: str,
    document_language: str = "en",
    output_language: str = "en",
) -> str:
    schema = get_json_schema()
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    source_language = _language_names.get(document_language, "English")
    target_language = _language_names.get(output_language, "English")
    prompt = (
        f"System: {_system_prompt}\n\n"
        f"The document language is {source_language}. Interpret OCR labels in that language.\n"
        f"The requested XML content language is {target_language}. Preserve all extracted values in their source "
        "language during this extraction pass. A dedicated translation pass handles descriptive content later. "
        "Never alter proper names, addresses, locations, identifiers, codes, measurement units, or enum values.\n\n"
        f"JSON Schema:\n{schema_str}\n\n"
        f"OCR Text (layout-preserved):\n{ocr_text}\n\n"
        f"Extract the shipping instruction data as JSON:"
    )
    return prompt


def run_guided_inference(
    ocr_text: str,
    document_language: str = "en",
    output_language: str = "en",
) -> str:
    pipe = get_llm_pipeline()
    prompt = build_prompt(ocr_text, document_language, output_language)
    config = _build_generation_config()
    result = pipe.generate(prompt, config)
    return str(result)


def _build_generation_config():
    return _build_generation_config_for_schema(get_json_schema())


def _build_generation_config_for_schema(schema: Dict[str, Any]):
    import openvino_genai

    config = openvino_genai.GenerationConfig()
    config.max_new_tokens = settings.model.max_new_tokens
    config.do_sample = False
    structured_output_mode = _configure_structured_output(
        config,
        openvino_genai,
        json.dumps(schema),
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


def _extract_labeled_value(ocr_text: str, patterns: tuple[str, ...]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, ocr_text)
        if match:
            value = match.group("value").strip().rstrip(".")
            if value:
                return value
    return None


def _normalize_date_value(value: str, require_time: bool = False) -> Optional[str]:
    match = re.fullmatch(
        r"\s*(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*",
        value,
    )
    if not match:
        return None
    first, second, third, hour, minute, second_value = match.groups()
    if len(first) == 4:
        year, month, day = int(first), int(second), int(third)
    elif len(third) == 4:
        day, month, year = int(first), int(second), int(third)
    else:
        return None
    if require_time and hour is None:
        return None
    try:
        parsed = datetime(
            year,
            month,
            day,
            int(hour or 0),
            int(minute or 0),
            int(second_value or 0),
        )
    except ValueError:
        return None
    if hour is None:
        return parsed.strftime("%Y-%m-%d")
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def _extract_labeled_date(
    ocr_text: str,
    patterns: tuple[str, ...],
    require_time: bool = False,
) -> Optional[str]:
    value = _extract_labeled_value(ocr_text, patterns)
    return _normalize_date_value(value, require_time) if value else None


def normalize_extracted_instruction(
    instruction: ShippingInstruction,
    ocr_text: str = "",
) -> ShippingInstruction:
    normalized = instruction.model_copy(deep=True)
    if normalized.document_status_code is None:
        normalized.document_status_code = DocumentStatusCode.DRAFT
    if normalized.shipping_instruction_reference is None:
        normalized.shipping_instruction_reference = _extract_labeled_value(
            ocr_text,
            (
                r"(?im)^\s*shipping\s+instructions?(?:\s+(?:reference|ref|number|no\.?))?\s*[:#-]?\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
                r"(?im)^\s*(?:s\s*/\s*i|si)\s+(?:reference|ref|number|no\.?)\s*[:#-]?\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
                r"(?im)^\s*(?:sevkiyat\s+)?talimat[ıi]\s+(?:referans[ıi]|numaras[ıi]|no\.?)\s*[:#-]?\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
            ),
        )
    if normalized.carrier_booking_reference is None:
        normalized.carrier_booking_reference = _extract_labeled_value(
            ocr_text,
            (
                r"(?im)^\s*(?:carrier\s+)?booking\s*(?:reference|ref|number|no\.?)?\s*[:#-]\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
                r"(?im)^\s*bkg\s*(?:reference|ref|number|no\.?)?\s*[:#-]\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
                r"(?im)^\s*rezervasyon\s*(?:referans[ıi]|numaras[ıi]|no\.?)?\s*[:#-]\s*(?P<value>[A-Z0-9][A-Z0-9._/-]{2,})\s*$",
            ),
        )
    if normalized.shipping_instruction_date_time is None:
        normalized.shipping_instruction_date_time = _extract_labeled_date(
            ocr_text,
            (
                r"(?im)^\s*shipping\s+instructions?\s+(?:date\s*/\s*time|date\s+time|datetime)\s*[:#-]\s*(?P<value>\d{1,4}[./-]\d{1,2}[./-]\d{1,4}[T\s]+\d{1,2}:\d{2}(?::\d{2})?)\s*$",
                r"(?im)^\s*(?:si|talimat)\s+(?:date\s*/\s*time|date\s+time|datetime|tarih\s*/\s*saat)\s*[:#-]\s*(?P<value>\d{1,4}[./-]\d{1,2}[./-]\d{1,4}[T\s]+\d{1,2}:\d{2}(?::\d{2})?)\s*$",
            ),
            require_time=True,
        )
    if normalized.issue_date is None:
        normalized.issue_date = _extract_labeled_date(
            ocr_text,
            (
                r"(?im)^\s*(?:issue\s+date|date\s+of\s+issue|date|tarih|d[üu]zenleme\s+tarihi)\s*[:#-]\s*(?P<value>\d{1,4}[./-]\d{1,2}[./-]\d{1,4})\s*$",
            ),
        )
    normalized_instruction_date_time = (
        _normalize_date_value(
            normalized.shipping_instruction_date_time,
            require_time=True,
        )
        if normalized.shipping_instruction_date_time
        else None
    )
    if normalized_instruction_date_time:
        normalized.shipping_instruction_date_time = normalized_instruction_date_time
    normalized_issue_date = (
        _normalize_date_value(normalized.issue_date)
        if normalized.issue_date
        else None
    )
    if normalized_issue_date:
        normalized.issue_date = normalized_issue_date
    for party in normalized.parties:
        if (
            party.party_id
            and party.party_name
            and party.party_id.strip().casefold() == party.party_name.strip().casefold()
        ):
            party.party_id = None
    tax_office = _extract_labeled_value(
        ocr_text,
        (
            r"(?im)^\s*(?:v\.?\s*dairesi|vergi\s+dairesi|tax\s+office)\s*[:#-]\s*(?P<value>[^\r\n]+?)\s*$",
        ),
    )
    place_name = (
        normalized.place_of_issue.location_name
        if normalized.place_of_issue is not None
        else None
    )
    if tax_office and place_name:
        normalized_tax_office = re.sub(r"\W+", "", tax_office.casefold())
        normalized_place_name = re.sub(r"\W+", "", place_name.casefold())
        if normalized_tax_office == normalized_place_name:
            normalized.place_of_issue = None
    for cargo_item in normalized.cargo_items:
        if cargo_item.description_of_goods:
            cleaned_description = re.sub(
                r"(?i)^\s*(?:\d+\s+)?(?:pallets?|cartons?|boxes?|crates?|bales?|drums?)\s+",
                "",
                cargo_item.description_of_goods,
            ).strip()
            if cleaned_description:
                cargo_item.description_of_goods = cleaned_description
    date_match = re.search(
        r"(?im)^\s*(?:issue\s+date|date|tarih)\s*[:\-]\s*(\d{4}-\d{2}-\d{2})\s*$",
        ocr_text,
    )
    date_time_value = normalized.shipping_instruction_date_time
    if (
        date_match
        and date_time_value
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_time_value.strip())
        and date_time_value.strip() == date_match.group(1)
        and normalized.issue_date in {None, date_match.group(1)}
    ):
        normalized.issue_date = date_match.group(1)
        normalized.shipping_instruction_date_time = None
    return normalized


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


def run_inference_with_fallback(
    ocr_text: str,
    document_language: str = "en",
    output_language: str = "en",
) -> Tuple[ShippingInstruction, str]:
    raw_output = run_guided_inference(ocr_text, document_language, output_language)
    try:
        return normalize_extracted_instruction(
            parse_llm_output(raw_output),
            ocr_text,
        ), raw_output
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        return normalize_extracted_instruction(
            ShippingInstruction.model_validate(data),
            ocr_text,
        ), raw_output


def build_refinement_prompt(
    ocr_text: str,
    initial_result: ShippingInstruction,
    findings: list[dict[str, Any]],
    document_language: str,
) -> str:
    source_language = _language_names.get(document_language, "mixed Turkish and English")
    schema = json.dumps(get_json_schema(), ensure_ascii=False)
    initial_json = initial_result.model_dump_json(exclude_none=False)
    findings_json = json.dumps(findings, ensure_ascii=False)
    return (
        f"System: {_system_prompt}\n\n"
        f"The source is {source_language}. Recheck the initial extraction against the OCR text. "
        "Correct only values directly supported by the OCR text. Resolve the listed deterministic validation "
        "findings when the document contains the required evidence. Keep unsupported fields null and preserve "
        "identifiers, names, addresses, locations, codes, units, and numeric values exactly.\n\n"
        f"Validation findings:\n{findings_json}\n\n"
        f"Initial extraction:\n{initial_json}\n\n"
        f"JSON Schema:\n{schema}\n\n"
        f"OCR Text:\n{ocr_text}\n\n"
        "Return the verified shipping instruction as JSON:"
    )


def run_refinement_with_fallback(
    ocr_text: str,
    initial_result: ShippingInstruction,
    findings: list[dict[str, Any]],
    document_language: str,
) -> Tuple[ShippingInstruction, str]:
    pipe = get_llm_pipeline()
    prompt = build_refinement_prompt(
        ocr_text,
        initial_result,
        findings,
        document_language,
    )
    raw_output = str(pipe.generate(prompt, _build_generation_config()))
    try:
        return normalize_extracted_instruction(
            parse_llm_output(raw_output),
            ocr_text,
        ), raw_output
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        return normalize_extracted_instruction(
            ShippingInstruction.model_validate(data),
            ocr_text,
        ), raw_output
