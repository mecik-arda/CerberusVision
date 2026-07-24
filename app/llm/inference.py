from __future__ import annotations
import ast
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import unicodedata
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple
from app.config import settings
from app.models import (
    DocumentStatusCode,
    FreightPaymentTermCode,
    ShippingInstruction,
    TransportDocumentType,
)


_llm_pipeline = None
_llm_pipeline_key: Optional[str] = None
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
    "weight (BRUT/GROSS/G.W.) belongs in equipment cargo_gross_weight and NET/net weight (NET/N.W.) belongs in cargo_items.weight. "
    "When OCR shows BRUT and NET together (e.g. 'BRUT:26.080,00 KG- NET: 24.776,00 KG'), "
    "BRUT=gross=cargo_gross_weight, NET=net=cargo_items.weight. Never put gross in cargo_items. "
    "Parse European-formatted quantities: 26.080,00 -> 26080.00, 28,16 -> 28.16, 24.776,00 -> 24776.00. "
    "Parse US-formatted quantities: 18,750.00 -> 18750.00 (comma=thousands, dot=decimal). "
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
    "--- DANGEROUS GOODS --- "
    "UN NO / UN Number maps to un_number. Preserve format as 'UN XXXX'. "
    "IMDG Class maps to imdg_class. Preserve format as 'Class X'. "
    "Packing Group maps to packing_group. Preserve format as 'PG X' (I, II, or III). "
    "Flash Point maps to flash_point with temperature (preserve negative sign for sub-zero values) and unit (CEL or FAH). "
    "Emergency Contact maps to emergency_contact with name and phone_number. "
    "Technical Name maps to technical_name. "
    "Only populate dangerous_goods_list when the cargo item actually contains hazardous materials. "
    "Non-hazardous cargo items must have null or absent dangerous_goods_list. "
    "--- CARGO --- "
    "description_of_goods contains only the goods "
    "description and must exclude leading package quantities and package-kind words such as PALLETS, CARTONS, BOXES, "
    "or CRATES, and must exclude wood packaging statements, marks prefixes, and freight clauses. "
    "Equipment/container references normally contain four letters "
    "followed by seven digits; preserve them in equipment_reference and link matching cargo equipment references. "
    "Container type codes: 40HC/40'HC/40 HIGH CUBE -> 45G1, 20GP/20'GP/20 STANDARD -> 22G1, "
    "40GP/40'GP/40 STANDARD -> 42G1, 40 REEFER -> 42R1, 20 REEFER -> 22R1, 45 HC REEFER -> 45R1. "
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
    "BRUT/ GROSS / G.W. -> cargo_gross_weight (ekipman seviyesinde), NET / N.W. -> cargo_items.weight. "
    "Avrupa formatli sayilari ayristir: 26.080,00 -> 26080.00, 28,16 -> 28.16, 24.776,00 -> 24776.00. "
    "US formatli sayilari ayristir: 18,750.00 -> 18750.00. "
    "--- KONTEYNER KURALLARI --- "
    "Konteyner referanslari genellikle 4 harf + 7 rakam formatindadir. "
    "ISO 6346 kontrol basamagini dogrula. equipment_reference alaninda sakla. "
    "Konteyner tip kodlarini tanimla: 40HC/40 HIGH CUBE/40HQ -> 45G1, "
    "20GP/20GP/20 STANDARD/20DC -> 22G1, 40GP/40 STANDARD/40DC -> 42G1, "
    "40 REEFER -> 42R1, 20 REEFER -> 22R1, 45 HC REEFER -> 45R1. "
    "--- TEHLIKELI MADDE KURALLARI (DANGEROUS GOODS) --- "
    "UN NO/UN Number: 'UN 1993' veya 'UN1993' formatinda. "
    "IMDG Class: 'Class 3', 'Class 8', '3', '8' formatlarinda. "
    "Packing Group: 'PG II', 'PG III', 'II', 'III' formatlarinda. "
    "Flash Point: eksi isaretini (-) koru, 'CEL' veya 'FAH' birimiyle birlikte. "
    "Emergency Contact: CHEMTREC gibi kurum adi ve +1-703-527-3887 gibi telefon. "
    "Technical Name: kimyasal maddenin teknik adi. "
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


def get_llm_pipeline(use_adapter: bool = True):
    global _llm_pipeline, _llm_pipeline_key
    import openvino_genai
    from app.llm.lora_adapter import enabled_adapter_path

    model_path = Path(settings.model.model_path)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. "
            "Run scripts/wsl_model_setup.sh or set QWEN_MODEL_PATH to an OpenVINO model."
        )
    qwen_adapter_path = (
        enabled_adapter_path(
            settings.lora_enabled,
            settings.lora_adapter_path,
            "qwen",
        )
        if use_adapter
        else None
    )
    pipeline_key = "|".join(
        (
            str(model_path.resolve()),
            settings.model.device,
            str(qwen_adapter_path or ""),
        )
    )
    if _llm_pipeline is not None and _llm_pipeline_key == pipeline_key:
        return _llm_pipeline
    pipeline_config = {
        "CACHE_DIR": settings.model.cache_dir,
        "CACHE_MODE": "OPTIMIZE_SIZE",
        "PERFORMANCE_HINT": "LATENCY",
    }
    if os.environ.get("CERBERUS_BENCHMARK_DETERMINISTIC") == "1":
        pipeline_config["NUM_STREAMS"] = "1"
    weights_path = model_path / "openvino_model.bin"
    if weights_path.exists():
        pipeline_config["WEIGHTS_PATH"] = str(weights_path)
    if settings.model.kv_cache_precision:
        pipeline_config["KV_CACHE_PRECISION"] = settings.model.kv_cache_precision
    if qwen_adapter_path is not None:
        adapter = openvino_genai.Adapter(str(qwen_adapter_path))
        adapter_config = openvino_genai.AdapterConfig()
        adapter_config.add(adapter, 1.0)
        pipeline_config["adapters"] = adapter_config
    _llm_pipeline = openvino_genai.LLMPipeline(
        str(model_path), settings.model.device, **pipeline_config
    )
    _llm_pipeline_key = pipeline_key
    return _llm_pipeline


