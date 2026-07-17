from __future__ import annotations
import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from time import monotonic
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from app.config import settings
from app.security import enforce_upload_rate_limit, require_api_key
from app.models import (
    DocumentStatusCode,
    ProcessingStatus,
    ProcessingResult,
    SaveInstructionRequest,
    ShippingInstruction,
)
from app.utils.audit_logger import (
    create_session_id,
    log_ocr_result,
    log_llm_result,
    log_xml_result,
    log_validation_report,
    log_processing_summary,
    log_cloud_review_report,
    log_user_revision,
)

from app.ocr.spatial_ocr import process_pdf_with_spatial_ocr
from app.llm.inference import run_inference_with_fallback
from app.llm.cloud_inference import run_deepseek_review
from app.llm.local_audit import assess_local_result, should_run_automatic_cloud_review
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import check_mandatory_fields, validate_xml_against_xsd

router = APIRouter(
    prefix="/api",
    tags=["processing"],
    dependencies=[Depends(require_api_key)],
)

inference_semaphore = asyncio.Semaphore(1)
cloud_review_semaphore = asyncio.Semaphore(1)

_processing_store: dict[str, ProcessingResult] = {}
_stream_queues: dict[str, asyncio.Queue] = {}
_session_models: dict[str, ShippingInstruction] = {}
_session_locks: dict[str, asyncio.Lock] = {}
_stream_queue_created_at: dict[str, float] = {}
_stream_queue_completed_at: dict[str, float] = {}
_stream_cleanup_handles: dict[str, asyncio.TimerHandle] = {}
_stream_consumers: set[str] = set()
_active_pipeline_sessions: set[str] = set()
_active_pipeline_lock = asyncio.Lock()


_PROCESSING_STORE_MAX_SIZE = 100
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


class _SizeLimitedReader:
    def __init__(self, raw_file, max_size: int):
        self.raw_file = raw_file
        self.max_size = max_size
        self.total = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.raw_file.read(size)
        self.total += len(chunk)
        if self.total > self.max_size:
            raise UploadTooLargeError
        return chunk


def _emit_status(session_id: str, status: ProcessingStatus, message: str, data: dict = None) -> str:
    payload = {
        "session_id": session_id,
        "status": status.value,
        "message": message,
    }
    if data:
        payload["data"] = data
        store_kwargs = {k: v for k, v in data.items() if k in ProcessingResult.model_fields.keys() - {"status", "message"}}
    else:
        store_kwargs = {}
    if session_id not in _processing_store and len(_processing_store) >= _PROCESSING_STORE_MAX_SIZE:
        oldest_key = next(iter(_processing_store))
        _processing_store.pop(oldest_key, None)
        _session_models.pop(oldest_key, None)
        _session_locks.pop(oldest_key, None)
    existing = _processing_store.get(session_id)
    existing_data = existing.model_dump() if existing else {}
    existing_data.update(store_kwargs)
    existing_data.update({"status": status, "message": message})
    _processing_store[session_id] = ProcessingResult.model_validate(existing_data)
    return json.dumps(payload, ensure_ascii=False)


