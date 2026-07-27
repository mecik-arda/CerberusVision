"""Phase 6.1 — ERP Function Calling birim testleri."""

from __future__ import annotations

import pytest

from app.integrations.erp_actions import (
    _generate_tracking_number,
    _first_party_by_role,
    transform_si_to_erp_payload,
)
from app.models import (
    DocumentStatusCode,
    ErpCreateShipmentResponse,
    ErpShipmentPayload,
)
from tests.test_validator import create_complete_si


# ---------------------------------------------------------------------------
# Dönüşüm testleri
# ---------------------------------------------------------------------------


def test_transform_si_to_erp_payload_returns_erp_shipment_payload():
    """Tam bir ShippingInstruction başarıyla ERP payload'ına dönüşmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    assert isinstance(payload, ErpShipmentPayload)
    assert payload.shipping_instruction_reference == si.shipping_instruction_reference
    assert payload.carrier_booking_reference == si.carrier_booking_reference
    if si.transport_document_type is not None:
        assert payload.transport_document_type == si.transport_document_type.value


def test_transform_si_to_erp_payload_shipper_fields():
    """Gönderici (CZ) alanları doğru eşlenmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    shipper = next(
        (p for p in si.parties if p.party_role_code.value == "CZ"), None
    )
    assert shipper is not None, "Test fixture'ında CZ rolü olmalı"
    assert payload.shipper_name == shipper.party_name
    if shipper.address:
        assert payload.shipper_city == shipper.address.city
        assert payload.shipper_country == shipper.address.country_code


def test_transform_si_to_erp_payload_consignee_fields():
    """Alıcı (CN) alanları doğru eşlenmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    consignee = next(
        (p for p in si.parties if p.party_role_code.value == "CN"), None
    )
    assert consignee is not None, "Test fixture'ında CN rolü olmalı"
    assert payload.consignee_name == consignee.party_name


def test_transform_si_to_erp_payload_port_fields():
    """Taşıma limanları doğru eşlenmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    transport_plan = si.transport_plans[0]
    assert payload.port_of_loading == transport_plan.port_of_loading.location_name
    assert payload.port_of_discharge == transport_plan.port_of_discharge.location_name
    assert payload.vessel_imo_number == transport_plan.vessel_imo_number


def test_transform_si_to_erp_payload_equipment_list():
    """Ekipman listesi doğru dönüşmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    assert len(payload.equipment_list) == len(si.equipment_list)
    assert payload.equipment_list[0]["equipment_reference"] == (
        si.equipment_list[0].equipment_reference
    )


def test_transform_si_to_erp_payload_cargo_items():
    """Yük kalemleri doğru dönüşmeli."""
    si = create_complete_si()
    payload = transform_si_to_erp_payload(si)

    assert len(payload.cargo_items) == len(si.cargo_items)
    assert payload.cargo_items[0]["description_of_goods"] == (
        si.cargo_items[0].description_of_goods
    )


def test_transform_si_to_erp_payload_empty_si():
    """Boş SI'da null değerler dönmeli, hata vermemeli."""
    from app.models import ShippingInstruction

    si = ShippingInstruction()
    payload = transform_si_to_erp_payload(si)

    assert isinstance(payload, ErpShipmentPayload)
    assert payload.shipping_instruction_reference is None
    assert payload.shipper_name is None
    assert payload.equipment_list == []


def test_transform_si_to_erp_payload_with_remarks():
    """Remarks alanı doğru taşınmalı."""
    from app.models import ShippingInstruction

    si = ShippingInstruction(remarks="TEST REMARK — Özel not")
    payload = transform_si_to_erp_payload(si)

    assert payload.remarks == "TEST REMARK — Özel not"


# ---------------------------------------------------------------------------
# Yardımcı fonksiyon testleri
# ---------------------------------------------------------------------------


def test_first_party_by_role_finds_correct_party():
    """_first_party_by_role doğru rolü bulmalı."""
    si = create_complete_si()
    result = _first_party_by_role(si, ("CZ", "SHI"))

    assert result["name"] is not None
    assert isinstance(result["name"], str)


def test_first_party_by_role_returns_empty_for_missing_role():
    """Olmayan bir rol için boş dict dönmeli."""
    from app.models import ShippingInstruction

    si = ShippingInstruction()
    result = _first_party_by_role(si, ("FW",))

    assert result["name"] is None
    assert result["city"] is None