def reset_llm_pipeline() -> None:
    global _llm_pipeline, _llm_pipeline_key
    _llm_pipeline = None
    _llm_pipeline_key = None


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
    ocr_text = _apply_utf8_normalization(ocr_text)
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


def _has_excessive_output_repetition(raw_output: str) -> bool:
    tokens = re.findall(r"\w+|[^\w\s]", raw_output.casefold())
    window_size = 24
    if len(tokens) < window_size * 4:
        return False
    occurrence_counts: Dict[Tuple[str, ...], int] = {}
    for start_index in range(0, len(tokens) - window_size + 1, 8):
        token_window = tuple(tokens[start_index:start_index + window_size])
        occurrence_counts[token_window] = (
            occurrence_counts.get(token_window, 0) + 1
        )
        if occurrence_counts[token_window] >= 4:
            return True
    return False


def _qwen_adapter_runtime_enabled() -> bool:
    from app.llm.lora_adapter import enabled_adapter_path

    return enabled_adapter_path(
        settings.lora_enabled,
        settings.lora_adapter_path,
        "qwen",
    ) is not None


def _run_stage_inference_once(
    ocr_text: str,
    stage: int,
    document_language: str = "en",
    output_language: str = "en",
    use_adapter: bool = True,
) -> Tuple[ShippingInstruction, str]:
    pipe = get_llm_pipeline(use_adapter=use_adapter)
    prompt = build_stage_prompt(ocr_text, stage, document_language, output_language)
    schema = get_stage_schema(stage)
    config = _build_generation_config_for_schema(schema)
    result = pipe.generate(prompt, config)
    raw_output = str(result)
    assert raw_output.strip(), f"Asama {stage} LLM ciktisi bos"
    if _has_excessive_output_repetition(raw_output):
        raise ValueError(f"Asama {stage} LLM ciktisi asiri tekrar iceriyor")
    try:
        cleaned = _extract_json(raw_output)
        data = json.loads(cleaned)
        instruction = ShippingInstruction.model_validate(data)
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        instruction = ShippingInstruction.model_validate(data)
    return instruction, raw_output


def run_stage_inference(
    ocr_text: str,
    stage: int,
    document_language: str = "en",
    output_language: str = "en",
) -> Tuple[ShippingInstruction, str]:
    try:
        return _run_stage_inference_once(
            ocr_text,
            stage,
            document_language,
            output_language,
            use_adapter=True,
        )
    except Exception as adapter_error:
        if not _qwen_adapter_runtime_enabled():
            raise
        logger.warning(
            "Qwen adapter stage %s failed, retrying with base model: %s",
            stage,
            adapter_error,
        )
        reset_llm_pipeline()
        try:
            return _run_stage_inference_once(
                ocr_text,
                stage,
                document_language,
                output_language,
                use_adapter=False,
            )
        except Exception as base_error:
            raise base_error from adapter_error
        finally:
            reset_llm_pipeline()


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


def _split_text_by_container_refs(text: str) -> list[str]:
    container_pattern = re.compile(r"\b[A-Z]{4}\d{7}\b")
    lines = text.split("\n")
    chunk_boundaries = []
    for i, line in enumerate(lines):
        if container_pattern.search(line):
            chunk_boundaries.append(i)
    if len(chunk_boundaries) <= 1:
        return [text]
    header_lines = "\n".join(lines[:chunk_boundaries[0]]) if chunk_boundaries[0] > 0 else ""
    chunks = []
    for j, start in enumerate(chunk_boundaries):
        end = chunk_boundaries[j + 1] if j + 1 < len(chunk_boundaries) else len(lines)
        chunk_lines = lines[start:end]
        chunk_body = "\n".join(chunk_lines)
        chunk_text = (header_lines + "\n" + chunk_body) if header_lines else chunk_body
        chunks.append(chunk_text)
    return chunks


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
    container_chunks = [combined_middle_lower]
    if len(container_chunks) > 1:
        all_equipment = []
        all_cargo = []
        for chunk_text in container_chunks:
            chunk_inst, chunk_raw = run_stage_inference(
                chunk_text, 3, document_language, output_language,
            )
            raw_outputs[3] = raw_outputs.get(3, "") + "\n--- CHUNK ---\n" + chunk_raw
            chunk_normalized = normalize_extracted_instruction(chunk_inst, chunk_text)
            all_equipment.extend(chunk_normalized.equipment_list)
            all_cargo.extend(chunk_normalized.cargo_items)
        stage3_instruction = ShippingInstruction(
            equipment_list=all_equipment, cargo_items=all_cargo,
        )
        stage3_normalized = stage3_instruction
    else:
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
    ocr_text = _apply_utf8_normalization(ocr_text)
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
    use_adapter: bool = True,
) -> str:
    pipe = get_llm_pipeline(use_adapter=use_adapter)
    prompt = build_prompt(ocr_text, document_language, output_language)
    config = _build_generation_config()
    result = pipe.generate(prompt, config)
    raw_output = str(result)
    if _has_excessive_output_repetition(raw_output):
        raise ValueError("LLM ciktisi asiri tekrar iceriyor")
    return raw_output