async def _run_blocking(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def _get_session_lock(session_id: str) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


async def _reserve_pipeline_slot(session_id: str) -> bool:
    async with _active_pipeline_lock:
        if len(_active_pipeline_sessions) >= settings.server.max_active_pipelines:
            return False
        _active_pipeline_sessions.add(session_id)
        return True


async def _release_pipeline_slot(session_id: str) -> None:
    async with _active_pipeline_lock:
        _active_pipeline_sessions.discard(session_id)


def _copy_upload_to_path(file: UploadFile, pdf_path: Path) -> None:
    source = file.file
    source.seek(0)
    if source.read(5) != b"%PDF-":
        raise ValueError("The uploaded file is not a valid PDF.")
    source.seek(0)
    limited_reader = _SizeLimitedReader(source, _MAX_UPLOAD_SIZE)
    try:
        with pdf_path.open("wb") as destination:
            shutil.copyfileobj(limited_reader, destination, length=1024 * 1024)
    except Exception:
        pdf_path.unlink(missing_ok=True)
        raise


async def _save_uploaded_pdf(file: UploadFile, pdf_path: Path) -> None:
    await _run_blocking(_copy_upload_to_path, file, pdf_path)


def _local_review_data(assessment, summary: str) -> dict:
    return {
        "audit_confidence_score": assessment.confidence_score,
        "audit_summary": summary,
        "cloud_review_used": False,
        "cloud_review_available": bool(settings.deepseek.api_key)
        and settings.deepseek.review_mode != "off",
        "local_risk_score": assessment.risk_score,
        "local_warnings": [finding.model_dump(mode="json") for finding in assessment.findings],
        "suspicious_fields": list(dict.fromkeys(
            finding.field_path for finding in assessment.findings
        )),
    }


def _local_review_summary(assessment) -> str:
    if not settings.deepseek.api_key:
        return "Yerel kontroller tamamlandi; DeepSeek yapilandirilmadigi icin kullanilmadi."
    mode = settings.deepseek.review_mode
    if mode == "off":
        return "Yerel kontroller tamamlandi; bulut denetimi kapali."
    if mode == "manual":
        return "Yerel kontroller tamamlandi; DeepSeek yalnizca manuel istekle kullanilir."
    if not assessment.requires_cloud_review:
        return "Yerel kontroller yeterli bulundu; DeepSeek cagrilmadi."
    return "Yerel kontroller tamamlandi; bulut denetimi kullanilamadi."


async def _execute_cloud_review(
    session_id: str,
    instruction: ShippingInstruction,
    assessment,
    ocr_text: str,
    label: str,
):
    review, raw_output, sent_payload = await _run_blocking(
        run_deepseek_review, instruction, assessment, ocr_text
    )
    report_path = log_cloud_review_report(
        session_id,
        local_assessment=assessment.model_dump(mode="json"),
        cloud_review_used=True,
        review=review.model_dump(mode="json"),
        sent_payload=sent_payload,
        raw_output=raw_output,
        label=label,
    )
    data = {
        "audit_confidence_score": review.score,
        "audit_summary": review.summary,
        "cloud_review_used": True,
        "cloud_review_available": True,
        "local_risk_score": assessment.risk_score,
        "local_warnings": [finding.model_dump(mode="json") for finding in assessment.findings],
        "suspicious_fields": list(dict.fromkeys(
            [finding.field_path for finding in assessment.findings]
            + review.suspicious_fields
        )),
    }
    return data, report_path


async def process_pdf_pipeline(
    pdf_path: Path,
    session_id: str,
    filename: str,
    status_queue: asyncio.Queue,
):
    async with _get_session_lock(session_id):
        await _process_pdf_pipeline_locked(
            pdf_path,
            session_id,
            filename,
            status_queue,
        )


async def _process_pdf_pipeline_locked(
    pdf_path: Path,
    session_id: str,
    filename: str,
    status_queue: asyncio.Queue,
):
    try:
        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.OCR_PROCESSING, "OCR Isleniyor...",
        ))

        async with inference_semaphore:
            ocr_text, boxes = await _run_blocking(process_pdf_with_spatial_ocr, pdf_path)
        boxes_data = [[asdict(box) for box in page_boxes] for page_boxes in boxes]
        ocr_path = log_ocr_result(session_id, ocr_text, boxes_data)

        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.LLM_ANALYZING, "LLM Analizi...",
            data={"raw_ocr_text": ocr_text},
        ))

        async with inference_semaphore:
            si_model, raw_llm_json = await _run_blocking(run_inference_with_fallback, ocr_text)
        llm_path = log_llm_result(session_id, raw_llm_json)
        _session_models[session_id] = si_model

        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.XML_VALIDATING, "XML Dogrulaniyor...",
        ))

        xml_content = await _run_blocking(shipping_instruction_to_xml, si_model)
        xml_path = log_xml_result(session_id, xml_content)

        is_xsd_valid, errors = await _run_blocking(validate_xml_against_xsd, xml_content)
        missing_fields = check_mandatory_fields(si_model)
        local_assessment = assess_local_result(
            si_model,
            ocr_text,
            is_xsd_valid,
            errors,
            missing_fields,
        )
        review_data = _local_review_data(
            local_assessment, _local_review_summary(local_assessment)
        )
        cloud_review_path = None
        if should_run_automatic_cloud_review(
            local_assessment,
            settings.deepseek.api_key,
            settings.deepseek.review_mode,
        ):
            status_queue.put_nowait(_emit_status(
                session_id,
                ProcessingStatus.CLOUD_REVIEW,
                "Riskli alanlar DeepSeek ile kisa denetimden geciriliyor...",
            ))
            try:
                async with cloud_review_semaphore:
                    review_data, cloud_review_path = await _execute_cloud_review(
                        session_id, si_model, local_assessment, ocr_text, "initial"
                    )
            except Exception as cloud_error:
                review_data = _local_review_data(
                    local_assessment,
                    "DeepSeek denetimi basarisiz oldu; yalnizca yerel kontroller kullanildi.",
                )
                cloud_review_path = log_cloud_review_report(
                    session_id,
                    local_assessment=local_assessment.model_dump(mode="json"),
                    cloud_review_used=False,
                    error=str(cloud_error),
                    label="initial",
                )
        else:
            cloud_review_path = log_cloud_review_report(
                session_id,
                local_assessment=local_assessment.model_dump(mode="json"),
                cloud_review_used=False,
                label="initial",
            )
        status = (
            ProcessingStatus.COMPLETED
            if is_xsd_valid and not missing_fields
            else ProcessingStatus.DRAFT
        )

        validation_path = log_validation_report(
            session_id,
            is_valid=is_xsd_valid,
            errors=errors,
            missing_fields=[f.model_dump() for f in missing_fields],
            status=status.value,
        )

        log_processing_summary(
            session_id,
            filename,
            status.value,
            str(ocr_path),
            str(llm_path),
            str(xml_path),
            str(validation_path),
            str(cloud_review_path) if cloud_review_path else None,
        )

        result_data = {
            "xml_content": xml_content,
            "raw_ocr_text": ocr_text,
            "raw_llm_json": si_model.model_dump_json(),
            "structured_data": si_model.model_dump(mode="json"),
            "validation_errors": errors,
            "missing_fields": [f.model_dump() for f in missing_fields],
            **review_data,
        }

        if status == ProcessingStatus.COMPLETED:
            status_queue.put_nowait(_emit_status(
                session_id, ProcessingStatus.COMPLETED, "Islem tamamlandi.",
                data=result_data,
            ))
        else:
            status_queue.put_nowait(_emit_status(
                session_id, ProcessingStatus.DRAFT, "Taslak (Draft) - Eksik alanlar mevcut.",
                data=result_data,
            ))

    except Exception as e:
        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.ERROR, f"Hata: {str(e)}",
        ))

    finally:
        pdf_path.unlink(missing_ok=True)
        status_queue.put_nowait(None)
        _mark_stream_queue_complete(session_id)
        await _release_pipeline_slot(session_id)