def test_generate_tracking_number_format():
    """Takip numarası ERP-YYYYMMDD-XXXXX formatında olmalı."""
    tracking = _generate_tracking_number()

    import re

    assert re.match(r"^ERP-\d{8}-\d{5}$", tracking), (
        f"Geçersiz format: {tracking}"
    )


# ---------------------------------------------------------------------------
# ERP response modeli testleri
# ---------------------------------------------------------------------------


def test_erp_create_shipment_response_success():
    """Başarılı ERP yanıtı geçerli olmalı."""
    response = ErpCreateShipmentResponse(
        success=True,
        tracking_number="ERP-20260726-00001",
        message="Gönderi kaydı oluşturuldu.",
    )

    assert response.success is True
    assert response.tracking_number == "ERP-20260726-00001"


def test_erp_create_shipment_response_failure():
    """Başarısız ERP yanıtı geçerli olmalı."""
    response = ErpCreateShipmentResponse(
        success=False,
        tracking_number="",
        message="Tüm denemelere rağmen ERP bağlantısı kurulamadı.",
    )

    assert response.success is False
    assert response.tracking_number == ""


def test_erp_shipment_payload_optional_fields():
    """Opsiyonel alanlar None olabilmeli."""
    payload = ErpShipmentPayload()
    assert payload.shipping_instruction_reference is None
    assert payload.port_of_loading is None
    assert payload.equipment_list == []
    assert payload.cargo_items == []


def test_erp_log_path_rejects_traversal():
    """_erp_log_path path traversal girişimini reddetmeli."""
    from app.integrations.erp_actions import _erp_log_path

    with pytest.raises(ValueError, match="Path traversal"):
        _erp_log_path("../../../etc/passwd")


def test_successful_erp_delivery_is_loaded_from_persistent_log(
    monkeypatch,
    tmp_path,
):
    import app.integrations.erp_actions as actions

    session_id = "20260726_130000_000001"
    monkeypatch.setattr(actions.settings, "logs_dir", tmp_path)
    payload = ErpShipmentPayload(shipping_instruction_reference="SI-001")
    actions._write_erp_log(
        session_id,
        1,
        "success",
        "tracking_number=ERP-20260726-12345",
        "ERP-20260726-12345",
    )

    restored = actions._read_successful_erp_delivery(session_id, payload)

    assert restored is not None
    assert restored.success is True
    assert restored.tracking_number == "ERP-20260726-12345"
    assert restored.shipment_payload == payload


@pytest.mark.asyncio
async def test_erp_route_reuses_delivery_without_second_send(monkeypatch):
    import json
    from types import SimpleNamespace

    import app.routes.erp as erp_route
    import app.routes.processing as processing

    session_id = "20260726_130000_000002"
    instruction = create_complete_si()
    instruction.document_status_code = DocumentStatusCode.FINAL
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = SimpleNamespace(status=None)
    erp_route._erp_delivery_locks.pop(session_id, None)
    delivery_state = {}
    send_count = 0

    def read_delivery(_session_id, payload):
        stored_tracking = delivery_state.get(_session_id)
        if not stored_tracking:
            return None
        return ErpCreateShipmentResponse(
            success=True,
            tracking_number=stored_tracking,
            message="existing",
            shipment_payload=payload,
        )

    async def send_delivery(payload, session_id=""):
        nonlocal send_count
        send_count += 1
        tracking_number = "ERP-20260726-54321"
        delivery_state[session_id] = tracking_number
        return ErpCreateShipmentResponse(
            success=True,
            tracking_number=tracking_number,
            message="created",
            shipment_payload=payload,
        )

    monkeypatch.setattr(erp_route, "_read_successful_erp_delivery", read_delivery)
    monkeypatch.setattr(erp_route, "mock_send_to_erp", send_delivery)

    try:
        first = await erp_route.create_erp_shipment(session_id)
        second = await erp_route.create_erp_shipment(session_id)
    finally:
        processing._session_models.pop(session_id, None)
        processing._processing_store.pop(session_id, None)
        erp_route._erp_delivery_locks.pop(session_id, None)

    assert first.status_code == 201
    assert second.status_code == 200
    assert json.loads(first.body)["tracking_number"] == "ERP-20260726-54321"
    assert json.loads(second.body)["tracking_number"] == "ERP-20260726-54321"
    assert send_count == 1