def _build_generation_config():
    return _build_generation_config_for_schema(get_json_schema())


def _build_generation_config_for_schema(schema: Dict[str, Any]):
    import openvino_genai

    config = openvino_genai.GenerationConfig()
    config.max_new_tokens = settings.model.max_new_tokens
    if settings.temperature > 0.0:
        config.do_sample = True
        config.temperature = settings.temperature
    else:
        config.do_sample = False
        
    try:
        config.repetition_penalty = settings.repetition_penalty
    except AttributeError:
        pass
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
_PORT_PREFIX_BLACKLIST = frozenset({
    "LOS", "LAS", "EL", "LA", "LE", "DE", "DA", "DO", "VAN", "VON", "SAN", "SANTA",
    "JEBEL", "PORT", "PUERTO", "RIO",
})
_PORT_PREFIX_WHITELIST = frozenset({
    "TCEGE", "COP", "GEMLIK", "MERSIN",
})
_KNOWN_PORTS = frozenset({
    "ALIAGA", "ISTANBUL", "IZMIR", "MERSIN", "ANTALYA", "SAMSUN", "TRABZON",
    "KARACHI", "HAMBURG", "ROTTERDAM", "ANTWERP", "SINGAPORE", "SHANGHAI",
    "HONG KONG", "BUSAN", "TOKYO", "NEW YORK", "LOS ANGELES", "MIAMI",
    "RIO DE JANEIRO", "SANTOS", "DUBAI", "JEBEL ALI", "HO CHI MINH",
    "HAI PHONG", "COLOMBO", "CHENNAI", "MUMBAI", "LONDON", "FELIXSTOWE",
    "GENOA", "BARCELONA", "VALENCIA", "PIRAEUS", "GDANSK", "GDYNIA",
})


