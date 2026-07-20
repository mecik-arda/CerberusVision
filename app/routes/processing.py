from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path
from time import monotonic
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from app.config import save_persistent_settings, settings
from app.security import enforce_upload_rate_limit, require_api_key
from app.models import (
    DocumentStatusCode,
    ProcessingStatus,
    ProcessingResult,
    RuntimeSettingsUpdate,
    SaveInstructionRequest,
    ShippingInstruction,
)
from app.document_ingestion import (
    DocumentValidationError,
    IMAGE_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    TEXT_DOCUMENT_EXTENSIONS,
    UploadSizeLimitError,
    copy_and_validate_upload,
    extract_text_document,
    validate_supported_filename,
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
from app.utils.model_discovery import discover_local_models

from app.ocr.spatial_ocr import (
    process_image_with_spatial_ocr,
    process_pdf_with_spatial_ocr,
)
from app.llm.inference import (
    reset_llm_pipeline,
    run_inference_with_fallback,
    run_refinement_with_fallback,
)
from app.llm.translation import translate_instruction_content
from app.llm.cloud_inference import run_deepseek_review
from app.llm.local_audit import assess_local_result, should_run_automatic_cloud_review
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import check_mandatory_fields, validate_xml_against_xsd

logger = logging.getLogger("cerberus.processing")

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
_SUPPORTED_DOCUMENT_LANGUAGES = {"auto", "tr", "en"}
_SUPPORTED_OUTPUT_LANGUAGES = {"tr", "en"}
_OCR_LANGUAGE_MAP = {"auto": "latin", "tr": "tr", "en": "en"}


UploadTooLargeError = UploadSizeLimitError


def _validate_processing_languages(
    document_language: str,
    output_language: str,
) -> tuple[str, str]:
    normalized_document_language = document_language.strip().lower()
    normalized_output_language = output_language.strip().lower()
    if normalized_document_language not in _SUPPORTED_DOCUMENT_LANGUAGES:
        raise ValueError("Document language must be 'auto', 'tr', or 'en'.")
    if normalized_output_language not in _SUPPORTED_OUTPUT_LANGUAGES:
        raise ValueError("Output language must be 'tr' or 'en'.")
    return normalized_document_language, normalized_output_language


def _runtime_settings_payload() -> dict:
    model_path = Path(settings.model.model_path)
    devices: list[str] = []
    try:
        from openvino import Core

        devices = list(Core().available_devices)
    except Exception:
        devices = []
    requested_device = settings.model.device.split(".", 1)[0].upper()
    device_ready = any(
        device.split(".", 1)[0].upper() == requested_device for device in devices
    )
    return {
        "local_model": {
            "name": model_path.name,
            "path": str(model_path),
            "device": settings.model.device,
            "available_devices": devices,
            "ready": model_path.exists() and device_ready,
            "max_new_tokens": settings.model.max_new_tokens,
            "kv_cache_precision": settings.model.kv_cache_precision,
        },
        "deepseek": {
            "model": settings.deepseek.model_name,
            "configured": bool(settings.deepseek.api_key),
            "review_mode": settings.deepseek.review_mode,
            "risk_threshold": settings.deepseek.risk_threshold,
        },
        "server": {
            "api_key_required": bool(settings.server.api_key),
        },
        "languages": {
            "document": sorted(_SUPPORTED_DOCUMENT_LANGUAGES),
            "output": sorted(_SUPPORTED_OUTPUT_LANGUAGES),
        },
        "interface": {
            "theme": settings.interface.theme,
            "interface_language": settings.interface.interface_language,
            "document_language": settings.interface.document_language,
            "output_language": settings.interface.output_language,
            "translation_enabled": settings.interface.translation_enabled,
        },
        "supported_formats": sorted(SUPPORTED_DOCUMENT_EXTENSIONS),
        "installed_models": discover_local_models(
            settings.base_dir,
            settings.model.model_path,
        ),
    }


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
    logger.info("session=%s status=%s %s", session_id, status.value, message)
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
    if validate_supported_filename(file.filename) != ".pdf":
        raise DocumentValidationError("The uploaded file is not a valid PDF.")
    copy_and_validate_upload(file, pdf_path, _MAX_UPLOAD_SIZE)


async def _save_uploaded_pdf(file: UploadFile, pdf_path: Path) -> None:
    await _run_blocking(_copy_upload_to_path, file, pdf_path)



async def _save_uploaded_document(file: UploadFile, document_path: Path) -> str:
    return await _run_blocking(
        copy_and_validate_upload,
        file,
        document_path,
        _MAX_UPLOAD_SIZE,
    )

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
    document_language: str = "en",
    output_language: str = "en",
    translation_enabled: bool = True,
):
    await process_document_pipeline(
        pdf_path,
        session_id,
        filename,
        status_queue,
        document_language,
        output_language,
        translation_enabled,
    )


async def process_document_pipeline(
    document_path: Path,
    session_id: str,
    filename: str,
    status_queue: asyncio.Queue,
    document_language: str = "en",
    output_language: str = "en",
    translation_enabled: bool = True,
):
    async with _get_session_lock(session_id):
        await _process_document_pipeline_locked(
            document_path,
            session_id,
            filename,
            status_queue,
            document_language,
            output_language,
            translation_enabled,
        )


async def _process_document_pipeline_locked(
    document_path: Path,
    session_id: str,
    filename: str,
    status_queue: asyncio.Queue,
    document_language: str,
    output_language: str,
    translation_enabled: bool,
):
    try:
        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.OCR_PROCESSING, "Belge icerigi isleniyor...",
        ))

        async with inference_semaphore:
            extension = validate_supported_filename(filename)
            if extension == ".pdf":
                ocr_text, boxes = await _run_blocking(
                    process_pdf_with_spatial_ocr,
                    document_path,
                    _OCR_LANGUAGE_MAP[document_language],
                )
            elif extension in IMAGE_EXTENSIONS:
                ocr_text, boxes = await _run_blocking(
                    process_image_with_spatial_ocr,
                    document_path,
                    _OCR_LANGUAGE_MAP[document_language],
                )
            elif extension in TEXT_DOCUMENT_EXTENSIONS:
                ocr_text = await _run_blocking(
                    extract_text_document, document_path, extension
                )
                boxes = []
            else:
                raise DocumentValidationError("Unsupported document type.")
        if not ocr_text.strip():
            raise DocumentValidationError("No readable text was found in the document.")
        boxes_data = [[asdict(box) for box in page_boxes] for page_boxes in boxes]
        ocr_path = log_ocr_result(session_id, ocr_text, boxes_data)

        status_queue.put_nowait(_emit_status(
            session_id, ProcessingStatus.LLM_ANALYZING, "LLM Analizi...",
            data={"raw_ocr_text": ocr_text},
        ))

        async with inference_semaphore:
            si_model, raw_llm_json = await _run_blocking(
                run_inference_with_fallback,
                ocr_text,
                document_language,
                output_language,
            )

        initial_xml = await _run_blocking(shipping_instruction_to_xml, si_model)
        initial_is_valid, initial_errors = await _run_blocking(
            validate_xml_against_xsd,
            initial_xml,
        )
        initial_missing_fields = check_mandatory_fields(si_model)
        initial_assessment = assess_local_result(
            si_model,
            ocr_text,
            initial_is_valid,
            initial_errors,
            initial_missing_fields,
        )
        refinement_raw_output = ""
        local_refinement_used = False
        if (
            settings.model.refinement_enabled
            and initial_assessment.risk_score
            >= settings.model.refinement_risk_threshold
        ):
            try:
                status_queue.put_nowait(_emit_status(
                    session_id,
                    ProcessingStatus.LLM_ANALYZING,
                    "Dusuk guvenli alanlar Qwen 7B ile yeniden dogrulaniyor...",
                ))
                async with inference_semaphore:
                    refined_model, refinement_raw_output = await _run_blocking(
                        run_refinement_with_fallback,
                        ocr_text,
                        si_model,
                        [
                            finding.model_dump(mode="json")
                            for finding in initial_assessment.findings
                        ],
                        document_language,
                    )
                refined_xml = await _run_blocking(
                    shipping_instruction_to_xml,
                    refined_model,
                )
                refined_is_valid, refined_errors = await _run_blocking(
                    validate_xml_against_xsd,
                    refined_xml,
                )
                refined_missing_fields = check_mandatory_fields(refined_model)
                refined_assessment = assess_local_result(
                    refined_model,
                    ocr_text,
                    refined_is_valid,
                    refined_errors,
                    refined_missing_fields,
                )
                if refined_assessment.risk_score < initial_assessment.risk_score:
                    si_model = refined_model
                    local_refinement_used = True
            except Exception as refinement_error:
                refinement_raw_output = json.dumps(
                    {"error": str(refinement_error)},
                    ensure_ascii=False,
                )

        translation_raw_output = ""
        if translation_enabled and document_language != output_language:
            try:
                status_queue.put_nowait(_emit_status(
                    session_id,
                    ProcessingStatus.LLM_ANALYZING,
                    "Aciklama alanlari hedef dile cevriliyor...",
                ))
                async with inference_semaphore:
                    si_model, translation_raw_output = await _run_blocking(
                        translate_instruction_content,
                        si_model,
                        output_language,
                    )
            except Exception as translation_error:
                translation_raw_output = json.dumps(
                    {"error": str(translation_error)},
                    ensure_ascii=False,
                )
        llm_path = log_llm_result(
            session_id,
            json.dumps(
                {
                    "extraction": raw_llm_json,
                    "refinement": refinement_raw_output,
                    "translation": translation_raw_output,
                },
                ensure_ascii=False,
            ),
        )
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
            "document_language": document_language,
            "output_language": output_language,
            "translation_enabled": translation_enabled,
            "local_refinement_used": local_refinement_used,
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
        document_path.unlink(missing_ok=True)
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