def _drop_stream_queue(session_id: str) -> None:
    cleanup_handle = _stream_cleanup_handles.pop(session_id, None)
    if cleanup_handle is not None:
        cleanup_handle.cancel()
    _stream_queues.pop(session_id, None)
    _stream_queue_created_at.pop(session_id, None)
    _stream_queue_completed_at.pop(session_id, None)


def _prune_stream_queues(now: float | None = None) -> None:
    timestamp = monotonic() if now is None else now
    expired = [
        session_id
        for session_id, completed_at in _stream_queue_completed_at.items()
        if timestamp - completed_at >= settings.server.stream_queue_ttl_seconds
        and session_id not in _stream_consumers
        and session_id not in _active_pipeline_sessions
    ]
    for session_id in expired:
        _drop_stream_queue(session_id)
    overflow = len(_stream_queues) - settings.server.stream_queue_max_size + 1
    if overflow <= 0:
        return
    candidates = sorted(
        (
            _stream_queue_completed_at.get(
                session_id,
                _stream_queue_created_at.get(session_id, timestamp),
            ),
            session_id,
        )
        for session_id in _stream_queues
        if session_id not in _stream_consumers
        and session_id not in _active_pipeline_sessions
    )
    for _, session_id in candidates[:overflow]:
        _drop_stream_queue(session_id)


