"""Phase 6.1 — ERP Function Calling (Tool Use) API endpoint'leri.

Mevcut onay akışını bozmadan, sadece FINAL durumundaki
ShippingInstruction'ları ERP komut formatına dönüştürüp
simüle edilmiş ERP API'sine gönderir.
"""

from __future__ import annotations

import asyncio
import logging
from weakref import WeakValueDictionary

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.integrations.erp_actions import (
    ErpCreateShipmentResponse,
    _read_successful_erp_delivery,
    mock_send_to_erp,
    transform_si_to_erp_payload,
)
from app.models import DocumentStatusCode, ProcessingStatus
from app.routes.processing import (
    _is_valid_session_id,
    _processing_store,
    _session_models,
)
from app.security import require_api_key

logger = logging.getLogger("cerberus.erp")

router = APIRouter(
    prefix="/api/erp",
    tags=["erp"],
    dependencies=[Depends(require_api_key)],
)

_erp_delivery_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@router.post("/create_shipment/{session_id}")
async def create_erp_shipment(session_id: str):
    """Onaylanmış (FINAL) Shipping Instruction'ı ERP gönderi kaydına dönüştür.

    Yalnızca document_status_code == FINAL olan oturumlar ERP'ye
    gönderilebilir. Taslak (DRAFT) veya hatalı (ERROR) oturumlar
    reddedilir.
    """
    if not _is_valid_session_id(session_id):
        return JSONResponse(
            status_code=400,
            content={"error": "Geçersiz oturum kimliği."},
        )

    # Bellek içi mağazalardan veriyi al (dosyadan değil)
    si_model = _session_models.get(session_id)
    stored = _processing_store.get(session_id)

    if si_model is None or stored is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    "Bu oturuma ait işlenmiş belge bulunamadı. "
                    "Belge hâlâ işleniyor veya oturum süresi dolmuş olabilir."
                ),
            },
        )

    # Sadece FINAL durumundakilere izin ver
    if si_model.document_status_code != DocumentStatusCode.FINAL:
        if si_model.document_status_code is not None:
            current_status = si_model.document_status_code.value
        elif stored.status is not None:
            current_status = stored.status.value if hasattr(stored.status, "value") else str(stored.status)
        else:
            current_status = "UNKNOWN"
        return JSONResponse(
            status_code=409,
            content={
                "error": (
                    f"ERP'ye yalnızca onaylanmış (FNL) belgeler gönderilebilir. "
                    f"Mevcut durum: {current_status}"
                ),
            },
        )

    try:
        erp_payload = transform_si_to_erp_payload(si_model)
        delivery_lock = _erp_delivery_locks.setdefault(session_id, asyncio.Lock())
        async with delivery_lock:
            existing_response = await asyncio.to_thread(
                _read_successful_erp_delivery,
                session_id,
                erp_payload,
            )
            if existing_response is not None:
                logger.info(
                    "ERP shipment reused: session=%s tracking=%s",
                    session_id,
                    existing_response.tracking_number,
                )
                return JSONResponse(
                    status_code=200,
                    content=existing_response.model_dump(mode="json"),
                )

            response: ErpCreateShipmentResponse = await mock_send_to_erp(
                erp_payload, session_id=session_id,
            )
            if response.success:
                logger.info(
                    "ERP shipment created: session=%s tracking=%s",
                    session_id,
                    response.tracking_number,
                )
                return JSONResponse(
                    status_code=201,
                    content=response.model_dump(mode="json"),
                )
            return JSONResponse(status_code=502, content=response.model_dump(mode="json"))

    except Exception as exc:
        logger.exception("ERP shipment failed for session %s: %s", session_id, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": f"ERP gönderi kaydı oluşturulamadı: {exc}",
            },
        )
