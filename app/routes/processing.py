from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from app.config import settings
from app.models import ProcessingStatus, ProcessingResult
from app.utils.audit_logger import (
    create_session_id,
    log_ocr_result,
    log_llm_result,
    log_xml_result,
    log_validation_report,
    log_processing_summary,
)

from app.ocr.spatial_ocr import process_pdf_with_spatial_ocr
from app.llm.inference import run_inference_with_fallback
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import validate_and_grade

router = APIRouter(prefix="/api", tags=["processing"])

inference_semaphore = asyncio.Semaphore(1)

_processing_store: dict[str, ProcessingResult] = {}
_stream_queues: dict[str, asyncio.Queue] = {}


_PROCESSING_STORE_MAX_SIZE = 100


def _emit_status(session_id: str, status: ProcessingStatus, message: str, data: dict = None) -> str:
    payload = {
        "session_id": session_id,
        "status": status.value,
        "message": message,
    }
    if data:
        payload["data"] = data
        store_kwargs = {k: v for k, v in data.items() if k in ["xml_content", "raw_ocr_text", "raw_llm_json", "validation_errors", "missing_fields"]}
    else:
        store_kwargs = {}
    if len(_processing_store) >= _PROCESSING_STORE_MAX_SIZE:
        oldest_key = next(iter(_processing_store))
        _processing_store.pop(oldest_key, None)
    _processing_store[session_id] = ProcessingResult(
        status=status,
        message=message,
        **store_kwargs,
    )
    return json.dumps(payload, ensure_ascii=False)


async def _run_blocking(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def process_pdf_pipeline(
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
        ocr_path = log_ocr_result(session_id, ocr_text)

        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.LLM_ANALYZING, "LLM Analizi...",
            data={"raw_ocr_text": ocr_text},
        ))

        async with inference_semaphore:
            si_model, raw_llm_json = await _run_blocking(run_inference_with_fallback, ocr_text)
        llm_path = log_llm_result(session_id, raw_llm_json)

        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.XML_VALIDATING, "XML Dogrulaniyor...",
        ))

        xml_content = await _run_blocking(shipping_instruction_to_xml, si_model)
        xml_path = log_xml_result(session_id, xml_content)

        status, errors, missing_fields = await _run_blocking(validate_and_grade, si_model, xml_content)

        validation_path = log_validation_report(
            session_id,
            is_valid=(status == ProcessingStatus.COMPLETED),
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
        )

        result_data = {
            "xml_content": xml_content,
            "raw_ocr_text": ocr_text,
            "raw_llm_json": raw_llm_json,
            "validation_errors": errors,
            "missing_fields": [f.model_dump() for f in missing_fields],
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
        status_queue.put_nowait(None)


def _get_or_create_queue(session_id: str) -> asyncio.Queue:
    if session_id not in _stream_queues:
        _stream_queues[session_id] = asyncio.Queue()
    return _stream_queues[session_id]


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are accepted."},
        )

    session_id = create_session_id()
    safe_filename = Path(file.filename).name
    pdf_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    content = await file.read()
    pdf_path.write_bytes(content)

    status_queue = _get_or_create_queue(session_id)

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
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = _get_or_create_queue(session_id)

        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=300.0)
                    if data is None:
                        yield f"data: {json.dumps({'status': 'COMPLETE', 'session_id': session_id})}\n\n"
                        break
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'status': 'TIMEOUT', 'session_id': session_id})}\n\n"
                    break
        finally:
            _stream_queues.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
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
    return JSONResponse(content=result.model_dump())


@router.post("/upload-and-stream")
async def upload_and_stream(
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are accepted."},
        )

    session_id = create_session_id()
    safe_filename = Path(file.filename).name
    pdf_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    content = await file.read()
    pdf_path.write_bytes(content)

    queue = _get_or_create_queue(session_id)

    asyncio.create_task(
        process_pdf_pipeline(
            pdf_path,
            session_id,
            file.filename,
            queue,
        )
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=300.0)
                    if data is None:
                        yield f"data: {json.dumps({'status': 'COMPLETE', 'session_id': session_id})}\n\n"
                        break
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'status': 'TIMEOUT', 'session_id': session_id})}\n\n"
                    break
        finally:
            _stream_queues.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )