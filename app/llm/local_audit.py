from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, List

from app.config import settings
from app.models import (
    AuditFinding,
    FieldValidation,
    LocalAuditAssessment,
    PartyRoleCode,
    ShippingInstruction,
    WeightUnit,
)


def _finding(
    field_path: str,
    code: str,
    message: str,
    severity: str,
    points: int,
) -> AuditFinding:
    return AuditFinding(
        field_path=field_path,
        code=code,
        message=message,
        severity=severity,
        risk_points=points,
    )


def _is_valid_iso_date(value: str, include_time: bool = False) -> bool:
    try:
        if include_time:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            date.fromisoformat(value[:10])
        return True
    except (TypeError, ValueError):
        return False


def _iso6346_check_digit(reference: str) -> bool:
    normalized = re.sub(r"\s+", "", reference or "").upper()
    if not re.fullmatch(r"[A-Z]{4}\d{7}", normalized):
        return False
    letter_values = {}
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


def _weight_in_kg(value: float, unit: WeightUnit) -> float:
    return value * 1000.0 if unit == WeightUnit.TON else value


def _add_format_findings(si: ShippingInstruction, findings: List[AuditFinding]) -> None:
    if si.issue_date and not _is_valid_iso_date(si.issue_date):
        findings.append(_finding("issue_date", "invalid_date", "Issue date is not ISO formatted.", "medium", 10))
    if si.shipping_instruction_date_time and not _is_valid_iso_date(
        si.shipping_instruction_date_time, include_time=True
    ):
        findings.append(_finding(
            "shipping_instruction_date_time",
            "invalid_datetime",
            "Shipping instruction date-time is not ISO formatted.",
            "medium",
            10,
        ))

    for index, party in enumerate(si.parties):
        country_code = party.address.country_code if party.address else None
        if country_code and not re.fullmatch(r"[A-Za-z]{2}", country_code):
            findings.append(_finding(
                f"parties[{index}].address.country_code",
                "invalid_country_code",
                "Country code must contain two letters.",
                "medium",
                8,
            ))

    locations = []
    if si.place_of_issue:
        locations.append(("place_of_issue", si.place_of_issue))
    for index, plan in enumerate(si.transport_plans):
        for name in ("port_of_loading", "port_of_discharge", "place_of_receipt", "place_of_delivery"):
            location = getattr(plan, name)
            if location:
                locations.append((f"transport_plans[{index}].{name}", location))
    for path, location in locations:
        code = location.un_location_code
        if code and not re.fullmatch(r"[A-Za-z]{2}[A-Za-z0-9]{3}", code):
            findings.append(_finding(
                f"{path}.un_location_code",
                "invalid_unlocode",
                "UN/LOCODE must contain five valid characters.",
                "medium",
                8,
            ))


def _add_numeric_findings(si: ShippingInstruction, findings: List[AuditFinding]) -> None:
    cargo_weights = []
    for index, item in enumerate(si.cargo_items):
        if item.package_quantity is not None and item.package_quantity <= 0:
            findings.append(_finding(
                f"cargo_items[{index}].package_quantity",
                "non_positive_quantity",
                "Package quantity must be positive.",
                "high",
                20,
            ))
        if item.weight and item.weight.weight_value is not None:
            cargo_weights.append(_weight_in_kg(item.weight.weight_value, item.weight.unit))
            if item.weight.weight_value <= 0:
                findings.append(_finding(
                    f"cargo_items[{index}].weight.weight_value",
                    "non_positive_weight",
                    "Cargo weight must be positive.",
                    "high",
                    20,
                ))
        if item.volume and item.volume.volume_value is not None and item.volume.volume_value <= 0:
            findings.append(_finding(
                f"cargo_items[{index}].volume.volume_value",
                "non_positive_volume",
                "Cargo volume must be positive.",
                "medium",
                10,
            ))

    equipment_weights = []
    for index, equipment in enumerate(si.equipment_list):
        if equipment.equipment_reference and not _iso6346_check_digit(equipment.equipment_reference):
            findings.append(_finding(
                f"equipment_list[{index}].equipment_reference",
                "invalid_container_check_digit",
                "Container reference does not pass ISO 6346 check-digit validation.",
                "high",
                25,
            ))
        if equipment.cargo_gross_weight and equipment.cargo_gross_weight.weight is not None:
            equipment_weights.append(_weight_in_kg(
                equipment.cargo_gross_weight.weight,
                equipment.cargo_gross_weight.unit,
            ))
            if equipment.cargo_gross_weight.weight <= 0:
                findings.append(_finding(
                    f"equipment_list[{index}].cargo_gross_weight.weight",
                    "non_positive_weight",
                    "Equipment gross weight must be positive.",
                    "high",
                    20,
                ))

    if cargo_weights and equipment_weights:
        cargo_total = sum(cargo_weights)
        equipment_total = sum(equipment_weights)
        denominator = max(abs(cargo_total), abs(equipment_total), 1.0)
        if abs(cargo_total - equipment_total) / denominator > 0.05:
            findings.append(_finding(
                "cargo_items",
                "weight_total_mismatch",
                "Cargo-item and equipment gross-weight totals differ by more than 5%.",
                "high",
                20,
            ))


def assess_local_result(
    si: ShippingInstruction,
    ocr_text: str,
    is_xsd_valid: bool,
    xsd_errors: Iterable[str],
    missing_fields: Iterable[FieldValidation],
    threshold: int | None = None,
) -> LocalAuditAssessment:
    findings: List[AuditFinding] = []
    missing_list = list(missing_fields)
    xsd_error_list = list(xsd_errors)
    for field in missing_list:
        findings.append(_finding(
            field.field_path,
            "missing_mandatory_field",
            f"Mandatory field is missing: {field.field_label}.",
            "medium",
            5,
        ))
    if not is_xsd_valid:
        findings.append(_finding(
            "xml",
            "xsd_validation_failed",
            f"XML validation failed with {len(xsd_error_list)} error(s).",
            "high",
            30,
        ))
    if len(ocr_text.strip()) < 100:
        findings.append(_finding(
            "ocr_text",
            "short_ocr_text",
            "OCR output is unusually short.",
            "medium",
            15,
        ))

    roles = {party.party_role_code for party in si.parties}
    if PartyRoleCode.SHIPPER_DCSA not in roles and PartyRoleCode.SHIPPER not in roles:
        findings.append(_finding(
            "parties",
            "missing_core_party_role",
            "Shipper role is missing.",
            "high",
            20,
        ))
    if PartyRoleCode.CONSIGNEE_DCSA not in roles and PartyRoleCode.CONSIGNEE not in roles:
        findings.append(_finding(
            "parties",
            "missing_core_party_role",
            "Consignee role is missing.",
            "high",
            20,
        ))

    _add_format_findings(si, findings)
    _add_numeric_findings(si, findings)

    risk_score = float(min(100, sum(finding.risk_points for finding in findings)))
    use_threshold = threshold if threshold is not None else settings.deepseek.risk_threshold
    return LocalAuditAssessment(
        risk_score=risk_score,
        confidence_score=100.0 - risk_score,
        requires_cloud_review=risk_score >= use_threshold,
        findings=findings,
    )


def should_run_automatic_cloud_review(
    assessment: LocalAuditAssessment,
    api_key: str | None,
    mode: str | None = None,
) -> bool:
    if not api_key:
        return False
    review_mode = (mode or settings.deepseek.review_mode).lower()
    if review_mode == "always":
        return True
    if review_mode == "risk":
        return assessment.requires_cloud_review
    return False
