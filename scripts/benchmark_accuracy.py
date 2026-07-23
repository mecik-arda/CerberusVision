from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm.evaluation import (
    aggregate_evaluations,
    evaluate_expected_fields,
    flatten_values,
)
from app.config import settings
from app.llm import inference as inference_module
from app.llm.inference import run_inference_with_fallback
from app.ocr.spatial_ocr import (
    process_pdf_with_region_ocr,
    process_pdf_with_spatial_ocr,
)
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import validate_xml_against_xsd

FIELD_CATEGORIES = {
    "parties": re.compile(r"^parties"),
    "transport_plans": re.compile(r"^transport_plans"),
    "equipment_list": re.compile(r"^equipment_list"),
    "cargo_items": re.compile(r"^cargo_items"),
    "document_info": re.compile(
        r"^(shipping_instruction_reference|carrier_booking_reference|"
        r"shipping_instruction_date_time|issue_date|place_of_issue|"
        r"export_declaration_number|service_contract_reference|"
        r"transport_document_type|freight_payment_term_code|"
        r"document_status_code|document_references|customs_information|remarks)"
    ),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_json_sha256(value: Any) -> str:
    return _sha256_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _artifact_manifest(path_value: str) -> Dict[str, Any]:
    if not path_value.strip():
        return {
            "path": None,
            "exists": False,
            "manifest_sha256": None,
        }
    artifact_path = Path(path_value).expanduser()
    if not artifact_path.exists():
        return {
            "path": str(artifact_path),
            "exists": False,
            "manifest_sha256": None,
        }
    artifact_files = (
        [artifact_path]
        if artifact_path.is_file()
        else sorted(path for path in artifact_path.rglob("*") if path.is_file())
    )
    entries = [
        {
            "path": (
                path.name
                if artifact_path.is_file()
                else str(path.relative_to(artifact_path))
            ),
            "size": path.stat().st_size,
        }
        for path in artifact_files
    ]
    return {
        "path": str(artifact_path.resolve()),
        "exists": True,
        "file_count": len(entries),
        "manifest_sha256": _canonical_json_sha256(entries),
    }


def _benchmark_provenance() -> Dict[str, Any]:
    prompt_payload = {
        "system_prompt": inference_module._system_prompt,
        "stage_prompts": inference_module._STAGE_PROMPTS,
        "build_prompt_source": inspect.getsource(
            inference_module.build_prompt
        ),
        "build_stage_prompt_source": inspect.getsource(
            inference_module.build_stage_prompt
        ),
    }
    generation_payload = {
        "do_sample": False,
        "max_new_tokens": settings.model.max_new_tokens,
        "num_streams": 1,
        "pipeline_reset_between_repeats": True,
        "structured_schema_sha256": _canonical_json_sha256(
            inference_module.get_json_schema()
        ),
        "inference_mode": settings.inference_mode,
    }
    return {
        "llm_model": _artifact_manifest(settings.model.model_path),
        "llm_adapter": {
            "path": None,
            "exists": False,
            "runtime_mode": "merged_openvino_model",
        },
        "layout_adapter": _artifact_manifest(
            settings.lora_adapter_path
        ),
        "layout_lora_enabled": settings.lora_enabled,
        "prompt_sha256": _canonical_json_sha256(prompt_payload),
        "generation_config": generation_payload,
        "generation_config_sha256": _canonical_json_sha256(
            generation_payload
        ),
    }


def _load_frozen_ocr(
    fixture_path_value: str,
    expected_sha256: Optional[str],
) -> Tuple[str, Optional[Tuple[str, str, str]], str]:
    fixture_path = (PROJECT_ROOT / fixture_path_value).resolve()
    fixture_bytes = fixture_path.read_bytes()
    actual_sha256 = _sha256_bytes(fixture_bytes)
    if expected_sha256 and expected_sha256 != actual_sha256:
        raise ValueError(
            f"Frozen OCR hash mismatch: expected={expected_sha256} "
            f"actual={actual_sha256} path={fixture_path}"
        )
    payload = json.loads(fixture_bytes.decode("utf-8"))
    upper = str(payload.get("upper", ""))
    middle = str(payload.get("middle", ""))
    lower = str(payload.get("lower", ""))
    full_text = str(payload.get("full", ""))
    if not full_text:
        full_text = (
            f"{upper}\n\n--- ORTA BOLGE ---\n\n{middle}"
            f"\n\n--- ALT BOLGE ---\n\n{lower}"
        )
    segmented_ocr = (
        (upper, middle, lower)
        if any(value.strip() for value in (upper, middle, lower))
        else None
    )
    if not full_text.strip():
        raise ValueError(f"Frozen OCR fixture is empty: {fixture_path}")
    return full_text, segmented_ocr, actual_sha256


def _classify_field(path: str) -> str:
    for category, pattern in FIELD_CATEGORIES.items():
        if pattern.match(path):
            return category
    return "other"


@dataclass
class CategoryStats:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    total: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return round((self.correct / self.total * 100.0) if self.total else 100.0, 2)

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return round((self.tp / denom * 100.0) if denom else 100.0, 2)

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return round((self.tp / denom * 100.0) if denom else 100.0, 2)

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        return round((2 * p * r / (p + r)) if (p + r) else 0.0, 2)


def _load_benchmark_cases(dataset_dir: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for json_path in sorted(dataset_dir.glob("*.json")):
        case = json.loads(json_path.read_text(encoding="utf-8"))
        case["_source_path"] = str(json_path)
        if "case_name" not in case:
            case["case_name"] = json_path.stem
        cases.append(case)
    if not cases:
        raise SystemExit(f"Benchmark dosyasi bulunamadi: {dataset_dir}")
    return cases


def _extract_ocr_text(pdf_path: Path, lang: str) -> Tuple[str, Optional[Tuple[str, str, str]]]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF bulunamadi: {pdf_path}")
    upper, middle, lower, _boxes = process_pdf_with_region_ocr(pdf_path, lang=lang)
    full_text = (
        f"{upper}\n\n--- ORTA BOLGE ---\n\n{middle}"
        f"\n\n--- ALT BOLGE ---\n\n{lower}"
    )
    return full_text, (upper, middle, lower)


def _extract_expected_from_xml(xml_path: Path) -> Dict[str, Any]:
    from lxml import etree

    doc = etree.parse(str(xml_path))
    root = doc.getroot()
    nsmap = {"dcsa": "http://dcsa.org/schemas/si/v2"}

    def _text(parent, tag: str) -> Optional[str]:
        el = parent.find(f"dcsa:{tag}", nsmap)
        return el.text.strip() if el is not None and el.text else None

    def _location(parent, tag: str) -> Optional[Dict[str, Any]]:
        el = parent.find(f"dcsa:{tag}", nsmap)
        if el is None:
            return None
        loc: Dict[str, Any] = {}
        code = _text(el, "UNLocationCode")
        name = _text(el, "LocationName")
        if code:
            loc["un_location_code"] = code
        if name:
            loc["location_name"] = name
        return loc if loc else None

    expected: Dict[str, Any] = {}
    expected["shipping_instruction_reference"] = _text(root, "ShippingInstructionReference")
    expected["document_status_code"] = _text(root, "DocumentStatusCode")
    expected["carrier_booking_reference"] = _text(root, "CarrierBookingReference")
    expected["transport_document_type"] = _text(root, "TransportDocumentType")
    expected["freight_payment_term_code"] = _text(root, "FreightPaymentTermCode")
    expected["issue_date"] = _text(root, "IssueDate")
    expected["export_declaration_number"] = _text(root, "ExportDeclarationNumber")
    expected["service_contract_reference"] = _text(root, "ServiceContractReference")
    expected["remarks"] = _text(root, "Remarks")

    issue_place = root.find("dcsa:PlaceOfIssue", nsmap)
    if issue_place is not None:
        expected["place_of_issue"] = _location(issue_place, ".")

    parties_el = root.find("dcsa:Parties", nsmap)
    if parties_el is not None:
        parties: List[Dict[str, Any]] = []
        for party_el in parties_el.findall("dcsa:Party", nsmap):
            party: Dict[str, Any] = {}
            party["party_role_code"] = _text(party_el, "PartyRoleCode")
            party["party_name"] = _text(party_el, "PartyName")
            party["party_id"] = _text(party_el, "PartyID")
            addr_el = party_el.find("dcsa:Address", nsmap)
            if addr_el is not None:
                party["address"] = {
                    "street": _text(addr_el, "Street"),
                    "city": _text(addr_el, "City"),
                    "postal_code": _text(addr_el, "PostalCode"),
                    "country_code": _text(addr_el, "CountryCode"),
                }
            contact_el = party_el.find("dcsa:ContactDetails", nsmap)
            if contact_el is not None:
                party["contact_details"] = {
                    "name": _text(contact_el, "Name"),
                    "email": _text(contact_el, "Email"),
                    "phone_number": _text(contact_el, "PhoneNumber"),
                }
            parties.append(party)
        if parties:
            expected["parties"] = parties

    plans_el = root.find("dcsa:TransportPlans", nsmap)
    if plans_el is not None:
        plans: List[Dict[str, Any]] = []
        for plan_el in plans_el.findall("dcsa:TransportPlan", nsmap):
            plan: Dict[str, Any] = {}
            plan["transport_mode"] = _text(plan_el, "TransportMode")
            plan["carrier_voyage_number"] = _text(plan_el, "CarrierVoyageNumber")
            plan["vessel_imo_number"] = _text(plan_el, "VesselIMONumber")
            plan["port_of_loading"] = _location(plan_el, "PortOfLoading")
            plan["port_of_discharge"] = _location(plan_el, "PortOfDischarge")
            plan["place_of_receipt"] = _location(plan_el, "PlaceOfReceipt")
            plan["place_of_delivery"] = _location(plan_el, "PlaceOfDelivery")
            plans.append(plan)
        if plans:
            expected["transport_plans"] = plans

    equipment_el = root.find("dcsa:EquipmentList", nsmap)
    if equipment_el is not None:
        equipment_list: List[Dict[str, Any]] = []
        for eq_el in equipment_el.findall("dcsa:Equipment", nsmap):
            eq: Dict[str, Any] = {}
            eq["equipment_reference"] = _text(eq_el, "EquipmentReference")
            eq["iso_equipment_code"] = _text(eq_el, "ISOEquipmentCode")
            eq["is_shipper_owned"] = _text(eq_el, "IsShipperOwned")
            gw_el = eq_el.find("dcsa:CargoGrossWeight", nsmap)
            if gw_el is not None:
                eq["cargo_gross_weight"] = {
                    "weight": float(gw_el.find("dcsa:Weight", nsmap).text)
                    if gw_el.find("dcsa:Weight", nsmap) is not None
                    else None,
                    "unit": _text(gw_el, "Unit"),
                }
            seals: List[Dict[str, Any]] = []
            seals_el = eq_el.find("dcsa:Seals", nsmap)
            if seals_el is not None:
                for seal_el in seals_el.findall("dcsa:Seal", nsmap):
                    seals.append({"seal_number": _text(seal_el, "SealNumber")})
            if seals:
                eq["seals"] = seals
            equipment_list.append(eq)
        if equipment_list:
            expected["equipment_list"] = equipment_list

    cargo_el = root.find("dcsa:CargoItems", nsmap)
    if cargo_el is not None:
        items: List[Dict[str, Any]] = []
        for item_el in cargo_el.findall("dcsa:CargoItem", nsmap):
            item: Dict[str, Any] = {}
            item["package_quantity"] = (
                int(qty) if (qty := _text(item_el, "PackageQuantity")) else None
            )
            item["package_kind_code"] = _text(item_el, "PackageKindCode")
            item["description_of_goods"] = _text(item_el, "DescriptionOfGoods")
            item["shipping_marks"] = _text(item_el, "ShippingMarks")
            item["commodity_code"] = _text(item_el, "CommodityCode")
            weight_el = item_el.find("dcsa:Weight", nsmap)
            if weight_el is not None:
                item["weight"] = {
                    "weight_value": (
                        float(wv) if (wv := _text(weight_el, "WeightValue")) else None
                    ),
                    "unit": _text(weight_el, "Unit"),
                }
            volume_el = item_el.find("dcsa:Volume", nsmap)
            if volume_el is not None:
                item["volume"] = {
                    "volume_value": (
                        float(vv) if (vv := _text(volume_el, "VolumeValue")) else None
                    ),
                    "unit": _text(volume_el, "Unit"),
                }
            items.append(item)
        if items:
            expected["cargo_items"] = items

    customs_el = root.find("dcsa:CustomsInformation", nsmap)
    if customs_el is not None:
        expected["customs_information"] = {
            "fta_declaration": _text(customs_el, "FTADeclaration"),
            "export_customs_clearance_location": _text(
                customs_el, "ExportCustomsClearanceLocation"
            ),
        }

    return expected


def _flatten_ground_truth(expected: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in expected.items():
        if value is None:
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if isinstance(value, dict) and len(value) == 0:
            continue
        clean[key] = value
    return flatten_values(clean)


def _compute_category_stats(
    all_results: List[Dict[str, Any]],
) -> Dict[str, CategoryStats]:
    categories: Dict[str, CategoryStats] = {
        name: CategoryStats() for name in FIELD_CATEGORIES
    }
    for result in all_results:
        for cat_name in FIELD_CATEGORIES:
            stats = categories[cat_name]
            field_metrics = result.get("category_metrics", {}).get(cat_name, {})
            stats.tp += field_metrics.get("tp", 0)
            stats.fp += field_metrics.get("fp", 0)
            stats.fn += field_metrics.get("fn", 0)
            stats.total += field_metrics.get("total", 0)
            stats.correct += field_metrics.get("correct", 0)
    return categories


def _compute_precision_recall(
    expected_fields: Dict[str, Any],
    actual_fields: Dict[str, Any],
    evaluation: Dict[str, Any],
) -> Dict[str, Dict[str, int]]:
    category_metrics: Dict[str, Dict[str, int]] = {}
    for cat_name in FIELD_CATEGORIES:
        expected_cat = {p: v for p, v in expected_fields.items() if _classify_field(p) == cat_name}
        actual_cat = {p: v for p, v in actual_fields.items() if _classify_field(p) == cat_name}
        expected_set = set(expected_cat.keys())
        actual_non_null = {p for p, v in actual_cat.items() if v is not None and v != "" and v is not False}
        correct_set = set(evaluation.get("correct_fields", []))
        cat_correct = correct_set & expected_set
        tp = len(cat_correct)
        fp = len(actual_non_null - expected_set)
        fn = len(expected_set - actual_non_null)
        total = len(expected_cat)
        correct = len(cat_correct)
        category_metrics[cat_name] = {
            "tp": tp, "fp": fp, "fn": fn,
            "total": total, "correct": correct,
        }
    return category_metrics


def _format_percent(value: float) -> str:
    if value >= 90:
        return f"\033[32m%{value:.1f}\033[0m"
    elif value >= 70:
        return f"\033[33m%{value:.1f}\033[0m"
    else:
        return f"\033[31m%{value:.1f}\033[0m"


def _print_report(
    all_results: List[Dict[str, Any]],
    category_stats: Dict[str, CategoryStats],
    total_time: float,
) -> None:
    overall = aggregate_evaluations(all_results)
    print()
    print("=" * 72)
    print("  CERBERUSVISION BENCHMARK RAPORU")
    print("=" * 72)
    print(f"  Belge sayisi:      {overall['documents']}")
    print(f"  Toplam alan:       {overall['total_fields']}")
    print(f"  Dogru alan:        {overall['correct_fields']}")
    print(f"  Eksik alan:        {overall['missing_fields']}")
    print(f"  Hatali alan:       {overall['mismatched_fields']}")
    print(f"  Toplam sure:       {total_time:.1f}s")
    print()

    cat_labels = {
        "document_info": "Belge Bilgileri & Referanslar",
        "parties": "Taraflar (Shipper/Consignee/Notify)",
        "transport_plans": "Lojistik & Tasima (POL/POD/Gemi)",
        "equipment_list": "Konteyner & Ekipman",
        "cargo_items": "Yuk Kalemleri & Mallar",
        "other": "Diger",
    }

    print("-" * 72)
    print(f"  {'Kategori':<36} {'Dogruluk':>8}  {'Kesinlik':>8}  {'GeriCagr':>8}  {'F1-Skor':>8}")
    print("-" * 72)
    for cat_name in ["document_info", "parties", "transport_plans", "equipment_list", "cargo_items"]:
        stats = category_stats[cat_name]
        label = cat_labels.get(cat_name, cat_name)
        print(
            f"  {label:<36}"
            f"  {_format_percent(stats.accuracy):>14}"
            f"  {_format_percent(stats.precision):>14}"
            f"  {_format_percent(stats.recall):>13}"
            f"  {_format_percent(stats.f1):>13}"
        )
    print("-" * 72)
    overall_cat = CategoryStats(
        tp=sum(s.tp for s in category_stats.values()),
        fp=sum(s.fp for s in category_stats.values()),
        fn=sum(s.fn for s in category_stats.values()),
        total=sum(s.total for s in category_stats.values()),
        correct=sum(s.correct for s in category_stats.values()),
    )
    print(
        f"  {'GENEL TOPLAM':<36}"
        f"  {_format_percent(overall_cat.accuracy):>14}"
        f"  {_format_percent(overall_cat.precision):>14}"
        f"  {_format_percent(overall_cat.recall):>13}"
        f"  {_format_percent(overall_cat.f1):>13}"
    )
    print("=" * 72)

    print()
    print("  Belge Bazli Sonuclar:")
    print("-" * 88)
    print(f"  {'Belge':<28} {'Alan':>5} {'Dogru':>5} {'Eksik':>5} {'Hata':>5} {'%Dog':>7} {'XSD':>6}")
    print("-" * 88)
    for idx, result in enumerate(all_results):
        name = result.get("case_name", f"Belge {idx+1}")
        if len(name) > 26:
            name = name[:23] + "..."
        xsd_status = "GECTI" if result.get("xsd_valid") else f"HATA({result.get('xsd_error_count', 0)})"
        print(
            f"  {name:<28}"
            f" {result['total_fields']:>5}"
            f" {len(result['correct_fields']):>5}"
            f" {len(result['missing_fields']):>5}"
            f" {len(result['mismatched_fields']):>5}"
            f" {_format_percent(result['accuracy'])}"
            f" {xsd_status:>6}"
        )
    print("-" * 88)
    print()


def _sort_arrays_by_key(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if key == "parties" and isinstance(value, list) and len(value) > 1:
            role_order = {"CZ": 0, "CN": 1, "N1": 2, "FW": 3, "SHI": 0, "CON": 1, "NTF": 2}
            result[key] = sorted(
                value,
                key=lambda p: role_order.get(
                    str(p.get("party_role_code", "")), 99
                ),
            )
        elif key == "equipment_list" and isinstance(value, list) and len(value) > 1:
            result[key] = sorted(
                value,
                key=lambda e: str(e.get("equipment_reference") or ""),
            )
        elif key == "transport_plans" and isinstance(value, list) and len(value) > 1:
            result[key] = sorted(
                value,
                key=lambda tp: int(tp.get("leg_sequence_number", 0) or 0),
            )
        elif isinstance(value, dict):
            result[key] = _sort_arrays_by_key(value)
        elif isinstance(value, list):
            result[key] = [
                _sort_arrays_by_key(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _prune_empty_objects(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            pruned = _prune_empty_objects(value)
            if any(
                v is not None and v != [] and v != {} and v != ""
                for v in pruned.values()
            ):
                result[key] = pruned
        elif isinstance(value, list):
            pruned_list = []
            for item in value:
                if isinstance(item, dict):
                    pruned_item = _prune_empty_objects(item)
                    if any(
                        v is not None and v != [] and v != {} and v != ""
                        for v in pruned_item.values()
                    ):
                        pruned_list.append(pruned_item)
                elif item is not None and item != "":
                    pruned_list.append(item)
            if pruned_list:
                result[key] = pruned_list
        elif value is not None and value != "" and value is not False:
            result[key] = value
    return result


def _evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case_name = case["case_name"]
    pdf_rel = case.get("pdf")
    ocr_text_raw = case.get("ocr_text")
    ocr_fixture = case.get("ocr_fixture")
    document_language = case.get("document_language", "en")
    output_language = case.get("output_language", "en")
    expected = case.get("expected")

    print(f"  [{case_name}] Isleniyor...", end=" ", flush=True)
    t_start = time.time()

    if ocr_fixture:
        full_ocr, segmented_ocr, ocr_sha256 = _load_frozen_ocr(
            str(ocr_fixture),
            case.get("ocr_sha256"),
        )
    elif ocr_text_raw:
        full_ocr = ocr_text_raw
        segmented_ocr = None
        ocr_sha256 = _sha256_text(full_ocr)
    elif pdf_rel:
        pdf_path = (PROJECT_ROOT / pdf_rel).resolve()
        if not pdf_path.exists():
            pdf_path = Path(pdf_rel)
        full_ocr, segmented_ocr = _extract_ocr_text(
            pdf_path,
            case.get("ocr_lang", "latin" if document_language == "tr" else "en"),
        )
        ocr_sha256 = _sha256_text(full_ocr)
    else:
        raise ValueError(
            f"'{case_name}': ocr_fixture, pdf veya ocr_text alani gerekli"
        )

    if expected is None and pdf_rel:
        xml_path = (PROJECT_ROOT / pdf_rel).with_suffix(".xml")
        if not xml_path.exists():
            raise FileNotFoundError(
                f"'{case_name}': expected alani bos ve ground-truth XML bulunamadi: {xml_path}"
            )
        expected = _extract_expected_from_xml(xml_path)

    if expected is None:
        raise ValueError(f"'{case_name}': expected alani gerekli")

    instruction, raw_output = run_inference_with_fallback(
        full_ocr, document_language, output_language, segmented_ocr,
    )
    actual = instruction.model_dump(mode="json")
    actual_sha256 = _canonical_json_sha256(actual)
    raw_output_sha256 = _sha256_text(raw_output)

    xml_str = shipping_instruction_to_xml(instruction)
    xsd_valid, xsd_errors = validate_xml_against_xsd(xml_str)

    expected_sorted = _sort_arrays_by_key(dict(expected))
    actual_sorted = _sort_arrays_by_key(dict(actual))
    expected_flat = _flatten_ground_truth(expected_sorted)
    actual_flat = flatten_values(actual_sorted)

    evaluation = evaluate_expected_fields(
        dict(expected_flat),
        dict(actual_flat),
    )
    category_metrics = _compute_precision_recall(
        expected_flat, actual_flat, evaluation,
    )

    elapsed = time.time() - t_start
    print(f"{elapsed:.1f}s (dogruluk: %{evaluation['accuracy']:.1f})")

    return {
        "case_name": case_name,
        "source_path": case.get("_source_path", ""),
        "elapsed_seconds": round(elapsed, 2),
        "ocr_sha256": ocr_sha256,
        "actual_sha256": actual_sha256,
        "raw_output_sha256": raw_output_sha256,
        "xsd_valid": xsd_valid,
        "xsd_error_count": len(xsd_errors),
        "xsd_errors": xsd_errors if not xsd_valid else [],
        "category_metrics": category_metrics,
        **evaluation,
    }


def main() -> int:
    os.environ["CERBERUS_BENCHMARK_DETERMINISTIC"] = "1"
    parser = argparse.ArgumentParser(
        description="CerberusVision Dogruluk Benchmark Suiti"
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path("tests/fixtures/qwen_benchmark"),
        help="Benchmark JSON dosyalarinin bulundugu dizin",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON raporunun kaydedilecegi dosya yolu",
    )
    parser.add_argument(
        "--html",
        type=Path,
        help="HTML raporunun kaydedilecegi dosya yolu",
    )
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help="Sadece PDF iceren testleri calistir",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Ayni donmus girdilerle deterministik tekrar sayisi",
    )
    args = parser.parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat en az 1 olmali")

    cases = _load_benchmark_cases(args.dataset)

    pdf_count = sum(1 for c in cases if c.get("pdf"))
    text_count = sum(1 for c in cases if c.get("ocr_text") and not c.get("pdf"))
    frozen_count = sum(1 for c in cases if c.get("ocr_fixture"))
    print(
        f"Benchmark veri seti: {len(cases)} vaka "
        f"({pdf_count} PDF, {text_count} salt metin, "
        f"{frozen_count} donmus OCR)"
    )
    print()

    if args.pdf_only:
        cases = [c for c in cases if c.get("pdf")]
        if not cases:
            raise SystemExit("--pdf-only ile calistirilabilir vaka bulunamadi")
        print(f"PDF filtresi sonrasi: {len(cases)} vaka")
        print()

    t_total = time.time()
    repeated_results: List[List[Dict[str, Any]]] = []
    for repeat_index in range(args.repeat):
        if args.repeat > 1:
            print(f"Deterministik tekrar {repeat_index + 1}/{args.repeat}")
        inference_module.reset_llm_pipeline()
        repeated_results.append([_evaluate_case(case) for case in cases])
    total_time = time.time() - t_total
    all_results = repeated_results[0]
    mismatches: List[Dict[str, Any]] = []
    for repeat_index, repeat_results in enumerate(
        repeated_results[1:],
        start=2,
    ):
        baseline_by_case = {
            result["case_name"]: result for result in all_results
        }
        for repeated_result in repeat_results:
            baseline_result = baseline_by_case[repeated_result["case_name"]]
            changed_hashes = [
                hash_name
                for hash_name in (
                    "ocr_sha256",
                    "actual_sha256",
                    "raw_output_sha256",
                )
                if repeated_result[hash_name] != baseline_result[hash_name]
            ]
            if changed_hashes:
                mismatches.append(
                    {
                        "repeat": repeat_index,
                        "case_name": repeated_result["case_name"],
                        "changed_hashes": changed_hashes,
                    }
                )

    category_stats = _compute_category_stats(all_results)
    _print_report(all_results, category_stats, total_time)

    aggregated = aggregate_evaluations(all_results)
    xsd_passed = sum(1 for r in all_results if r.get("xsd_valid"))
    xsd_failed = sum(1 for r in all_results if not r.get("xsd_valid"))
    output_payload = {
        "xsd_summary": {
            "total": len(all_results),
            "passed": xsd_passed,
            "failed": xsd_failed,
            "pass_rate_pct": round(xsd_passed / len(all_results) * 100, 1) if all_results else 0,
        },
        "benchmark_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_time_seconds": round(total_time, 2),
        "provenance": _benchmark_provenance(),
        "determinism": {
            "repeat_count": args.repeat,
            "passed": not mismatches,
            "mismatches": mismatches,
        },
        "category_breakdown": {
            cat_name: {
                "accuracy": stats.accuracy,
                "precision": stats.precision,
                "recall": stats.recall,
                "f1_score": stats.f1,
                "tp": stats.tp,
                "fp": stats.fp,
                "fn": stats.fn,
                "total_fields": stats.total,
                "correct_fields": stats.correct,
            }
            for cat_name, stats in category_stats.items()
        },
        **aggregated,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON raporu kaydedildi: {args.output}")

    if args.html:
        _write_html_report(output_payload, args.html)
        print(f"HTML raporu kaydedildi: {args.html}")

    if mismatches:
        raise SystemExit(
            f"Deterministik benchmark basarisiz: {len(mismatches)} uyusmazlik"
        )
    return 0


def _write_html_report(report: Dict[str, Any], output_path: Path) -> None:
    cat_breakdown = report.get("category_breakdown", {})
    rows_html = ""
    cat_labels = {
        "document_info": "Belge Bilgileri",
        "parties": "Taraflar",
        "transport_plans": "Tasima",
        "equipment_list": "Ekipman",
        "cargo_items": "Yuk Kalemleri",
        "other": "Diger",
    }
    for cat_name in ["document_info", "parties", "transport_plans", "equipment_list", "cargo_items"]:
        c = cat_breakdown.get(cat_name, {})
        label = cat_labels.get(cat_name, cat_name)
        rows_html += (
            f"<tr><td>{label}</td>"
            f"<td>{c.get('total_fields', 0)}</td>"
            f"<td>{c.get('correct_fields', 0)}</td>"
            f"<td>{c.get('accuracy', 0):.1f}%</td>"
            f"<td>{c.get('precision', 0):.1f}%</td>"
            f"<td>{c.get('recall', 0):.1f}%</td>"
            f"<td>{c.get('f1_score', 0):.1f}%</td></tr>\n"
        )
    overall_acc = report.get("accuracy", 0)
    xsd_summary = report.get("xsd_summary", {})
    xsd_pass_rate = xsd_summary.get("pass_rate_pct", 0)
    xsd_color = "#20c997" if xsd_pass_rate >= 90 else ("#ffa94d" if xsd_pass_rate >= 70 else "#fa5252")
    color = "#20c997" if overall_acc >= 90 else ("#ffa94d" if overall_acc >= 70 else "#fa5252")
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>CerberusVision Benchmark</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#f8f9fa;color:#212529}}
h1{{color:#0d9488}} .score{{font-size:48px;font-weight:800;color:{color}}} .card{{background:#fff;border-radius:12px;padding:20px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:10px 14px;text-align:left;border-bottom:1px solid #e9ecef}} th{{background:#f1f3f5;font-weight:600}}
.meta{{color:#868e96;font-size:14px}} .badge{{display:inline-block;padding:4px 10px;border-radius:16px;font-size:12px;font-weight:600}}
.badge-green{{background:#d3f9d8;color:#2b8a3e}} .badge-yellow{{background:#fff3bf;color:#e67700}} .badge-red{{background:#ffe3e3;color:#c92a2a}}
</style></head>
<body>
<h1>CerberusVision Benchmark Raporu</h1>
<p class="meta">{report.get('benchmark_date', '')} &middot; {report.get('documents', 0)} belge &middot; {report.get('total_time_seconds', 0):.1f}s</p>
<div class="card">
<h2>Genel Dogruluk</h2>
<div class="score">{overall_acc:.1f}%</div>
<p>{report.get('correct_fields', 0)} / {report.get('total_fields', 0)} alan dogru &middot; {report.get('missing_fields', 0)} eksik &middot; {report.get('mismatched_fields', 0)} hatali</p>
</div>
<div class="card">
<h2>XSD Schema Dogrulama</h2>
	<div class="score" style="color:{xsd_color}">{xsd_pass_rate:.1f}%</div>
	<p>{xsd_summary.get('passed', 0)} / {xsd_summary.get('total', 0)} belge XSD'den gecti &middot; {xsd_summary.get('failed', 0)} basarisiz</p>
	</div>
	<div class="card">
	<h2>Kategori Bazli Metrikler</h2>
<table>
<tr><th>Kategori</th><th>Alan</th><th>Dogru</th><th>Dogruluk</th><th>Kesinlik</th><th>Geri Cagirma</th><th>F1-Skor</th></tr>
{rows_html}
</table></div></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