def _mark_stream_queue_complete(session_id: str) -> None:
    if session_id in _stream_queues:
        completed_at = monotonic()
        _stream_queue_completed_at[session_id] = completed_at
        existing_handle = _stream_cleanup_handles.pop(session_id, None)
        if existing_handle is not None:
            existing_handle.cancel()
        loop = asyncio.get_running_loop()
        _stream_cleanup_handles[session_id] = loop.call_later(
            settings.server.stream_queue_ttl_seconds,
            _expire_stream_queue,
            session_id,
            completed_at,
        )


def _expire_stream_queue(session_id: str, completed_at: float) -> None:
    if (
        _stream_queue_completed_at.get(session_id) == completed_at
        and session_id not in _stream_consumers
        and session_id not in _active_pipeline_sessions
    ):
        _drop_stream_queue(session_id)


def _get_or_create_queue(session_id: str) -> asyncio.Queue:
    existing = _stream_queues.get(session_id)
    if existing is not None:
        return existing
    _prune_stream_queues()
    if len(_stream_queues) >= settings.server.stream_queue_max_size:
        raise RuntimeError("The stream queue capacity has been reached.")
    queue = asyncio.Queue()
    _stream_queues[session_id] = queue
    _stream_queue_created_at[session_id] = monotonic()
    return queue


async def _event_generator(session_id: str) -> AsyncGenerator[str, None]:
    queue = _stream_queues.get(session_id)
    if queue is None:
        yield f"data: {json.dumps({'status': 'ERROR', 'session_id': session_id, 'message': 'Stream session not found.'})}\n\n"
        return
    _stream_consumers.add(session_id)
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    queue.get(), timeout=float(settings.sse_timeout_seconds)
                )
                if data is None:
                    yield f"data: {json.dumps({'status': 'COMPLETE', 'session_id': session_id})}\n\n"
                    break
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'status': 'TIMEOUT', 'session_id': session_id})}\n\n"
                break
    finally:
        _stream_consumers.discard(session_id)
        _drop_stream_queue(session_id)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are accepted."},
        )

    session_id = create_session_id()
    if not await _reserve_pipeline_slot(session_id):
        return JSONResponse(
            status_code=429,
            content={"error": "The active document processing limit has been reached."},
            headers={"Retry-After": "30"},
        )
    safe_filename = Path(file.filename).name
    pdf_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    try:
        await _save_uploaded_pdf(file, pdf_path)
    except UploadTooLargeError:
        await _release_pipeline_slot(session_id)
        return JSONResponse(
            status_code=413,
            content={"error": f"File size exceeds maximum allowed size ({_MAX_UPLOAD_SIZE // (1024*1024)} MB)."},
        )
    except ValueError as error:
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=400, content={"error": str(error)})
    except Exception:
        await _release_pipeline_slot(session_id)
        raise

    try:
        status_queue = _get_or_create_queue(session_id)
    except RuntimeError as error:
        pdf_path.unlink(missing_ok=True)
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=503, content={"error": str(error)})

    asyncio.create_task(
        process_pdf_pipeline(
            pdf_path,
            session_id,
            file.filename,
            status_queue,
        )
    )

    return JSONResponse(
        content={
            "session_id": session_id,
            "filename": file.filename,
            "status_endpoint": f"/api/status/{session_id}",
            "stream_endpoint": f"/api/stream/{session_id}",
        }
    )