def _parse_european_number(raw: str) -> Optional[float]:
    """Parse European or mixed-format numeric strings.

    Smart heuristic: if both ',' and '.' are present, the rightmost
    separator with exactly 2 decimal digits is treated as the decimal
    marker; the other is a thousands separator.

    Examples:
      26.080,00 -> 26080.00 (European: dot=thousands, comma=decimal)
      18,750.00 -> 18750.00 (US: comma=thousands, dot=decimal)
      28.16     -> 28.16    (simple dot=decimal)
      28,16     -> 28.16    (simple comma=decimal)
    """
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        return None
    # If both comma and dot present, determine which is the decimal separator
    if "," in cleaned and "." in cleaned:
        comma_pos = cleaned.rfind(",")
        dot_pos = cleaned.rfind(".")
        if dot_pos > comma_pos:
            # Dot is the rightmost — treat dot as decimal, comma as thousands
            # e.g. "18,750.00" -> remove commas, keep dot
            normalized = cleaned.replace(",", "")
        else:
            # Comma is the rightmost — European format: dot=thousands, comma=decimal
            # e.g. "26.080,00" -> remove dots, replace comma with dot
            normalized = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # Only comma present — could be "28,16" (decimal) or "26,080" (thousands)
        comma_pos = cleaned.rfind(",")
        after_comma = cleaned[comma_pos + 1:]
        if len(after_comma) in (1, 2) and comma_pos > 0:
            # Short suffix (1-2 digits) → comma is decimal separator
            normalized = cleaned.replace(",", ".")
        else:
            # Long or no suffix → comma could be thousands, just remove
            normalized = cleaned.replace(",", "")
    else:
        normalized = cleaned
    try:
        return float(normalized)
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
    # 45' High Cube Reefer (edge case: "45 HC REEFER")
    "45 HC REEFER": "45R1", "45' HC REEFER": "45R1",
    "45HC REEFER": "45R1", "45'HC REEFER": "45R1",
    "45HI CUBE REEFER": "45R1", "45 HI CUBE REEFER": "45R1",
    "45HCR": "45R1",
    # 20' General Purpose
    "20GP": "22G1", "20'GP": "22G1", "20 GP": "22G1", "20' GP": "22G1",
    "20GENERAL PURPOSE": "22G1", "20 GENERAL PURPOSE": "22G1",
    "20STANDARD": "22G1", "20 STANDARD": "22G1", "20' STANDARD": "22G1",
    "20DC": "22G1", "20' DC": "22G1", "20 DRY": "22G1", "20 DRY VAN": "22G1",
    "20DV": "22G1", "20' DV": "22G1",
    # 40' General Purpose
    "40GP": "42G1", "40'GP": "42G1", "40 GP": "42G1", "40' GP": "42G1",
    "40GENERAL PURPOSE": "42G1", "40 GENERAL PURPOSE": "42G1",
    "40STANDARD": "42G1", "40 STANDARD": "42G1", "40' STANDARD": "42G1",
    "40DC": "42G1", "40' DC": "42G1", "40 DRY": "42G1", "40 DRY VAN": "42G1",
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
    r"40\s*[''’]?\s*(?:HC|HIGH\s*CUBE|HQ)|"
    r"20\s*[''’]?\s*(?:GP|GENERAL\s*PURPOSE|STANDARD|DC|DV|DRY(?:\s+VAN)?|RF|REEFER|REFRIGERATED|OT|OPEN\s*TOP|FR|FLAT\s*RACK|FLAT|TK|TANK)|"
    r"40\s*[''’]?\s*(?:GP|GENERAL\s*PURPOSE|STANDARD|DC|DV|DRY(?:\s+VAN)?|RF|REEFER|REFRIGERATED|OT|OPEN\s*TOP|FR|FLAT\s*RACK|FLAT|TK|TANK)|"
    r"45\s*[''’]?\s*(?:HC|HIGH\s*CUBE|HQ)(?:\s*REEFER)?"
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
    "JEBEL ALI", "NHAVA SHEVA", "PORT KLANG", "TANJUNG PELEPAS",
    "LAEM CHABANG", "CAI MEP", "VUNG TAU", "DAMMAM", "JEDDAH",
    "ALEXANDRIA", "CASABLANCA", "DURBAN", "CAPE TOWN",
    "ICD TUGHLAKABAD", "TUGHLAKABAD",
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
    # Only strip prefix if it's a known OCR artifact, not a real word prefix
    match = _PORT_PREFIX_PATTERN.match(name)
    if match:
        prefix = match.group(1).upper()
        # Skip if prefix is a common word that's part of a real name
        if prefix in _PORT_PREFIX_BLACKLIST:
            # JEBEL ALI, LOS ANGELES, RIO DE JANEIRO — keep as-is
            pass
        elif prefix in _PORT_PREFIX_WHITELIST:
            # Known OCR artifacts: TCEGE, COP — strip
            remainder = name[match.end():].strip()
            words = remainder.split()
            for i in range(len(words), 0, -1):
                candidate = " ".join(words[:i])
                if candidate.upper() in _KNOWN_PORTS:
                    location.location_name = candidate
                    return
            if remainder:
                location.location_name = remainder
        else:
            # Unknown prefix — check if the remainder is a known port
            remainder = name[match.end():].strip()
            words = remainder.split()
            found = False
            for i in range(len(words), 0, -1):
                candidate = " ".join(words[:i])
                if candidate.upper() in _KNOWN_PORTS:
                    location.location_name = candidate
                    found = True
                    break
            if not found and remainder:
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
        for field_name in ("street", "city", "postal_code", "country_code"):
            field_value = getattr(address, field_name)
            if field_value is not None and not any(
                character.isalnum() for character in field_value
            ):
                setattr(address, field_name, None)

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
                    r"[,/\-]?\s*" + escaped_city + r"\s*[,/\-]?",
                    "",
                    address.street,
                    count=1,
                ).strip()

        if address.street is not None:
            cleaned = address.street.strip()
            cleaned = re.sub(r"^[,/\-\s]+", "", cleaned)
            cleaned = re.sub(r"[,/\-\s]+$", "", cleaned)
            address.street = cleaned if cleaned else address.street
        if all(
            getattr(address, field_name) is None
            for field_name in ("street", "city", "postal_code", "country_code")
        ):
            party.address = None


def _deduplicate_bl_document_references(
    normalized: ShippingInstruction,
) -> None:
    unique_bl_references: set[str] = set()
    retained_references = []
    for document_reference in normalized.document_references:
        type_code = (document_reference.type_code or "").strip().casefold()
        reference_number = document_reference.reference_number
        if type_code != "bl" or reference_number is None:
            retained_references.append(document_reference)
            continue
        normalized_reference_number = " ".join(reference_number.split()).casefold()
        if not normalized_reference_number:
            retained_references.append(document_reference)
            continue
        if normalized_reference_number in unique_bl_references:
            continue
        unique_bl_references.add(normalized_reference_number)
        retained_references.append(document_reference)
    normalized.document_references = retained_references


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


