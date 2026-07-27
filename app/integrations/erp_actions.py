"""Phase 6.1 — ShippingInstruction → ERP komut dönüşümü ve mock API gönderimi.

Mevcut webhook.py pattern'ini (fire-and-forget, exponential backoff,
audit logging) izleyerek çalışır. Gerçek ERP entegrasyonu için
``mock_send_to_erp`` yerine gerçek bir HTTP istemcisi konulması yeterlidir.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import (
    ErpCreateShipmentResponse,
    ErpShipmentPayload,
    ShippingInstruction,
)

logger = logging.getLogger("cerberus.erp")

_MAX_RETRIES = 3
_BACKOFF_SECONDS = 2.0
_MOCK_LATENCY_SECONDS = 0.3


# ---------------------------------------------------------------------------
# Dönüşüm
# ---------------------------------------------------------------------------


def _first_party_by_role(
    si: ShippingInstruction,
    role_codes: tuple[str, ...],
) -> dict[str, str | None]:
    """Belirtilen rollerden ilk eşleşen tarafı döndür."""
    for party in si.parties:
        if party.party_role_code and party.party_role_code.value in role_codes:
            address = party.address
            return {
                "name": party.party_name,
                "street": address.street if address else None,
                "city": address.city if address else None,
                "country": address.country_code if address else None,
            }
    return {"name": None, "street": None, "city": None, "country": None}


def _first_location_name(obj: Any) -> str | None:
    """Location nesnesinden location_name değerini güvenle al."""
    if obj is None:
        return None
    return obj.location_name


def transform_si_to_erp_payload(si: ShippingInstruction) -> ErpShipmentPayload:
    """ShippingInstruction Pydantic modelini ERP'nin beklediği düz JSON'a çevir."""

    shipper = _first_party_by_role(si, ("CZ", "SHI"))
    consignee = _first_party_by_role(si, ("CN", "CON"))
    notify = _first_party_by_role(si, ("N1", "NTF"))

    transport_plan = si.transport_plans[0] if si.transport_plans else None

    equipment_data: list[dict] = []
    for eq in si.equipment_list:
        entry: dict[str, Any] = {}
        if eq.equipment_reference:
            entry["equipment_reference"] = eq.equipment_reference
        if eq.iso_equipment_code:
            entry["iso_equipment_code"] = eq.iso_equipment_code
        if eq.cargo_gross_weight and eq.cargo_gross_weight.weight is not None:
            entry["cargo_gross_weight"] = {
                "weight": eq.cargo_gross_weight.weight,
                "unit": eq.cargo_gross_weight.unit.value,
            }
        if eq.seals:
            entry["seals"] = [
                s.seal_number for s in eq.seals if s.seal_number
            ]
        equipment_data.append(entry)

    cargo_data: list[dict] = []
    for item in si.cargo_items:
        entry: dict[str, Any] = {}
        if item.package_quantity is not None:
            entry["package_quantity"] = item.package_quantity
        if item.package_kind_code:
            entry["package_kind_code"] = item.package_kind_code.value
        if item.description_of_goods:
            entry["description_of_goods"] = item.description_of_goods
        if item.weight and item.weight.weight_value is not None:
            entry["weight"] = {
                "weight_value": item.weight.weight_value,
                "unit": item.weight.unit.value,
            }
        if item.volume and item.volume.volume_value is not None:
            entry["volume"] = {
                "volume_value": item.volume.volume_value,
                "unit": item.volume.unit.value,
            }
        if item.dangerous_goods_list:
            entry["dangerous_goods"] = [
                {
                    "un_number": dg.un_number,
                    "imdg_class": dg.imdg_class,
                    "packing_group": dg.packing_group,
                }
                for dg in item.dangerous_goods_list
            ]
        cargo_data.append(entry)

    return ErpShipmentPayload(
        shipping_instruction_reference=si.shipping_instruction_reference,
        carrier_booking_reference=si.carrier_booking_reference,
        transport_document_type=(
            si.transport_document_type.value
            if si.transport_document_type
            else None
        ),
        freight_payment_term_code=(
            si.freight_payment_term_code.value
            if si.freight_payment_term_code
            else None
        ),
        issue_date=si.issue_date,
        place_of_issue_name=(
            si.place_of_issue.location_name if si.place_of_issue else None
        ),
        shipper_name=shipper["name"],
        shipper_address=shipper["street"],
        shipper_city=shipper["city"],
        shipper_country=shipper["country"],
        consignee_name=consignee["name"],
        consignee_address=consignee["street"],
        consignee_city=consignee["city"],
        consignee_country=consignee["country"],
        notify_party_name=notify["name"],
        port_of_loading=(
            _first_location_name(transport_plan.port_of_loading)
            if transport_plan
            else None
        ),
        port_of_discharge=(
            _first_location_name(transport_plan.port_of_discharge)
            if transport_plan
            else None
        ),
        vessel_imo_number=(
            transport_plan.vessel_imo_number if transport_plan else None
        ),
        carrier_voyage_number=(
            transport_plan.carrier_voyage_number if transport_plan else None
        ),
        equipment_list=equipment_data,
        cargo_items=cargo_data,
        remarks=si.remarks,
    )


# ---------------------------------------------------------------------------
# Mock ERP API (exponential backoff, fire-and-forget)
# ---------------------------------------------------------------------------


def _generate_tracking_number() -> str:
    now = datetime.now(timezone.utc)
    return f"ERP-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S%f')[:5]}"


def _erp_log_path(session_id: str) -> Path:
    base = settings.logs_dir.resolve()
    target = (base / session_id / "erp_delivery.json").resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Path traversal denemesi tespit edildi.")
    return target


def _read_successful_erp_delivery(
    session_id: str,
    payload: ErpShipmentPayload,
) -> ErpCreateShipmentResponse | None:
    log_path = _erp_log_path(session_id)
    if not log_path.exists():
        return None
    try:
        record = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if record.get("status") != "success":
        return None
    tracking_number = str(record.get("tracking_number") or "")
    if not tracking_number:
        detail = str(record.get("detail") or "")
        if detail.startswith("tracking_number="):
            tracking_number = detail.removeprefix("tracking_number=").strip()
    if not tracking_number:
        return None
    return ErpCreateShipmentResponse(
        success=True,
        tracking_number=tracking_number,
        message="Gönderi bu oturum için daha önce oluşturuldu.",
        shipment_payload=payload,
    )


def _write_erp_log(
    session_id: str,
    attempt: int,
    status: str,
    detail: str,
    tracking_number: str = "",
) -> None:
    record = {
        "session_id": session_id,
        "attempt": attempt,
        "status": status,
        "detail": detail,
        "tracking_number": tracking_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log_path = _erp_log_path(session_id)
    tmp_path = log_path.with_suffix(".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(tmp_path, log_path)


async def mock_send_to_erp(
    payload: ErpShipmentPayload,
    session_id: str = "",
) -> ErpCreateShipmentResponse:
    """Simüle edilmiş ERP API çağrısı — exponential backoff ile.

    Gerçek entegrasyonda bu fonksiyon ``httpx.AsyncClient`` ile
    dış ERP endpoint'ine POST atacak şekilde değiştirilmelidir.
    """
    erp_enabled = os.environ.get("ERP_MOCK_ENABLED", "1") == "1"
    if not erp_enabled:
        return ErpCreateShipmentResponse(
            success=False,
            tracking_number="",
            message="ERP mock is disabled (ERP_MOCK_ENABLED=0).",
        )

    tracking = _generate_tracking_number()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            # Gerçek API çağrısı simülasyonu — hafif gecikme
            await asyncio.sleep(_MOCK_LATENCY_SECONDS)

            # Her zaman başarılı dönen mock
            response = ErpCreateShipmentResponse(
                success=True,
                tracking_number=tracking,
                message=(
                    f"Gönderi kaydı başarıyla oluşturuldu "
                    f"(deneme {attempt}/{_MAX_RETRIES})."
                ),
                shipment_payload=payload,
            )
            await asyncio.to_thread(
                _write_erp_log,
                session_id,
                attempt,
                "success",
                f"tracking_number={tracking}",
                tracking,
            )
            logger.info(
                "ERP shipment created for session %s (attempt %d/%d): %s",
                session_id, attempt, _MAX_RETRIES, tracking,
            )
            return response

        except Exception as exc:
            detail = str(exc)[:200]
            await asyncio.to_thread(
                _write_erp_log, session_id, attempt, "failed", detail,
            )
            logger.warning(
                "ERP attempt %d/%d failed for session %s: %s",
                attempt, _MAX_RETRIES, session_id, detail,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    # Tüm denemeler başarısız
    await asyncio.to_thread(
        _write_erp_log,
        session_id, _MAX_RETRIES, "exhausted",
        "All retry attempts failed",
    )
    return ErpCreateShipmentResponse(
        success=False,
        tracking_number="",
        message="Tüm denemelere rağmen ERP bağlantısı kurulamadı.",
    )