@router.get("/runtime-settings")
async def get_runtime_settings():
    return JSONResponse(content=_runtime_settings_payload())


@router.put("/runtime-settings")
async def update_runtime_settings(request: RuntimeSettingsUpdate):
    if request.clear_deepseek_api_key:
        settings.deepseek.api_key = None
    elif request.deepseek_api_key is not None:
        api_key = request.deepseek_api_key.get_secret_value().strip()
        if not api_key:
            return JSONResponse(
                status_code=422,
                content={"error": "DeepSeek API key cannot be empty."},
            )
        settings.deepseek.api_key = api_key
    if request.deepseek_review_mode is not None:
        settings.deepseek.review_mode = request.deepseek_review_mode
    if request.deepseek_risk_threshold is not None:
        settings.deepseek.risk_threshold = request.deepseek_risk_threshold
    if request.local_model_path is not None:
        requested_model_path = str(Path(request.local_model_path).resolve())
        installed_models = discover_local_models(
            settings.base_dir,
            settings.model.model_path,
        )
        selectable_paths = {
            model["path"]
            for model in installed_models
            if model.get("selectable")
        }
        if requested_model_path not in selectable_paths:
            return JSONResponse(
                status_code=422,
                content={"error": "Selected model is not a usable OpenVINO model."},
            )
        if requested_model_path != str(Path(settings.model.model_path).resolve()):
            settings.model.model_path = requested_model_path
            reset_llm_pipeline()
    if request.theme is not None:
        settings.interface.theme = request.theme
    if request.interface_language is not None:
        settings.interface.interface_language = request.interface_language
    if request.document_language is not None:
        settings.interface.document_language = request.document_language
    if request.output_language is not None:
        settings.interface.output_language = request.output_language
    if request.translation_enabled is not None:
        settings.interface.translation_enabled = request.translation_enabled
    save_persistent_settings()
    return JSONResponse(content=_runtime_settings_payload())


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    document_language: str = Form("en"),
    output_language: str = Form("en"),
    translation_enabled: bool = Form(True),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
):
    try:
        validate_supported_filename(file.filename)
    except DocumentValidationError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})
    try:
        document_language, output_language = _validate_processing_languages(
            document_language,
            output_language,
        )
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})

    session_id = create_session_id()
    if not await _reserve_pipeline_slot(session_id):
        return JSONResponse(
            status_code=429,
            content={"error": "The active document processing limit has been reached."},
            headers={"Retry-After": "30"},
        )
    safe_filename = Path(file.filename).name
    document_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    try:
        await _save_uploaded_document(file, document_path)
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
        document_path.unlink(missing_ok=True)
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=503, content={"error": str(error)})

    asyncio.create_task(
        process_document_pipeline(
            document_path,
            session_id,
            file.filename,
            status_queue,
            document_language,
            output_language,
            translation_enabled,
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
    document_language: str = Form("en"),
    output_language: str = Form("en"),
    translation_enabled: bool = Form(True),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
):
    try:
        validate_supported_filename(file.filename)
    except DocumentValidationError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})
    try:
        document_language, output_language = _validate_processing_languages(
            document_language,
            output_language,
        )
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})

    session_id = create_session_id()
    if not await _reserve_pipeline_slot(session_id):
        return JSONResponse(
            status_code=429,
            content={"error": "The active document processing limit has been reached."},
            headers={"Retry-After": "30"},
        )
    safe_filename = Path(file.filename).name
    document_path = settings.uploads_dir / f"{session_id}_{safe_filename}"
    try:
        await _save_uploaded_document(file, document_path)
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
        document_path.unlink(missing_ok=True)
        await _release_pipeline_slot(session_id)
        return JSONResponse(status_code=503, content={"error": str(error)})

    asyncio.create_task(
        process_document_pipeline(
            document_path,
            session_id,
            file.filename,
            queue,
            document_language,
            output_language,
            translation_enabled,
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
