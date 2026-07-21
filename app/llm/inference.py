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
    "Clean OCR artifacts from port names. If a port name has a random prefix before a known city "
    "(e.g. 'TCEGE ALIAGA' -> 'ALIAGA', 'COP RIO DE JANEIRO' -> 'RIO DE JANEIRO'), "
    "keep only the city/port name. "
    "Only populate place_of_issue when the document explicitly labels a place of issue; V.DAIRESI, VERGI DAIRESI, "
    "and TAX OFFICE are tax-office labels and must never become place_of_issue. "
    "--- VESSEL --- "
    "vessel_imo_number is a 7-digit IMO number. A vessel name (e.g. 'JAZAN') is NOT an IMO number. "
    "--- WEIGHTS --- "
    "Values marked KG/KGM are weights; values marked M3/CBM are volumes. Gross "
    "weight belongs in equipment cargo_gross_weight and NET/net weight belongs in cargo_items.weight. "
    "When OCR shows BRUT and NET together (e.g. 'BRUT:26.080,00 KG- NET: 24.776,00 KG'), "
    "BRUT=gross=cargo_gross_weight, NET=net=cargo_items.weight. Never put gross in cargo_items. "
    "Parse European-formatted quantities: 26.080,00 -> 26080.00, 28,16 -> 28.16, 24.776,00 -> 24776.00. "
    "--- CONTACT --- "
    "A contact name must be a person's name, never a telephone number or label. "
    "If the OCR shows 'TELEPHONE:05325400708', put '05325400708' in phone_number and leave name null. "
    "Do not put 'TELEPHONE:' or the phone number in the name field. "
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

_STAGE1_SYSTEM_PROMPT = (
    "Sen bir konsimento belgesi ayristiricisin. "
    "OCR metninden SADECE taraflar ve belge referans bilgilerini cikar. "
    "Cikarilacak alanlar: shipping_instruction_reference, document_status_code, "
    "carrier_booking_reference, issue_date, place_of_issue, export_declaration_number, "
    "service_contract_reference, parties (SHI/CON/NTF rolleriyle; party_id, party_name, "
    "address, contact_details, same_as_consignee), document_references, customs_information, remarks. "
    "Diger tum alanlari bos (null) birak. "
    "Return ONLY valid JSON matching the provided schema. "
    "If a field is not present in the document, set it to null. Do not fabricate data. "
    "--- TARAF KURALLARI --- "
    "SHIPPER=ihracatçi/satici. CONSIGNEE=alici/ithalatçi. NOTIFY PARTY sirket veya kisi adi olmali, "
    "referans numarasi veya dosya numarasi olmamali. "
    "Antetli kagit uzerindeki tasiyici adresi (ornegin 'Hapag-Lloyd, Hamburg') SHIPPER adresi degildir. "
    "--- REFERANS KURALLARI --- "
    "shipping_instruction_reference: sadece SI No, SI Reference, Talimat No. "
    "B/L No, konteyner numarasi, liman adi girilmemeli. Yoksa null. "
    "carrier_booking_reference: sadece Booking No, BKG Ref, Rezervasyon No. B/L No buraya girilmemeli. "
    "B/L numaralari document_references icine type_code='BL' ile eklenmeli. "
    "--- TARIH KURALLARI --- "
    "ISSUE DATE, DATE OF ISSUE, DATE, TARIH -> issue_date. "
    "shipping_instruction_date_time sadece saat bilgisi de varsa doldurulmali. "
    "--- VERGI KURALLARI --- "
    "V.NO, VKN, VERGI NO, TAX ID, CPF, CNPJ, VAT NO -> party_id. "
    "party_id ile party_name ayni olmamali. "
    "--- KONUM KURALLARI --- "
    "place_of_issue sadece belge duzenleme yeri oldugunda doldurulmali. "
    "V.DAIRESI, VERGI DAIRESI, TAX OFFICE -> place_of_issue OLAMAZ. "
    "--- ILETISIM KURALLARI --- "
    "Contact name bir kisi adi olmali, telefon numarasi olmamali. "
    "'TELEPHONE:05325400708' -> phone_number='05325400708', name=null. "
    "Preserve company names, personal names, addresses, identifiers, codes, "
    "port names, and numeric values exactly as found in the source."
)

_STAGE2_SYSTEM_PROMPT = (
    "Sen bir konsimento belgesi ayristiricisin. "
    "OCR metninden SADECE lojistik ve tasima bilgilerini cikar. "
    "Cikarilacak alanlar: transport_document_type, freight_payment_term_code, "
    "transport_plans (leg_sequence_number, transport_mode, port_of_loading, port_of_discharge, "
    "place_of_receipt, place_of_delivery, carrier_voyage_number, vessel_imo_number). "
    "Diger tum alanlari bos (null) birak. "
    "Return ONLY valid JSON matching the provided schema. "
    "If a field is not present in the document, set it to null. Do not fabricate data. "
    "--- LIMAN KURALLARI --- "
    "Serbest metin liman adlari location_name alanina; UN/LOCODE sadece kaynakta "
    "5 karakterli gecerli bir kod varsa un_location_code alanina. "
    "POL = port of loading (yukleme limani), POD = port of discharge (bosaltma limani). "
    "OCR bozukluklarini liman adlarindan temizle: "
    "'TCEGE ALIAGA' -> 'ALIAGA', 'COP RIO DE JANEIRO' -> 'RIO DE JANEIRO'. "
    "--- GEMI KURALLARI --- "
    "vessel_imo_number 7 haneli IMO numarasidir. Gemi adi (ornegin 'JAZAN') IMO numarasi DEGILDIR. "
    "--- TASIMA TURU KURALLARI --- "
    "transport_document_type: B/L veya SWB. freight_payment_term_code: PPD (prepaid) veya COL (collect). "
    "FREIGHT PREPAID -> PPD, FREIGHT COLLECT -> COL. "
    "Preserve identifiers, codes, port names, and numeric values exactly as found in the source."
)

_STAGE3_SYSTEM_PROMPT = (
    "Sen bir konsimento belgesi ayristiricisin. "
    "OCR metninden SADECE konteyner ve yuk bilgilerini cikar. "
    "Cikarilacak alanlar: equipment_list (equipment_reference, iso_equipment_code, "
    "is_shipper_owned, cargo_gross_weight, verified_gross_mass, seals, tare_weight), "
    "cargo_items (package_quantity, package_kind_code, description_of_goods, "
    "shipping_marks, commodity_code, weight, volume, equipment_references, "
    "dangerous_goods_list). "
    "Diger tum alanlari bos (null) birak. "
    "Return ONLY valid JSON matching the provided schema. "
    "If a field is not present in the document, set it to null. Do not fabricate data. "
    "--- AGIRLIK KURALLARI --- "
    "KG/KGM -> agirlik, M3/CBM -> hacim. "
    "BRUT/ GROSS -> cargo_gross_weight (ekipman seviyesinde), NET -> cargo_items.weight. "
    "Avrupa formatli sayilari ayristir: 26.080,00 -> 26080.00, 28,16 -> 28.16, 24.776,00 -> 24776.00. "
    "--- KONTEYNER KURALLARI --- "
    "Konteyner referanslari genellikle 4 harf + 7 rakam formatindadir. "
    "ISO 6346 kontrol basamagini dogrula. equipment_reference alaninda sakla. "
    "--- YUK KURALLARI --- "
    "description_of_goods sadece mal aciklamasini icermeli; baslangictaki paket sayisi "
    "ve paket turu (PALLETS, CARTONS, BOXES, CRATES) cikarilmali. "
    "Ahsap ambalaj beyanlari, marks on ekleri ve navlun klozlari description_of_goods disinda tutulmali. "
    "shipping_marks icinde markalar ve referanslar yer almali. "
    "Eslesen kargo ekipman referanslari equipment_references altinda iliskilendirilmeli. "
    "Preserve identifiers, codes, measurement units, and numeric values exactly as found in the source."
)

_STAGE_FIELD_OWNERSHIP = {
    1: {
        "shipping_instruction_reference", "carrier_booking_reference",
        "shipping_instruction_date_time", "issue_date", "place_of_issue",
        "export_declaration_number", "service_contract_reference",
        "parties", "document_references", "customs_information", "remarks",
    },
    2: {
        "transport_document_type", "freight_payment_term_code",
        "transport_plans",
    },
    3: {
        "equipment_list", "cargo_items",
    },
}

_STAGE_PROMPTS = {
    1: _STAGE1_SYSTEM_PROMPT,
    2: _STAGE2_SYSTEM_PROMPT,
    3: _STAGE3_SYSTEM_PROMPT,
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


@lru_cache(maxsize=4)
def get_stage_schema(stage: int) -> Dict[str, Any]:
    full_schema = ShippingInstruction.model_json_schema()
    owned_fields = _STAGE_FIELD_OWNERSHIP.get(stage, set())
    if not owned_fields:
        return full_schema
    schema_copy = {
        k: v for k, v in full_schema.items() if k != "properties"
    }
    schema_copy["properties"] = {}
    for field_name in owned_fields:
        if field_name in full_schema.get("properties", {}):
            schema_copy["properties"][field_name] = full_schema["properties"][field_name]
    assert schema_copy.get("properties"), (
        f"Asama {stage} icin alan bulunamadi"
    )
    return schema_copy


def build_stage_prompt(
    ocr_text: str,
    stage: int,
    document_language: str = "en",
    output_language: str = "en",
) -> str:
    system_prompt = _STAGE_PROMPTS.get(stage, _system_prompt)
    schema = get_stage_schema(stage)
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    source_language = _language_names.get(document_language, "English")
    target_language = _language_names.get(output_language, "English")
    prompt = (
        f"System: {system_prompt}\n\n"
        f"The document language is {source_language}. Interpret OCR labels in that language.\n"
        f"The requested XML content language is {target_language}. Preserve all extracted values in their source "
        "language during this extraction pass. A dedicated translation pass handles descriptive content later. "
        "Never alter proper names, addresses, locations, identifiers, codes, measurement units, or enum values.\n\n"
        f"JSON Schema:\n{schema_str}\n\n"
        f"OCR Text (layout-preserved):\n{ocr_text}\n\n"
        f"Extract the shipping instruction data as JSON:"
    )
    assert ocr_text.strip(), "OCR metni bos"
    return prompt


def run_stage_inference(
    ocr_text: str,
    stage: int,
    document_language: str = "en",
    output_language: str = "en",
) -> Tuple[ShippingInstruction, str]:
    pipe = get_llm_pipeline()
    prompt = build_stage_prompt(ocr_text, stage, document_language, output_language)
    schema = get_stage_schema(stage)
    config = _build_generation_config_for_schema(schema)
    result = pipe.generate(prompt, config)
    raw_output = str(result)
    assert raw_output.strip(), f"Asama {stage} LLM ciktisi bos"
    try:
        cleaned = _extract_json(raw_output)
        data = json.loads(cleaned)
        instruction = ShippingInstruction.model_validate(data)
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        instruction = ShippingInstruction.model_validate(data)
    return instruction, raw_output


def merge_stage_results(
    stage1: ShippingInstruction,
    stage2: ShippingInstruction,
    stage3: ShippingInstruction,
) -> ShippingInstruction:
    merged = ShippingInstruction()
    merged.document_status_code = (
        stage1.document_status_code
        or stage2.document_status_code
        or stage3.document_status_code
        or DocumentStatusCode.DRAFT
    )
    merged.shipping_instruction_date_time = (
        stage1.shipping_instruction_date_time
        or stage2.shipping_instruction_date_time
        or stage3.shipping_instruction_date_time
    )
    for field_name in _STAGE_FIELD_OWNERSHIP[1]:
        value = getattr(stage1, field_name)
        if value is not None and value != []:
            setattr(merged, field_name, value)
    for field_name in _STAGE_FIELD_OWNERSHIP[2]:
        value = getattr(stage2, field_name)
        if value is not None and value != []:
            setattr(merged, field_name, value)
    for field_name in _STAGE_FIELD_OWNERSHIP[3]:
        value = getattr(stage3, field_name)
        if value is not None and value != []:
            setattr(merged, field_name, value)
    merged = ShippingInstruction.model_validate(merged.model_dump())
    assert merged.parties == stage1.parties, "Birlesik parties, stage1'den farkli"
    assert merged.transport_plans == stage2.transport_plans, (
        "Birlesik transport_plans, stage2'den farkli"
    )
    assert merged.equipment_list == stage3.equipment_list, (
        "Birlesik equipment_list, stage3'ten farkli"
    )
    assert merged.cargo_items == stage3.cargo_items, (
        "Birlesik cargo_items, stage3'ten farkli"
    )
    return merged


def run_threestage_extraction(
    upper_text: str,
    middle_text: str,
    lower_text: str,
    document_language: str = "en",
    output_language: str = "en",
) -> Tuple[ShippingInstruction, Dict[int, str]]:
    assert upper_text.strip() or middle_text.strip() or lower_text.strip(), (
        "Tum bolge metinleri bos"
    )
    raw_outputs: Dict[int, str] = {}
    stage1_instruction, stage1_raw = run_stage_inference(
        upper_text if upper_text.strip() else middle_text,
        1, document_language, output_language,
    )
    raw_outputs[1] = stage1_raw
    stage1_normalized = normalize_extracted_instruction(stage1_instruction, upper_text)
    stage2_instruction, stage2_raw = run_stage_inference(
        middle_text if middle_text.strip() else lower_text,
        2, document_language, output_language,
    )
    raw_outputs[2] = stage2_raw
    stage2_normalized = normalize_extracted_instruction(stage2_instruction, middle_text)
    combined_middle_lower = (
        (middle_text + "\n" + lower_text) if (middle_text.strip() and lower_text.strip())
        else (middle_text or lower_text)
    )
    stage3_instruction, stage3_raw = run_stage_inference(
        combined_middle_lower if combined_middle_lower.strip() else lower_text,
        3, document_language, output_language,
    )
    raw_outputs[3] = stage3_raw
    stage3_normalized = normalize_extracted_instruction(stage3_instruction, combined_middle_lower)
    merged = merge_stage_results(
        stage1_normalized, stage2_normalized, stage3_normalized
    )
    for stage_num, raw in raw_outputs.items():
        assert raw.strip(), f"Asama {stage_num} ham cikti bos"
    return merged, raw_outputs


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


_PORT_PREFIX_PATTERN = re.compile(
    r"^([A-Z]{2,6})\s+(?=[A-Z]{2,})"
)
_KNOWN_PORTS = frozenset({
    "ALIAGA", "ISTANBUL", "IZMIR", "MERSIN", "ANTALYA", "SAMSUN", "TRABZON",
    "KARACHI", "HAMBURG", "ROTTERDAM", "ANTWERP", "SINGAPORE", "SHANGHAI",
    "HONG KONG", "BUSAN", "TOKYO", "NEW YORK", "LOS ANGELES", "MIAMI",
    "RIO DE JANEIRO", "SANTOS", "DUBAI", "JEBEL ALI", "HO CHI MINH",
    "HAI PHONG", "COLOMBO", "CHENNAI", "MUMBAI", "LONDON", "FELIXSTOWE",
    "GENOA", "BARCELONA", "VALENCIA", "PIRAEUS", "GDANSK", "GDYNIA",
})


def _parse_european_number(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _iso6346_check_digit_light(reference: str) -> bool:
    normalized = re.sub(r"\s+", "", reference or "").upper()
    if not re.fullmatch(r"[A-Z]{4}\d{7}", normalized):
        return False
    letter_values: dict[str, int] = {}
    value = 10
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        while value % 11 == 0:
            value += 1
        letter_values[letter] = value
        value += 1
    total = 0
    for position, character in enumerate(normalized[:10]):
        numeric = int(character) if character.isdigit() else letter_values[character]
        total += numeric * (2 ** position)
    calculated = (total % 11) % 10
    return calculated == int(normalized[-1])


def _extract_containers_from_ocr(ocr_text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z]{4}\d{7}\b", ocr_text)
    valid: list[str] = []
    for candidate in candidates:
        if _iso6346_check_digit_light(candidate):
            valid.append(candidate)
    seen: set[str] = set()
    deduped: list[str] = []
    for container in valid:
        if container not in seen:
            seen.add(container)
            deduped.append(container)
    return deduped


_ROLE_CODE_MAP = {
    "SHIPPER": "CZ", "CZ": "CZ", "SHI": "CZ", "EXPORTER": "CZ",
    "CONSIGNEE": "CN", "CN": "CN", "CON": "CN", "CONSIGNED TO ORDER": "CN",
    "NOTIFY": "N1", "N1": "N1", "NTF": "N1", "NOTIFY PARTY": "N1",
    "FORWARDER": "FW", "FW": "FW", "FREIGHT FORWARDER": "FW",
    "GONDERICI": "CZ", "ALICI": "CN", "BILDIRIM TARAFI": "N1",
    "ACENTE": "FW",
}

_CONTAINER_TYPE_MAP = {
    # 40' High Cube
    "40HC": "45G1", "40'HC": "45G1", "40 HC": "45G1", "40' HC": "45G1",
    "40HIGH CUBE": "45G1", "40 HIGH CUBE": "45G1", "40' HIGH CUBE": "45G1",
    "40HQ": "45G1", "40' HQ": "45G1", "40 HQ": "45G1",
    # 20' General Purpose
    "20GP": "22G1", "20'GP": "22G1", "20 GP": "22G1", "20' GP": "22G1",
    "20GENERAL PURPOSE": "22G1", "20 GENERAL PURPOSE": "22G1",
    "20STANDARD": "22G1", "20 STANDARD": "22G1", "20' STANDARD": "22G1",
    "20DC": "22G1", "20' DC": "22G1", "20 DRY": "22G1",
    "20DV": "22G1", "20' DV": "22G1",
    # 40' General Purpose
    "40GP": "42G1", "40'GP": "42G1", "40 GP": "42G1", "40' GP": "42G1",
    "40GENERAL PURPOSE": "42G1", "40 GENERAL PURPOSE": "42G1",
    "40STANDARD": "42G1", "40 STANDARD": "42G1", "40' STANDARD": "42G1",
    "40DC": "42G1", "40' DC": "42G1", "40 DRY": "42G1",
    "40DV": "42G1", "40' DV": "42G1",
    # 45' High Cube
    "45HC": "L5G1", "45'HC": "L5G1", "45 HC": "L5G1", "45' HC": "L5G1",
    "45HIGH CUBE": "L5G1", "45 HIGH CUBE": "L5G1",
    # 20' Reefer
    "20RF": "22R1", "20'RF": "22R1", "20 RF": "22R1", "20' RF": "22R1",
    "20REEFER": "22R1", "20 REEFER": "22R1", "20 REFRIGERATED": "22R1",
    "20' REEFER": "22R1",
    # 40' Reefer
    "40RF": "42R1", "40'RF": "42R1", "40 RF": "42R1", "40' RF": "42R1",
    "40REEFER": "42R1", "40 REEFER": "42R1", "40 REFRIGERATED": "42R1",
    "40' REEFER": "42R1", "40HI CUBE REEFER": "45R1",
    # 20' Open Top
    "20OT": "22U1", "20'OT": "22U1", "20 OT": "22U1", "20' OT": "22U1",
    "20OPEN TOP": "22U1", "20 OPEN TOP": "22U1",
    # 40' Open Top
    "40OT": "42U1", "40'OT": "42U1", "40 OT": "42U1", "40' OT": "42U1",
    "40OPEN TOP": "42U1", "40 OPEN TOP": "42U1",
    # 20' Flat Rack
    "20FR": "22P1", "20'FR": "22P1", "20 FR": "22P1", "20' FR": "22P1",
    "20FLAT RACK": "22P1", "20 FLAT RACK": "22P1", "20FLAT": "22P1",
    # 40' Flat Rack
    "40FR": "42P1", "40'FR": "42P1", "40 FR": "42P1", "40' FR": "42P1",
    "40FLAT RACK": "42P1", "40 FLAT RACK": "42P1", "40FLAT": "42P1",
    # 20' Tank
    "20TK": "22T1", "20' TK": "22T1", "20 TANK": "22T1",
    # 40' Tank
    "40TK": "42T1", "40' TK": "42T1", "40 TANK": "42T1",
}

_CONTAINER_TYPE_PATTERN = re.compile(
    r"(?i)(?:"
    r"40\s*['’]?\s*(?:HC|HIGH\s*CUBE|HQ)|"
    r"20\s*['’]?\s*(?:GP|GENERAL\s*PURPOSE|STANDARD|DC|DV|DRY|RF|REEFER|REFRIGERATED|OT|OPEN\s*TOP|FR|FLAT\s*RACK|FLAT|TK|TANK)|"
    r"40\s*['’]?\s*(?:GP|GENERAL\s*PURPOSE|STANDARD|DC|DV|DRY|RF|REEFER|REFRIGERATED|OT|OPEN\s*TOP|FR|FLAT\s*RACK|FLAT|TK|TANK)|"
    r"45\s*['’]?\s*(?:HC|HIGH\s*CUBE|HQ)"
    r")",
    re.IGNORECASE,
)

_COUNTRY_NAME_TO_CODE = {
    # Europe
    "TURKEY": "TR", "TÜRKIYE": "TR", "TURKIYE": "TR", "TÜRKİYE": "TR",
    "GERMANY": "DE", "ALMANYA": "DE", "DEUTSCHLAND": "DE",
    "UNITED KINGDOM": "GB", "UK": "GB", "ENGLAND": "GB", "GREAT BRITAIN": "GB",
    "ITALY": "IT", "İTALYA": "IT", "ITALIA": "IT",
    "SPAIN": "ES", "İSPANYA": "ES", "ESPANA": "ES", "ESPAÑA": "ES",
    "FRANCE": "FR", "FRANSA": "FR",
    "NETHERLANDS": "NL", "HOLLAND": "NL", "HOLLANDA": "NL",
    "BELGIUM": "BE", "BELÇİKA": "BE",
    "RUSSIA": "RU", "RUSYA": "RU", "RUSSIAN FEDERATION": "RU",
    "UKRAINE": "UA", "UKRAYNA": "UA",
    "POLAND": "PL", "POLONYA": "PL",
    "ROMANIA": "RO", "ROMANYA": "RO",
    "GREECE": "GR", "YUNANISTAN": "GR",
    "BULGARIA": "BG", "BULGARISTAN": "BG",
    "PORTUGAL": "PT", "PORTEKIZ": "PT",
    "SWEDEN": "SE", "İSVEÇ": "SE",
    "NORWAY": "NO", "NORVEÇ": "NO",
    "DENMARK": "DK", "DANIMARKA": "DK",
    "FINLAND": "FI", "FİNLANDİYA": "FI",
    "AUSTRIA": "AT", "AVUSTURYA": "AT",
    "SWITZERLAND": "CH", "İSVİÇRE": "CH",
    "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "ÇEK CUMHURİYETİ": "CZ",
    "HUNGARY": "HU", "MACARISTAN": "HU",
    "SLOVAKIA": "SK", "SLOVAKYA": "SK",
    "SLOVENIA": "SI", "SLOVENYA": "SI",
    "CROATIA": "HR", "HIRVATISTAN": "HR",
    "SERBIA": "RS", "SIRBISTAN": "RS",
    "IRELAND": "IE", "İRLANDA": "IE",
    "LITHUANIA": "LT", "LITVANYA": "LT",
    "LATVIA": "LV", "LETONYA": "LV",
    "ESTONIA": "EE", "ESTONYA": "EE",
    "MALTA": "MT",
    "CYPRUS": "CY", "KIBRIS": "CY",
    "LUXEMBOURG": "LU", "LÜKSEMBURG": "LU",
    "ICELAND": "IS", "İZLANDA": "IS",
    # Asia
    "CHINA": "CN", "ÇİN": "CN", "PRC": "CN",
    "INDIA": "IN", "HİNDİSTAN": "IN",
    "PAKISTAN": "PK", "PAKİSTAN": "PK",
    "JAPAN": "JP", "JAPONYA": "JP",
    "SOUTH KOREA": "KR", "KOREA": "KR", "GÜNEY KORE": "KR",
    "TAIWAN": "TW", "TAYVAN": "TW",
    "VIETNAM": "VN", "VIETNAM": "VN",
    "THAILAND": "TH", "TAYLAND": "TH",
    "MALAYSIA": "MY", "MALEZYA": "MY",
    "INDONESIA": "ID", "ENDONEZYA": "ID",
    "PHILIPPINES": "PH", "FILIPINLER": "PH",
    "SINGAPORE": "SG", "SİNGAPUR": "SG",
    "BANGLADESH": "BD", "BANGLADEŞ": "BD",
    "SRI LANKA": "LK", "SRİ LANKA": "LK",
    # Middle East
    "UAE": "AE", "UNITED ARAB EMIRATES": "AE", "BİRLEŞİK ARAP EMİRLİKLERİ": "AE",
    "SAUDI ARABIA": "SA", "SUUDI ARABISTAN": "SA", "SUUDİ ARABİSTAN": "SA",
    "QATAR": "QA", "KATAR": "QA",
    "KUWAIT": "KW", "KÜVEYT": "KW",
    "BAHRAIN": "BH", "BAHREYN": "BH",
    "OMAN": "OM", "UMMAN": "OM",
    "JORDAN": "JO", "ÜRDÜN": "JO",
    "LEBANON": "LB", "LÜBNAN": "LB",
    "ISRAEL": "IL", "İSRAIL": "IL",
    "IRAN": "IR", "İRAN": "IR",
    "IRAQ": "IQ", "IRAK": "IQ",
    "YEMEN": "YE", "YEMEN": "YE",
    "SYRIA": "SY", "SURIYE": "SY", "SURİYE": "SY",
    # Africa
    "EGYPT": "EG", "MISIR": "EG",
    "SOUTH AFRICA": "ZA", "GÜNEY AFRİKA": "ZA",
    "MOROCCO": "MA", "FAS": "MA",
    "ALGERIA": "DZ", "CEZAYİR": "DZ",
    "TUNISIA": "TN", "TUNUS": "TN",
    "LIBYA": "LY", "LIBYA": "LY",
    "NIGERIA": "NG", "NİJERYA": "NG",
    "KENYA": "KE", "KENYA": "KE",
    "GHANA": "GH", "GANA": "GH",
    "ETHIOPIA": "ET", "ETİYOPYA": "ET",
    "TANZANIA": "TZ", "TANZANYA": "TZ",
    "SUDAN": "SD", "SUDAN": "SD",
    "ANGOLA": "AO", "ANGOLA": "AO",
    "MOZAMBIQUE": "MZ", "MOZAMBİK": "MZ",
    "SENEGAL": "SN", "SENEGAL": "SN",
    "IVORY COAST": "CI", "CÔTE D'IVOIRE": "CI", "FILDİŞİ SAHİLİ": "CI",
    # Americas
    "UNITED STATES": "US", "USA": "US", "U.S.A.": "US",
    "AMERICA": "US", "UNITED STATES OF AMERICA": "US",
    "CANADA": "CA", "KANADA": "CA",
    "MEXICO": "MX", "MEKSIKA": "MX", "MEKSİKA": "MX",
    "BRAZIL": "BR", "BREZİLYA": "BR",
    "ARGENTINA": "AR", "ARJANTİN": "AR",
    "CHILE": "CL", "ŞİLİ": "CL",
    "COLOMBIA": "CO", "KOLOMBIYA": "CO",
    "PERU": "PE", "PERU": "PE",
    "VENEZUELA": "VE", "VENEZUELA": "VE",
    "ECUADOR": "EC", "EKVADOR": "EC",
    "URUGUAY": "UY", "URUGUAY": "UY",
    "PARAGUAY": "PY", "PARAGUAY": "PY",
    "PANAMA": "PA", "PANAMA": "PA",
    "COSTA RICA": "CR", "KOSTA RIKA": "CR",
    "DOMINICAN REPUBLIC": "DO", "DOMİNİK CUMHURİYETİ": "DO",
    # Oceania
    "AUSTRALIA": "AU", "AVUSTRALYA": "AU",
    "NEW ZEALAND": "NZ", "YENİ ZELANDA": "NZ",
    # ISO codes (already a code, normalize to uppercase)
    "TR": "TR", "DE": "DE", "PK": "PK", "US": "US", "GB": "GB",
    "IT": "IT", "ES": "ES", "FR": "FR", "IN": "IN", "CN": "CN",
    "JP": "JP", "KR": "KR", "RU": "RU", "BR": "BR", "AE": "AE",
    "SA": "SA", "EG": "EG", "GR": "GR", "NL": "NL", "BE": "BE",
    "PL": "PL", "RO": "RO", "UA": "UA", "BG": "BG", "PT": "PT",
    "SE": "SE", "NO": "NO", "DK": "DK", "FI": "FI", "AT": "AT",
    "CH": "CH", "CZ": "CZ", "HU": "HU", "SK": "SK", "SI": "SI",
    "HR": "HR", "RS": "RS", "IE": "IE", "LT": "LT", "LV": "LV",
    "EE": "EE", "MT": "MT", "CY": "CY", "LU": "LU", "IS": "IS",
    "TW": "TW", "VN": "VN", "TH": "TH", "MY": "MY", "ID": "ID",
    "PH": "PH", "SG": "SG", "BD": "BD", "LK": "LK", "QA": "QA",
    "KW": "KW", "BH": "BH", "OM": "OM", "JO": "JO", "LB": "LB",
    "IL": "IL", "IR": "IR", "IQ": "IQ", "YE": "YE", "SY": "SY",
    "ZA": "ZA", "MA": "MA", "DZ": "DZ", "TN": "TN", "LY": "LY",
    "NG": "NG", "KE": "KE", "GH": "GH", "ET": "ET", "TZ": "TZ",
    "SD": "SD", "AO": "AO", "MZ": "MZ", "SN": "SN", "CI": "CI",
    "CA": "CA", "MX": "MX", "AR": "AR", "CL": "CL", "CO": "CO",
    "PE": "PE", "VE": "VE", "EC": "EC", "UY": "UY", "PY": "PY",
    "PA": "PA", "CR": "CR", "DO": "DO", "AU": "AU", "NZ": "NZ",
}

_KNOWN_CITIES = frozenset({
    # Turkey
    "ISTANBUL", "ANKARA", "IZMIR", "İZMİR", "ANTALYA", "BURSA", "ADANA",
    "KONYA", "GAZIANTEP", "MERSIN", "MERSİN", "KOCAELI", "KAYSERI",
    "ESKISEHIR", "DENIZLI", "SAMSUN", "TRABZON", "ERZURUM", "MALATYA",
    "SAKARYA", "TEKIRDAG", "DIYARBAKIR", "HATAY", "MANISA", "KAHRAMANMARAS",
    "SANLIURFA", "KARS", "SIVAS", "VAN", "EDIRNE", "IZMIT", "CANAKKALE",
    "AYDIN", "MUGLA", "ISKENDERUN", "ALIAGA", "GEBZE", "DILOVASI",
    "CORLU", "KARAMAN", "KUTAHYA", "BALIKESIR", "KIRKLARELI", "ZONGULDAK",
    "ORDU", "GIRESUN", "RIZE", "SINOP", "KARABUK",
    # Pakistan
    "KARACHI", "LAHORE", "ISLAMABAD", "FAISALABAD", "RAWALPINDI",
    "MULTAN", "PESHAWAR", "QUETTA", "SIALKOT", "GUJRANWALA",
    # Germany
    "HAMBURG", "BERLIN", "MUNICH", "MÜNCHEN", "FRANKFURT", "BREMEN",
    "DUISBURG", "DUSSELDORF", "DÜSSELDORF", "STUTTGART", "COLOGNE", "KÖLN",
    "LEIPZIG", "DORTMUND", "ESSEN", "NUREMBERG", "NÜRNBERG",
    # Netherlands
    "ROTTERDAM", "AMSTERDAM", "UTRECHT", "EINDHOVEN", "GRONINGEN",
    # Belgium
    "ANTWERP", "BRUSSELS", "BRÜKSEL", "GENT", "LIEGE",
    # UK
    "LONDON", "MANCHESTER", "LIVERPOOL", "BIRMINGHAM", "LEEDS",
    "BRISTOL", "SOUTHAMPTON", "FELIXSTOWE", "TILBURY",
    # France
    "PARIS", "MARSEILLE", "LE HAVRE", "LYON", "BORDEAUX", "NANTES",
    "DUNKERQUE", "STRASBOURG", "TOULOUSE",
    # Italy
    "MILAN", "GENOA", "NAPLES", "TRIESTE", "VENICE",
    "LIVORNO", "ROME", "RAVENNA", "LA SPEZIA", "GIOIA TAURO",
    # Spain
    "BARCELONA", "VALENCIA", "ALGECIRAS", "MADRID", "BILBAO",
    "LAS PALMAS", "SEVILLE", "MALAGA",
    # USA
    "NEW YORK", "LOS ANGELES", "MIAMI", "HOUSTON", "CHICAGO",
    "SAVANNAH", "OAKLAND", "SEATTLE", "BALTIMORE", "BOSTON",
    "SAN FRANCISCO", "PHILADELPHIA", "DALLAS", "ATLANTA",
    "LONG BEACH", "TACOMA", "CHARLESTON",
    # UAE
    "DUBAI", "ABU DHABI", "SHARJAH",
    # China
    "SHANGHAI", "SHENZHEN", "BEIJING", "GUANGZHOU", "NINGBO",
    "TIANJIN", "QINGDAO", "DALIAN", "XIAMEN",
    # Other major ports
    "SINGAPORE", "HONG KONG", "BUSAN", "SEOUL", "TOKYO", "YOKOHAMA",
    "MUMBAI", "CHENNAI", "DELHI", "KOLKATA", "NHAVA SHEVA",
    "COLOMBO", "JAKARTA", "HO CHI MINH", "HAI PHONG", "BANGKOK",
    "GDANSK", "GDYNIA", "SZCZECIN",
    "HELSINKI", "OSLO", "COPENHAGEN", "STOCKHOLM",
    "RIO DE JANEIRO", "SANTOS", "BUENOS AIRES", "LIMA", "SANTIAGO",
    "JEBEL ALI", "DAMMAM", "JEDDAH", "MUSCAT", "DOHA",
    "ALEXANDRIA", "CASABLANCA", "DURBAN", "CAPE TOWN",
    "SYDNEY", "MELBOURNE", "AUCKLAND",
})


def _apply_role_code_mapping(instruction: ShippingInstruction) -> None:
    from app.models import PartyRoleCode

    _valid_roles = {r.value: r for r in PartyRoleCode}
    for party in instruction.parties:
        if party.party_role_code is None:
            continue
        raw = party.party_role_code.strip().upper()
        mapped = _ROLE_CODE_MAP.get(raw)
        if mapped is not None and mapped in _valid_roles:
            party.party_role_code = _valid_roles[mapped]


def _bind_container_cargo(instruction: ShippingInstruction, ocr_text: str) -> None:
    if not instruction.equipment_list or not instruction.cargo_items:
        return
    container_positions: list[tuple[int, int]] = []
    for idx, eq in enumerate(instruction.equipment_list):
        ref = eq.equipment_reference
        if ref:
            pos = ocr_text.casefold().find(ref.casefold())
            container_positions.append((idx, pos if pos >= 0 else 999999))
    cargo_positions: list[tuple[int, int]] = []
    for idx, ci in enumerate(instruction.cargo_items):
        desc = ci.description_of_goods or ""
        pos = ocr_text.casefold().find(desc.casefold()[:30]) if desc else 999999
        cargo_positions.append((idx, pos if pos >= 0 else 999999))
    container_positions.sort(key=lambda x: x[1])
    cargo_positions.sort(key=lambda x: x[1])
    if len(container_positions) == len(cargo_positions) and len(container_positions) > 1:
        reordered_eq: list = [None] * len(instruction.equipment_list)
        reordered_cargo: list = [None] * len(instruction.cargo_items)
        for new_idx, (orig_idx, _) in enumerate(container_positions):
            reordered_eq[new_idx] = instruction.equipment_list[orig_idx]
        for new_idx, (orig_idx, _) in enumerate(cargo_positions):
            reordered_cargo[new_idx] = instruction.cargo_items[orig_idx]
        instruction.equipment_list = reordered_eq
        instruction.cargo_items = reordered_cargo


def _detect_weight_unit(ocr_text: str, value_str: str) -> str:
    if not value_str or not ocr_text:
        return "KGM"
    idx = ocr_text.casefold().find(value_str.casefold())
    if idx == -1:
        return "KGM"
    window_start = max(0, idx - 5)
    window_end = min(len(ocr_text), idx + len(value_str) + 10)
    window = ocr_text[window_start:window_end].casefold()
    unit_map = {
        "lbs": "LBR", "lbr": "LBR", "pound": "LBR", "pounds": "LBR",
        "kg": "KGM", "kgs": "KGM", "kgm": "KGM", "kilogram": "KGM",
        "ton": "TON", "tons": "TON",
    }
    for keyword, unit in unit_map.items():
        if keyword in window:
            return unit
    return "KGM"


def _clean_location_name(location) -> None:
    if location is None or not location.location_name:
        return
    name = location.location_name.strip()
    if not name:
        return
    match = _PORT_PREFIX_PATTERN.match(name)
    if match:
        remainder = name[match.end():].strip()
        words = remainder.split()
        for i in range(len(words), 0, -1):
            candidate = " ".join(words[:i])
            if candidate.upper() in _KNOWN_PORTS:
                location.location_name = candidate
                return
        if remainder:
            location.location_name = remainder


def _normalize_party_addresses(normalized: ShippingInstruction) -> None:
    """Deterministik adres ve ulke kodu parcAlayici.

    Her Party'nin Address'inde:
    1. street sonundan ulke ismini bulup country_code'a tasir
    2. street icinden bilinen sehir ismini bulup city'ye tasir
    3. Kalan metni temizler
    """
    for party in normalized.parties:
        if party.address is None:
            continue
        address = party.address

        # --- Ulke kodu cikarma ---
        country_already_valid = (
            address.country_code is not None
            and re.fullmatch(r"[A-Za-z]{2}", address.country_code or "")
        )
        if not country_already_valid:
            # street sonundan ulke ismi ara
            if address.street:
                found_code = None
                clean_street = address.street
                for separator in ("/", ",", "-"):
                    parts = [p.strip() for p in clean_street.rsplit(separator, 1)]
                    if len(parts) == 2:
                        last_part = parts[1].strip().upper()
                        if last_part in _COUNTRY_NAME_TO_CODE:
                            found_code = _COUNTRY_NAME_TO_CODE[last_part]
                            clean_street = parts[0].strip()
                            break
                # Tum street'i ulke olarak dene (sadece ulke ismi varsa)
                if found_code is None:
                    street_upper = address.street.strip().upper()
                    if street_upper in _COUNTRY_NAME_TO_CODE:
                        found_code = _COUNTRY_NAME_TO_CODE[street_upper]
                        clean_street = ""
                if found_code is not None:
                    address.country_code = found_code
                    address.street = clean_street if clean_street else None

            # country_code hala bossa city'de de dene
            if address.country_code is None and address.city:
                city_upper = address.city.strip().upper()
                if city_upper in _COUNTRY_NAME_TO_CODE:
                    address.country_code = _COUNTRY_NAME_TO_CODE[city_upper]
                    address.city = None

        # --- Sehir cikarma (sadece city None ise) ---
        if address.city is None and address.street:
            # street'i bol ve bilinen sehirleri ara
            tokens = re.split(r"\s*[,/\-]\s*|\s+MAH\.?\s*|\s+CAD\.?\s*|\s+CD\.?\s*|\s+SOK\.?\s*|\s+SK\.?\s*|\s+NO:?\s*|\s+NO\.?\s*", address.street)
            found_city = None
            best_idx = -1
            for i, token in enumerate(tokens):
                token_upper = token.strip().upper()
                if token_upper in _KNOWN_CITIES:
                    # En sondaki sehir eslesmesini tercih et
                    if i >= best_idx:
                        found_city = token.strip()
                        best_idx = i
            if found_city is not None:
                address.city = found_city
                # Sehri street'ten cikar
                escaped_city = re.escape(found_city)
                address.street = re.sub(
                    r"[,/\-]*\s*" + escaped_city + r"\s*[,/\-]*",
                    "",
                    address.street,
                    count=1,
                ).strip()

        # --- Street temizligi ---
        if address.street is not None:
            cleaned = address.street.strip()
            cleaned = re.sub(r"^[,/\-\s]+", "", cleaned)
            cleaned = re.sub(r"[,/\-\s]+$", "", cleaned)
            address.street = cleaned if cleaned else address.street


def _parse_volume_number(raw: str) -> Optional[float]:
    """Hacim sayisi ayristirici: hem ondalik hem binlik ayraci formatini destekler.

    Ornekler:
      28.16  -> 28.16 (ondalik, cunku .16 2 haneli)
      28,16  -> 28.16 (Avrupa ondalik)
      26.080,00 -> 26080.00 (binlik ayracli)
    """
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        return None
    if "," in cleaned:
        # Virgul varsa Avrupa formati: nokta=binlik, virgul=ondalik
        return _parse_european_number(cleaned)
    # Sadece nokta var. 1-2 haneli son grup -> ondalik; 3 haneli -> binlik olabilir
    if "." in cleaned:
        parts = cleaned.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            # Tum gruplar 3 haneli -> binlik ayraci
            return _parse_european_number(cleaned)
        # Son grup 1-2 haneli -> ondalik
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_cargo_volume(normalized: ShippingInstruction, ocr_text: str) -> None:
    """Hacim/CBM motoru.

    OCR metninde CBM/M3 hacim degerlerini regex ile yakalar,
    _parse_european_number ile float'a cevirir ve CargoItem'lara dagitir.
    """
    if not ocr_text.strip():
        return
    from app.models import CargoVolume

    volume_matches: list[float] = []
    for pattern in (
        r"(?im)(?:VOLUME|CBM|M3|CUBIC\s*MET(?:ER|RE)S?)\s*[:#\-]?\s*(?P<value>[\d][\d.,]*)",
        r"(?im)(?P<value>[\d][\d.,]*)\s*(?:CBM|M3|CUBIC\s*MET(?:ER|RE)S?)",
    ):
        for match in re.finditer(pattern, ocr_text):
            raw_value = match.group("value")
            parsed = _parse_volume_number(raw_value)
            if parsed is not None and parsed > 0:
                volume_matches.append(parsed)
    # Deduplicate
    seen: set[float] = set()
    deduped: list[float] = []
    for val in volume_matches:
        if val not in seen:
            seen.add(val)
            deduped.append(val)
    volume_matches = deduped
    if not volume_matches:
        return
    cargo_items = normalized.cargo_items
    if not cargo_items:
        volume_value = volume_matches[0]
        from app.models import CargoItem
        normalized.cargo_items.append(
            CargoItem(volume=CargoVolume(volume_value=volume_value))
        )
        return
    # Dagitim: sirayla, sadece volume'u bos olanlara
    vol_idx = 0
    for cargo_item in cargo_items:
        if cargo_item.volume is not None:
            continue
        if vol_idx >= len(volume_matches):
            break
        cargo_item.volume = CargoVolume(volume_value=volume_matches[vol_idx])
        vol_idx += 1
    # Kalan hacim degerleri varsa yeni CargoItem ekle
    while vol_idx < len(volume_matches):
        from app.models import CargoItem
        normalized.cargo_items.append(
            CargoItem(volume=CargoVolume(volume_value=volume_matches[vol_idx]))
        )
        vol_idx += 1


def _normalize_equipment_types(normalized: ShippingInstruction, ocr_text: str) -> None:
    """Konteyner tipi (ISO Equipment Code) motoru.

    OCR metninde insan-yazimi konteyner tiplerini (40HC, 20GP vb.) arar
    ve DCSA ISO 6346 kodlarina (45G1, 22G1 vb.) donusturur.
    """
    if not normalized.equipment_list or not ocr_text.strip():
        return
    from app.models import Equipment
    _valid_iso_pattern = re.compile(r"^[0-9A-Z]{4}$")
    # Tum OCR eslesmelerini konumlari ve kodlariyla topla
    all_ocr_matches: list[tuple[int, str]] = []
    for m in _CONTAINER_TYPE_PATTERN.finditer(ocr_text):
        normalized_key = re.sub(r"\s+", " ", m.group().strip().upper())
        normalized_key = re.sub(r"['’]", "", normalized_key)
        iso_code = _CONTAINER_TYPE_MAP.get(normalized_key)
        if iso_code:
            all_ocr_matches.append((m.start(), iso_code))
    assigned_match_indices: set[int] = set()

    for equipment in normalized.equipment_list:
        if equipment.iso_equipment_code is not None:
            existing = equipment.iso_equipment_code.strip().upper()
            if _valid_iso_pattern.match(existing):
                continue
        found_code: str | None = None
        ref = equipment.equipment_reference
        if ref:
            ref_pos = ocr_text.casefold().find(ref.casefold())
            if ref_pos >= 0:
                # Henuz atanmamis en yakin tip eslesmesini bul
                best_distance = 999999
                best_idx = -1
                for idx, (match_pos, iso_code) in enumerate(all_ocr_matches):
                    if idx in assigned_match_indices:
                        continue
                    distance = abs(ref_pos - match_pos)
                    if distance < best_distance:
                        best_distance = distance
                        best_idx = idx
                        found_code = iso_code
                if best_idx >= 0:
                    assigned_match_indices.add(best_idx)
        if found_code is None:
            # Global fallback: henuz kullanilmamis ilk eslesmeyi al
            for idx, (pos, iso_code) in enumerate(all_ocr_matches):
                if idx not in assigned_match_indices:
                    found_code = iso_code
                    assigned_match_indices.add(idx)
                    break
        if found_code is not None:
            equipment.iso_equipment_code = found_code


def normalize_extracted_instruction(
    instruction: ShippingInstruction,
    ocr_text: str = "",
) -> ShippingInstruction:
    normalized = instruction.model_copy(deep=True)
    _apply_role_code_mapping(normalized)
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
    for party in normalized.parties:
        contact = party.contact_details
        if contact and contact.name:
            name_val = contact.name.strip()
            if re.match(r"(?i)^(?:tel|telefon|telephone)[\s:.\-]+\d", name_val):
                phone_part = re.sub(r"(?i)^(?:tel|telefon|telephone)[\s:.\-]+", "", name_val)
                if phone_part.isdigit() and not contact.phone_number:
                    contact.phone_number = phone_part
                contact.name = None
            elif re.fullmatch(r"[\d\s\-()+./]+", name_val):
                if not contact.phone_number:
                    contact.phone_number = name_val
                contact.name = None
    _normalize_party_addresses(normalized)
    for plan in normalized.transport_plans:
        _clean_location_name(plan.port_of_loading)
        _clean_location_name(plan.port_of_discharge)
        _clean_location_name(plan.place_of_receipt)
        _clean_location_name(plan.place_of_delivery)
    brut_value = _extract_labeled_value(
        ocr_text,
        (
            r"(?im)(?:BRUT|GROSS\s+WEIGHT|GROSS|G\.W\.|GW)\s*[:#\-]?\s*(?:WEIGHT|AGIRLIK|WT\.?)?\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:\.[\d]{3})*(?:,[\d]+)?)",
        ),
    )
    net_value = _extract_labeled_value(
        ocr_text,
        (
            r"(?im)(?:NET|NET\s+WEIGHT|N\.W\.|NW)\s*[:#\-]?\s*(?:WEIGHT|AGIRLIK|WT\.?)?\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:\.[\d]{3})*(?:,[\d]+)?)",
        ),
    )
    if brut_value is not None:
        parsed_brut = _parse_european_number(brut_value)
        if parsed_brut is not None and parsed_brut > 0:
            from app.models import Weight, WeightUnit
            brut_unit_str = _detect_weight_unit(ocr_text, brut_value)
            brut_unit = WeightUnit.KILOGRAM if brut_unit_str == "KGM" else (
                WeightUnit.TON if brut_unit_str == "TON" else WeightUnit.KILOGRAM
            )
            applied = False
            for equipment in normalized.equipment_list:
                if equipment.cargo_gross_weight is None or equipment.cargo_gross_weight.weight is None:
                    equipment.cargo_gross_weight = Weight(weight=parsed_brut, unit=brut_unit)
                    applied = True
                    break
            if not applied:
                from app.models import Equipment
                new_eq = Equipment(cargo_gross_weight=Weight(weight=parsed_brut, unit=brut_unit))
                normalized.equipment_list.append(new_eq)
    if net_value is not None:
        parsed_net = _parse_european_number(net_value)
        if parsed_net is not None and parsed_net > 0:
            from app.models import CargoWeight
            net_unit_str = _detect_weight_unit(ocr_text, net_value)
            applied = False
            for cargo_item in normalized.cargo_items:
                if cargo_item.weight is None or cargo_item.weight.weight_value is None:
                    cargo_item.weight = CargoWeight(weight_value=parsed_net, unit=net_unit_str)
                    applied = True
                    break
            if not applied:
                from app.models import CargoItem
                new_item = CargoItem(weight=CargoWeight(weight_value=parsed_net, unit=net_unit_str))
                normalized.cargo_items.append(new_item)
    _bind_container_cargo(normalized, ocr_text)
    _normalize_cargo_volume(normalized, ocr_text)
    ocr_containers = _extract_containers_from_ocr(ocr_text)
    if ocr_containers:
        existing_refs: set[str] = set()
        for equipment in normalized.equipment_list:
            if equipment.equipment_reference:
                existing_refs.add(re.sub(r"\s+", "", equipment.equipment_reference).upper())
        for container_ref in ocr_containers:
            if container_ref not in existing_refs:
                from app.models import Equipment
                normalized.equipment_list.append(Equipment(equipment_reference=container_ref))
    _normalize_equipment_types(normalized, ocr_text)
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
    segmented_ocr: Optional[Tuple[str, str, str]] = None,
) -> Tuple[ShippingInstruction, str]:
    if segmented_ocr is not None:
        upper_text, middle_text, lower_text = segmented_ocr
        merged, raw_outputs = run_threestage_extraction(
            upper_text, middle_text, lower_text,
            document_language, output_language,
        )
        combined_raw = json.dumps(
            {str(k): v for k, v in raw_outputs.items()},
            ensure_ascii=False,
        )
        return merged, combined_raw
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


def _extract_targeted_ocr_excerpt(
    ocr_text: str, findings: list[dict[str, Any]], context_lines: int = 3
) -> str:
    """Extract only OCR lines relevant to the findings, not the full text."""
    if not findings:
        return ocr_text

    # Keywords associated with common field paths
    keyword_map = {
        "shipper": ("shipper", "exporter", "seller", "gönderici", "ihracatçı"),
        "consignee": ("consignee", "buyer", "receiver", "alıcı", "ithalatçı"),
        "party": ("party", "shipper", "consignee", "notify"),
        "port_of_loading": ("port of loading", "loading", "pol", "yükleme"),
        "port_of_discharge": ("port of discharge", "discharge", "pod", "boşaltma"),
        "equipment": ("container", "equipment", "seal", "konteyner"),
        "weight": ("weight", "gross", "kg", "kgs", "kgm", "ağırlık"),
        "cargo": ("cargo", "goods", "description", "package", "mal"),
        "reference": ("reference", "booking", "no", "number", "referans"),
        "date": ("date", "issue", "tarih"),
        "vessel": ("vessel", "voyage", "imo", "ship", "gemi"),
    }

    terms: set[str] = set()
    for finding in findings:
        path = finding.get("field_path", "").casefold()
        for key, keywords in keyword_map.items():
            if key in path:
                terms.update(keywords)

    if not terms:
        return ocr_text

    lines = ocr_text.splitlines()
    matched_indices: set[int] = set()
    for i, line in enumerate(lines):
        lowered = line.casefold()
        if any(term in lowered for term in terms):
            for offset in range(-context_lines, context_lines + 1):
                idx = i + offset
                if 0 <= idx < len(lines):
                    matched_indices.add(idx)

    if not matched_indices:
        return ocr_text

    selected = [lines[i] for i in sorted(matched_indices)]
    return "\n".join(selected)


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

    # Use targeted OCR excerpt to reduce token usage
    targeted_ocr = _extract_targeted_ocr_excerpt(ocr_text, findings)
    if len(targeted_ocr) * 4 > len(ocr_text) * 3:
        # Targeted excerpt isn't significantly smaller; use full text
        targeted_ocr = ocr_text

    return (
        f"System: {_system_prompt}\n\n"
        f"The source is {source_language}. Recheck the initial extraction against the OCR text. "
        "Correct only values directly supported by the OCR text. Resolve the listed deterministic validation "
        "findings when the document contains the required evidence. Keep unsupported fields null and preserve "
        "identifiers, names, addresses, locations, codes, units, and numeric values exactly.\n\n"
        f"Validation findings:\n{findings_json}\n\n"
        f"Initial extraction:\n{initial_json}\n\n"
        f"JSON Schema:\n{schema}\n\n"
        f"OCR Text:\n{targeted_ocr}\n\n"
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
