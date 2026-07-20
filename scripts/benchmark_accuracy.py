from __future__ import annotations

import argparse
import json
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
from app.llm.inference import run_inference_with_fallback
from app.ocr.spatial_ocr import (
    process_pdf_with_region_ocr,
    process_pdf_with_spatial_ocr,
)

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
        actual_present = {p for p, v in actual_cat.items() if v is not None}
        correct_set = set(evaluation.get("correct_fields", []))
        cat_correct = correct_set & expected_set
        tp = len(cat_correct)
        fp = len(actual_present - expected_set)
        fn = len(expected_set - actual_present)
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
    print("-" * 72)
    print(f"  {'Belge':<34} {'Alan':>6} {'Dogru':>6} {'Eksik':>6} {'Hata':>6} {'%Dog':>8}")
    print("-" * 72)
    for idx, result in enumerate(all_results):
        name = result.get("case_name", f"Belge {idx+1}")
        if len(name) > 32:
            name = name[:29] + "..."
        print(
            f"  {name:<34}"
            f" {result['total_fields']:>6}"
            f" {len(result['correct_fields']):>6}"
            f" {len(result['missing_fields']):>6}"
            f" {len(result['mismatched_fields']):>6}"
            f" {_format_percent(result['accuracy'])}"
        )
    print("-" * 72)
    print()


def _evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case_name = case["case_name"]
    pdf_rel = case.get("pdf")
    ocr_text_raw = case.get("ocr_text")
    document_language = case.get("document_language", "en")
    output_language = case.get("output_language", "en")
    expected = case.get("expected")

    print(f"  [{case_name}] Isleniyor...", end=" ", flush=True)
    t_start = time.time()

    if ocr_text_raw:
        full_ocr = ocr_text_raw
        segmented_ocr = None
    elif pdf_rel:
        pdf_path = (PROJECT_ROOT / pdf_rel).resolve()
        if not pdf_path.exists():
            pdf_path = Path(pdf_rel)
        full_ocr, segmented_ocr = _extract_ocr_text(
            pdf_path,
            case.get("ocr_lang", "latin" if document_language == "tr" else "en"),
        )
    else:
        raise ValueError(f"'{case_name}': pdf veya ocr_text alani gerekli")

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

    expected_flat = _flatten_ground_truth(expected)
    actual_flat = flatten_values(actual)

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
        "category_metrics": category_metrics,
        **evaluation,
    }


def main() -> int:
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
    args = parser.parse_args()

    cases = _load_benchmark_cases(args.dataset)

    pdf_count = sum(1 for c in cases if c.get("pdf"))
    text_count = sum(1 for c in cases if c.get("ocr_text") and not c.get("pdf"))
    print(f"Benchmark veri seti: {len(cases)} vaka ({pdf_count} PDF, {text_count} salt metin)")
    print()

    if args.pdf_only:
        cases = [c for c in cases if c.get("pdf")]
        if not cases:
            raise SystemExit("--pdf-only ile calistirilabilir vaka bulunamadi")
        print(f"PDF filtresi sonrasi: {len(cases)} vaka")
        print()

    t_total = time.time()
    all_results = [_evaluate_case(case) for case in cases]
    total_time = time.time() - t_total

    category_stats = _compute_category_stats(all_results)
    _print_report(all_results, category_stats, total_time)

    aggregated = aggregate_evaluations(all_results)
    output_payload = {
        "benchmark_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_time_seconds": round(total_time, 2),
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
<h2>Kategori Bazli Metrikler</h2>
<table>
<tr><th>Kategori</th><th>Alan</th><th>Dogru</th><th>Dogruluk</th><th>Kesinlik</th><th>Geri Cagirma</th><th>F1-Skor</th></tr>
{rows_html}
</table></div></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