@router.get("/stream/{session_id}")
async def stream_status(session_id: str):
    if session_id not in _stream_queues:
        return JSONResponse(
            status_code=404,
            content={"error": f"No stream found for session {session_id}"},
        )
    return StreamingResponse(
        _event_generator(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    result = _processing_store.get(session_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No processing found for session {session_id}"},
        )
    return JSONResponse(content=result.model_dump(mode="json"))


async def _save_instruction(
    session_id: str,
    request: SaveInstructionRequest,
    approve: bool,
):
    if session_id not in _session_models:
        return JSONResponse(
            status_code=404,
            content={"error": f"No processing found for session {session_id}"},
        )
    async with _get_session_lock(session_id):
        return await _save_instruction_locked(session_id, request, approve)


async def _save_instruction_locked(
    session_id: str,
    request: SaveInstructionRequest,
    approve: bool,
):
    if session_id not in _session_models:
        return JSONResponse(
            status_code=404,
            content={"error": f"No processing found for session {session_id}"},
        )

    instruction = request.shipping_instruction.model_copy(deep=True)
    instruction.document_status_code = (
        DocumentStatusCode.FINAL if approve else DocumentStatusCode.DRAFT
    )
    xml_content = await _run_blocking(shipping_instruction_to_xml, instruction)
    is_xsd_valid, errors = await _run_blocking(validate_xml_against_xsd, xml_content)
    missing_fields = check_mandatory_fields(instruction)
    stored_result = _processing_store.get(session_id)
    ocr_text = stored_result.raw_ocr_text if stored_result and stored_result.raw_ocr_text else ""
    local_assessment = assess_local_result(
        instruction,
        ocr_text,
        is_xsd_valid,
        errors,
        missing_fields,
    )
    revision_summary = (
        "Veri duzenlendi; DeepSeek yeniden cagrilmadi. Yerel kontroller guncellendi."
    )
    review_data = _local_review_data(local_assessment, revision_summary)

    if approve and (not is_xsd_valid or missing_fields):
        instruction.document_status_code = DocumentStatusCode.DRAFT
        xml_content = await _run_blocking(shipping_instruction_to_xml, instruction)
        return JSONResponse(
            status_code=422,
            content={
                "error": "Mandatory fields or XSD validation errors prevent approval.",
                "xml_content": xml_content,
                "validation_errors": errors,
                "missing_fields": [field.model_dump(mode="json") for field in missing_fields],
                **review_data,
            },
        )

    status = ProcessingStatus.COMPLETED if approve else ProcessingStatus.DRAFT
    _session_models[session_id] = instruction
    log_user_revision(
        session_id,
        action="approved" if approve else "draft",
        instruction_data=instruction.model_dump(mode="json"),
        xml_content=xml_content,
        is_valid=is_xsd_valid,
        errors=errors,
        missing_fields=[field.model_dump(mode="json") for field in missing_fields],
    )
    log_cloud_review_report(
        session_id,
        local_assessment=local_assessment.model_dump(mode="json"),
        cloud_review_used=False,
        label="approved" if approve else "draft",
    )
    result_data = {
        "xml_content": xml_content,
        "raw_llm_json": instruction.model_dump_json(),
        "structured_data": instruction.model_dump(mode="json"),
        "validation_errors": errors,
        "missing_fields": [field.model_dump(mode="json") for field in missing_fields],
        **review_data,
    }
    _emit_status(
        session_id,
        status,
        "Veriler onaylandi." if approve else "Taslak kaydedildi.",
        data=result_data,
    )
    return JSONResponse(content=_processing_store[session_id].model_dump(mode="json"))


@router.put("/sessions/{session_id}/draft")
async def save_draft(session_id: str, request: SaveInstructionRequest):
    return await _save_instruction(session_id, request, approve=False)


@router.post("/sessions/{session_id}/approve")
async def approve_instruction(session_id: str, request: SaveInstructionRequest):
    return await _save_instruction(session_id, request, approve=True)


@router.post("/sessions/{session_id}/cloud-review")
async def run_manual_cloud_review(session_id: str):
    if session_id not in _session_models or session_id not in _processing_store:
        return JSONResponse(
            status_code=404,
            content={"error": f"No processing found for session {session_id}"},
        )
    async with _get_session_lock(session_id):
        return await _run_manual_cloud_review_locked(session_id)


async def _run_manual_cloud_review_locked(session_id: str):
    instruction = _session_models.get(session_id)
    stored_result = _processing_store.get(session_id)
    if instruction is None or stored_result is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No processing found for session {session_id}"},
        )
    if not settings.deepseek.api_key:
        return JSONResponse(
            status_code=503,
            content={"error": "DEEPSEEK_API_KEY is not configured."},
        )
    if settings.deepseek.review_mode == "off":
        return JSONResponse(
            status_code=403,
            content={"error": "Cloud review is disabled by DEEPSEEK_REVIEW_MODE."},
        )
    if stored_result.cloud_review_used:
        return JSONResponse(content=stored_result.model_dump(mode="json"))

    xml_content = await _run_blocking(shipping_instruction_to_xml, instruction)
    is_xsd_valid, errors = await _run_blocking(validate_xml_against_xsd, xml_content)
    missing_fields = check_mandatory_fields(instruction)
    assessment = assess_local_result(
        instruction,
        stored_result.raw_ocr_text or "",
        is_xsd_valid,
        errors,
        missing_fields,
    )
    try:
        async with cloud_review_semaphore:
            latest_result = _processing_store.get(session_id)
            if latest_result and latest_result.cloud_review_used:
                return JSONResponse(content=latest_result.model_dump(mode="json"))
            review_data, _ = await _execute_cloud_review(
                session_id,
                instruction,
                assessment,
                stored_result.raw_ocr_text or "",
                "manual",
            )
    except Exception as error:
        log_cloud_review_report(
            session_id,
            local_assessment=assessment.model_dump(mode="json"),
            cloud_review_used=False,
            error=str(error),
            label="manual",
        )
        return JSONResponse(
            status_code=502,
            content={"error": f"Cloud review failed: {error}"},
        )

    latest_result = _processing_store.get(session_id)
    current_status = latest_result.status if latest_result else stored_result.status
    _emit_status(
        session_id,
        current_status,
        "DeepSeek kisa denetimi tamamlandi.",
        data=review_data,
    )
    return JSONResponse(content=_processing_store[session_id].model_dump(mode="json"))


@router.post("/upload-and-stream")
async def upload_and_stream(
    file: UploadFile = File(...),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are accepted."},
        )

    session_id = create_session_id()
    if not await _reserve_pipeline_slot(session_id):
        return JSONResponse(
            status_code=429,
            content={"error": "The active document processing limit has been reached."},
            headers={"Retry-After": "30"},
        )
    safe_filename = Path(file.filename).name
    pdf_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    try:
        await _save_uploaded_pdf(file, pdf_path)
    except UploadTooLargeError:
        await _release_pipeline_slot(session_id)
        return JSONResponse(
            status_code=413,
            content={"error": f"File size exceeds maximum allowed size ({_MAX_UPLOAD_SIZE // (1024*1024)} MB)."},
        )
    except ValueError as error:
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=400, content={"error": str(error)})
    except Exception:
        await _release_pipeline_slot(session_id)
        raise

    try:
        queue = _get_or_create_queue(session_id)
    except RuntimeError as error:
        pdf_path.unlink(missing_ok=True)
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=503, content={"error": str(error)})

    asyncio.create_task(
        process_pdf_pipeline(
            pdf_path,
            session_id,
            file.filename,
            queue,
        )
    )

    return StreamingResponse(
        _event_generator(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