def _normalize_dangerous_goods(normalized: ShippingInstruction, ocr_text: str) -> None:
    """Deterministik tehlikeli madde normalizasyonu.

    LLM ciktisindaki UN Number, IMDG Class, Packing Group ve Flash Point
    degerlerini OCR metni ile dogrular, eksikleri tamamlar ve format standartlastirir.
    """
    if not normalized.cargo_items:
        return
    for cargo_item in normalized.cargo_items:
        if cargo_item.dangerous_goods_list is None:
            continue
        for dg in cargo_item.dangerous_goods_list:
            # UN Number: "UN1993" -> "UN 1993", "1993" -> "UN 1993"
            if dg.un_number:
                un_raw = dg.un_number.strip()
                un_clean = re.sub(r"\s+", "", un_raw.upper())
                if re.fullmatch(r"UN\d{4}", un_clean):
                    dg.un_number = f"{un_clean[:2]} {un_clean[2:]}"
                elif re.fullmatch(r"\d{4}", un_clean):
                    dg.un_number = f"UN {un_clean}"
            # IMDG Class: "3" -> "Class 3", "8" -> "Class 8", "Class3" -> "Class 3"
            if dg.imdg_class:
                cls_raw = dg.imdg_class.strip()
                cls_clean = re.sub(r"\s+", "", cls_raw)
                class_match = re.match(r"(?:Class)?(\d+(?:\.\d+)?)", cls_clean, re.IGNORECASE)
                if class_match:
                    dg.imdg_class = f"Class {class_match.group(1)}"
            # Packing Group: "II" -> "PG II", "pg2" -> "PG II", "2" -> "PG II"
            if dg.packing_group:
                pg_raw = dg.packing_group.strip().upper()
                pg_clean = re.sub(r"\s+", "", pg_raw)
                roman_map = {"I": "I", "II": "II", "III": "III", "1": "I", "2": "II", "3": "III"}
                pg_match = re.match(r"(?:PG)?(I{1,3}|\d)", pg_clean)
                if pg_match:
                    roman = roman_map.get(pg_match.group(1))
                    if roman:
                        dg.packing_group = f"PG {roman}"
            # Flash Point temperature sign preservation
            if dg.flash_point and dg.flash_point.temperature is not None:
                # Ensure negative values survive roundtrip
                dg.flash_point.temperature = float(dg.flash_point.temperature)


def _validate_vkn_format(party_id: Optional[str]) -> Optional[str]:
    """Validate and clean Turkish VKN (Vergi Kimlik Numarasi) format.

    VKN must be exactly 10 digits. Returns cleaned VKN or None if invalid.
    """
    if not party_id:
        return None
    digits = re.sub(r"\D", "", party_id.strip())
    if len(digits) == 10 and digits != "0000000000":
        return digits
    return None


_REC21_PACKAGING_MAP = {
    "PALLET": "PL", "PALLETS": "PL", "PLT": "PL", "PAL": "PL", "PL": "PL",
    "CARTON": "CT", "CARTONS": "CT", "CTN": "CT", "CTNS": "CT", "CT": "CT",
    "BOX": "BX", "BOXES": "BX", "BX": "BX",
    "CRATE": "CR", "CRATES": "CR", "CR": "CR",
    "DRUM": "DR", "DRUMS": "DR", "DR": "DR",
    "BAG": "BG", "BAGS": "BG", "BG": "BG",
    "BALE": "BA", "BALES": "BA", "BA": "BA",
    "PIECE": "PC", "PIECES": "PC", "PCS": "PC", "PC": "PC",
    "PACKAGE": "PK", "PACKAGES": "PK", "PKGS": "PK", "PK": "PK",
    "BUNDLE": "BE", "BUNDLES": "BE", "BE": "BE",
    "ROLL": "RO", "ROLLS": "RO", "RO": "RO",
    "CAN": "CA", "CANS": "CA", "CA": "CA",
    "BOTTLE": "BO", "BOTTLES": "BO", "BO": "BO",
    "BUCKET": "BJ", "BUCKETS": "BJ", "BJ": "BJ",
    "CYLINDER": "CY", "CYLINDERS": "CY", "CY": "CY",
    "BARREL": "BA", "BARRELS": "BA",
    "IBC": "IBC", "TOTE": "IBC",
    "LOOSE": "NE", "BULK": "NE",
}

_NESTED_PACKAGING_PATTERN = re.compile(
    r"(?P<outer_qty>\d+)\s+(?P<outer_kind>PALLETS?|PALLET|CRATES?|CRATE|DRUMS?|DRUM|BUNDLES?|BUNDLE)\s+"
    r"CONTAINING\s+(?P<inner_qty>\d+)\s+(?P<inner_kind>CARTONS?|CARTON|BOXES?|BOX|BAGS?|BAG|DRUMS?|DRUM|PIECES?|PIECE|PACKAGES?|PACKAGE)",
    re.IGNORECASE,
)

_DCSA_LABELS = frozenset({
    "SHIPPING INSTRUCTION", "SHIPPING INSTRUCTION REFERENCE", "CARRIER BOOKING REFERENCE",
    "CONSIGNEE", "SHIPPER", "NOTIFY PARTY", "PORT OF LOADING", "PORT OF DISCHARGE",
    "PLACE OF RECEIPT", "PLACE OF DELIVERY", "GROSS WEIGHT", "NET WEIGHT",
    "FREIGHT PREPAID", "FREIGHT COLLECT", "BILL OF LADING", "SEA WAYBILL",
    "CONTAINER", "SEAL", "VESSEL", "VOYAGE", "IMO", "ISSUE DATE", "DATE",
    "BOOKING", "REFERENCE", "DESCRIPTION OF GOODS", "SHIPPING MARKS",
    "PACKAGE QUANTITY", "COMMODITY CODE", "HS CODE", "VOLUME",
    "TEMPERATURE", "VENTILATION", "HUMIDITY",
})

_DCSA_LABEL_WORDS = frozenset(
    word for label in _DCSA_LABELS for word in label.split()
)

_DCSA_LABEL_WORDS_BY_LEN: dict[int, frozenset[str]] = {}
for word in _DCSA_LABEL_WORDS:
    _DCSA_LABEL_WORDS_BY_LEN.setdefault(len(word), frozenset()).union({word})
_DCSA_LABEL_WORDS_BY_LEN = {k: frozenset(v) for k, v in _DCSA_LABEL_WORDS_BY_LEN.items()}

_DANGEROUS_GOODS_UN_PATTERN = re.compile(r"UN\s*(?P<un>\d{4})", re.IGNORECASE)
_DANGEROUS_GOODS_CLASS_PATTERN = re.compile(
    r"(?:IMDG\s+)?CLASS\s*(?P<cls>\d(?:\.\d)?)", re.IGNORECASE,
)
_DANGEROUS_GOODS_PG_PATTERN = re.compile(
    r"(?:PACKING\s+GROUP|PG)\s*(?P<pg>I{1,3}|IV|V|[1-5])", re.IGNORECASE,
)
_REEFER_TEMP_PATTERN = re.compile(
    r"(?P<sign>\-|MINUS|NEG(?:ATIVE)?)?\s*(?P<temp>\d+(?:\.\d+)?)\s*"
    r"(?:°\s*)?(?:DEGREES?\s*)?(?P<unit>C|CEL|CELSIUS|F|FAH|FAHRENHEIT)",
    re.IGNORECASE,
)


def _normalize_packaging_codes(normalized: ShippingInstruction) -> None:
    for cargo_item in normalized.cargo_items:
        if cargo_item.package_kind_code is None:
            continue
        from app.models import PackageKindCode
        if isinstance(cargo_item.package_kind_code, PackageKindCode):
            continue
        try:
            raw = str(cargo_item.package_kind_code).strip().upper()
            cargo_item.package_kind_code = PackageKindCode(raw)
        except ValueError:
            pass


def _resolve_nested_packaging(normalized: ShippingInstruction, ocr_text: str) -> None:
    for match in _NESTED_PACKAGING_PATTERN.finditer(ocr_text):
        outer_qty = int(match.group("outer_qty"))
        outer_kind = match.group("outer_kind").upper()
        inner_qty = int(match.group("inner_qty"))
        inner_kind = match.group("inner_kind").upper()
        outer_code = _REC21_PACKAGING_MAP.get(outer_kind, outer_kind)
        inner_code = _REC21_PACKAGING_MAP.get(inner_kind, inner_kind)
        for cargo_item in normalized.cargo_items:
            if cargo_item.package_quantity == outer_qty and cargo_item.package_kind_code in (outer_code, outer_kind, None):
                from app.models import PackageKindCode
                cargo_item.package_quantity = inner_qty
                try:
                    cargo_item.package_kind_code = PackageKindCode(inner_code)
                except ValueError:
                    pass
                break


def _extract_dangerous_goods_from_ocr(normalized: ShippingInstruction, ocr_text: str) -> None:
    for cargo_item in normalized.cargo_items:
        desc = cargo_item.description_of_goods or ""
        cargo_text = ocr_text
        if desc:
            idx = ocr_text.casefold().find(desc.casefold()[:20])
            if idx >= 0:
                window = 500
                cargo_text = ocr_text[max(0, idx - window):idx + len(desc) + window]
        un_match = _DANGEROUS_GOODS_UN_PATTERN.search(cargo_text)
        cls_match = _DANGEROUS_GOODS_CLASS_PATTERN.search(cargo_text)
        pg_match = _DANGEROUS_GOODS_PG_PATTERN.search(cargo_text)
        has_dangerous = un_match or cls_match or pg_match
        if not has_dangerous:
            continue
        if cargo_item.dangerous_goods_list is None:
            from app.models import DangerousGoods
            cargo_item.dangerous_goods_list = [DangerousGoods()]
        dg = cargo_item.dangerous_goods_list[0]
        if un_match and dg.un_number is None:
            dg.un_number = f"UN {un_match.group('un')}"
        if cls_match and dg.imdg_class is None:
            dg.imdg_class = f"Class {cls_match.group('cls')}"
        if pg_match and dg.packing_group is None:
            roman_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
            pg_val = pg_match.group("pg").upper()
            pg_val = roman_map.get(pg_val, pg_val)
            if not pg_val.startswith("PG "):
                pg_val = f"PG {pg_val}"
            dg.packing_group = pg_val


def _normalize_reefer_temperatures(normalized: ShippingInstruction, ocr_text: str) -> None:
    temp_matches = list(_REEFER_TEMP_PATTERN.finditer(ocr_text))
    if not temp_matches:
        return
    temp_remarks_parts = []
    for match in temp_matches:
        sign = match.group("sign")
        temp_val = float(match.group("temp"))
        unit_raw = match.group("unit").upper()
        if sign and sign.strip() in ("-", "MINUS", "NEG", "NEGATIVE"):
            temp_val = -temp_val
        unit_map = {"CELSIUS": "CEL", "C": "CEL", "FAHRENHEIT": "FAH", "F": "FAH"}
        unit = unit_map.get(unit_raw, "CEL")
        temp_remarks_parts.append(f"TEMP:{temp_val}{unit}")
    if temp_remarks_parts and not normalized.remarks:
        normalized.remarks = "REEFER SETTINGS: " + ", ".join(temp_remarks_parts)
    elif temp_remarks_parts and "REEFER" not in (normalized.remarks or "").upper():
        normalized.remarks = (normalized.remarks or "") + " | REEFER SETTINGS: " + ", ".join(temp_remarks_parts)


def _levenshtein_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein_distance(b, a)
    if len(b) == 0:
        return len(a)
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a):
        current_row = [i + 1]
        for j, char_b in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (0 if char_a == char_b else 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _fuzzy_correct_dcsa_labels(text: str, max_distance: int = 2) -> str:
    words = text.split()
    corrected = []
    for word in words:
        word_upper = word.upper()
        if word_upper in _DCSA_LABEL_WORDS or len(word_upper) < 3:
            corrected.append(word)
            continue
        best_match = word
        best_distance = max_distance + 1
        candidates = set()
        for delta in (-2, -1, 0, 1, 2):
            candidates.update(_DCSA_LABEL_WORDS_BY_LEN.get(len(word_upper) + delta, frozenset()))
        for label_word in candidates:
            dist = _levenshtein_distance(word_upper, label_word)
            if dist < best_distance and dist <= max_distance:
                best_distance = dist
                best_match = label_word
        corrected.append(best_match)
    return " ".join(corrected)


def _apply_utf8_normalization(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    try:
        from ftfy import fix_text
        normalized = fix_text(normalized)
    except ImportError:
        pass
    return normalized


_KNOWN_ISO_CODES = frozenset({
    "22G1", "42G1", "45G1", "L5G1", "22R1", "42R1", "45R1",
    "22U1", "42U1", "22P1", "42P1", "22T1", "42T1",
})

_KNOWN_PACKAGE_CODES = frozenset(_REC21_PACKAGING_MAP.values())

_KNOWN_FREIGHT_TERMS = frozenset({"PPD", "COL"})

_KNOWN_TRANSPORT_DOCS = frozenset({"B/L", "SWB"})


def _fuzzy_correct_enum_fields(normalized: ShippingInstruction, max_distance: int = 1) -> None:
    for equipment in normalized.equipment_list:
        if equipment.iso_equipment_code is not None:
            code = equipment.iso_equipment_code.strip().upper()
            if code not in _KNOWN_ISO_CODES and len(code) >= 3:
                best = None
                best_dist = max_distance + 1
                for known in _KNOWN_ISO_CODES:
                    if abs(len(code) - len(known)) > max_distance:
                        continue
                    dist = _levenshtein_distance(code, known)
                    if dist < best_dist:
                        best_dist = dist
                        best = known
                if best is not None and best_dist <= max_distance:
                    equipment.iso_equipment_code = best
    for cargo_item in normalized.cargo_items:
        if cargo_item.package_kind_code is not None:
            code = cargo_item.package_kind_code.strip().upper()
            if code not in _KNOWN_PACKAGE_CODES and len(code) >= 2:
                best = None
                best_dist = max_distance + 1
                for known in _KNOWN_PACKAGE_CODES:
                    if abs(len(code) - len(known)) > max_distance:
                        continue
                    dist = _levenshtein_distance(code, known)
                    if dist < best_dist:
                        best_dist = dist
                        best = known
                if best is not None and best_dist <= max_distance:
                    cargo_item.package_kind_code = best
    if normalized.freight_payment_term_code is not None:
        code = normalized.freight_payment_term_code.strip().upper()
        if code not in _KNOWN_FREIGHT_TERMS and len(code) >= 2:
            best = None
            best_dist = max_distance + 1
            for known in _KNOWN_FREIGHT_TERMS:
                dist = _levenshtein_distance(code, known)
                if dist < best_dist and dist <= max_distance:
                    best_dist = dist
                    best = known
            if best is not None:
                mapped = FreightPaymentTermCode.PREPAID if best == "PPD" else FreightPaymentTermCode.COLLECT
                normalized.freight_payment_term_code = mapped
    if normalized.transport_document_type is not None:
        code = normalized.transport_document_type.strip().upper()
        if code not in _KNOWN_TRANSPORT_DOCS and len(code) >= 2:
            best = None
            best_dist = max_distance + 1
            for known in _KNOWN_TRANSPORT_DOCS:
                dist = _levenshtein_distance(code, known)
                if dist < best_dist and dist <= max_distance:
                    best_dist = dist
                    best = known
            if best is not None:
                normalized.transport_document_type = (
                    TransportDocumentType.BILL_OF_LADING if best == "B/L"
                    else TransportDocumentType.SEA_WAYBILL
                )


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
    # Party ID basindaki etiket on eklerini temizle (V.NO:, VKN:, TAX ID: vb.)
    for party in normalized.parties:
        if party.party_id:
            cleaned = re.sub(
                r"(?i)^\s*(?:V\.?\s*NO\.?\s*[:#\-]?|VKN\s*[:#\-]?|VERGI\s*NO\.?\s*[:#\-]?|TAX\s*ID\s*[:#\-]?|VAT\s*NO\.?\s*[:#\-]?)\s*",
                "",
                party.party_id.strip(),
            )
            if cleaned and cleaned != party.party_id.strip():
                party.party_id = cleaned.strip()
            # Validate VKN format (10-digit) for Turkish parties
            vkn_validated = _validate_vkn_format(party.party_id)
            if vkn_validated is not None:
                party.party_id = vkn_validated
            else:
                # Check if party_id looks like a VKN but invalid format
                digits_only = re.sub(r"\D", "", party.party_id.strip())
                if 9 <= len(digits_only) <= 11 and digits_only != party.party_id.strip():
                    # Keep the original if it contains non-digit separators
                    pass
                elif len(digits_only) == 10:
                    party.party_id = digits_only
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
    _deduplicate_bl_document_references(normalized)
    for plan in normalized.transport_plans:
        _clean_location_name(plan.port_of_loading)
        _clean_location_name(plan.port_of_discharge)
        _clean_location_name(plan.place_of_receipt)
        _clean_location_name(plan.place_of_delivery)
    brut_value = _extract_labeled_value(
        ocr_text,
        (
            r"(?im)(?:BRUT|GROSS\s+WEIGHT|GROSS|G\.W\.|GW|G\.W)\s*[:#\-]?\s*(?:WEIGHT|AGIRLIK|WT\.?)?\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:\.[\d]{3})*(?:,[\d]+)?)",
            r"(?im)(?:BRUT|GROSS\s+WEIGHT|GROSS|G\.W\.|GW|G\.W)\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:,[\d]{3})*(?:\.[\d]+)?)",
        ),
    )
    net_value = _extract_labeled_value(
        ocr_text,
        (
            r"(?im)(?:NET|NET\s+WEIGHT|N\.W\.|NW|N\.W)\s*[:#\-]?\s*(?:WEIGHT|AGIRLIK|WT\.?)?\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:\.[\d]{3})*(?:,[\d]+)?)",
            r"(?im)(?:NET|NET\s+WEIGHT|N\.W\.|NW|N\.W)\s*[:#\-]?\s*(?P<value>[\d]{1,3}(?:,[\d]{3})*(?:\.[\d]+)?)",
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
    _normalize_dangerous_goods(normalized, ocr_text)
    _normalize_packaging_codes(normalized)
    _fuzzy_correct_enum_fields(normalized, max_distance=1)
    _normalize_reefer_temperatures(normalized, ocr_text)
    # Transport Document Type: OCR'da KONSIMENTO / BILL OF LADING -> B/L
    if normalized.transport_document_type is None and ocr_text:
        if re.search(
            r"(?i)(?:KONSIMENTO|KONŞİMENTO|BILL\s+OF\s+LOADING|B/L|B\s*/\s*L)\b",
            ocr_text,
        ):
            normalized.transport_document_type = TransportDocumentType.BILL_OF_LADING
        elif re.search(r"(?i)(?:SEA\s+WAYBILL|SWB|DENIZ\s+KONŞİMENTOSU)\b", ocr_text):
            normalized.transport_document_type = TransportDocumentType.SEA_WAYBILL
    # Freight Payment Term: OCR'da NAVLUN ALICIYA AIT / FREIGHT COLLECT -> COL
    if normalized.freight_payment_term_code is None and ocr_text:
        if re.search(
            r"(?i)(?:NAVLUN\s+ALICIYA\s+AİTTİR|NAVLUN\s+ALICIYA\s+AIT|FREIGHT\s+COLLECT|NAVLUN\s+TOPLANACAK|COLLECT)"
            r"|ALICI\s+ÖDEMELİ",
            ocr_text,
        ):
            normalized.freight_payment_term_code = FreightPaymentTermCode.COLLECT
        elif re.search(
            r"(?i)(?:NAVLUN\s+ÖDENMİŞTİR|FREIGHT\s+PREPAID|PREPAID|ÖDENMİŞ\s+NAVLUN)",
            ocr_text,
        ):
            normalized.freight_payment_term_code = FreightPaymentTermCode.PREPAID
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


def _normalize_raw_inference_output(
    raw_output: str,
    ocr_text: str,
) -> ShippingInstruction:
    try:
        parsed_instruction = parse_llm_output(raw_output)
    except Exception:
        cleaned = _extract_json(raw_output)
        data = _parse_json_with_fallback(cleaned)
        parsed_instruction = ShippingInstruction.model_validate(data)
    return normalize_extracted_instruction(parsed_instruction, ocr_text)


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
    try:
        raw_output = run_guided_inference(
            ocr_text,
            document_language,
            output_language,
            use_adapter=True,
        )
        return _normalize_raw_inference_output(raw_output, ocr_text), raw_output
    except Exception as adapter_error:
        if not _qwen_adapter_runtime_enabled():
            raise
        logger.warning(
            "Qwen adapter inference failed, retrying with base model: %s",
            adapter_error,
        )
        reset_llm_pipeline()
        try:
            base_raw_output = run_guided_inference(
                ocr_text,
                document_language,
                output_language,
                use_adapter=False,
            )
            return (
                _normalize_raw_inference_output(base_raw_output, ocr_text),
                base_raw_output,
            )
        except Exception as base_error:
            raise base_error from adapter_error
        finally:
            reset_llm_pipeline()


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
