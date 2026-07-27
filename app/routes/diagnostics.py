from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import platform
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.config import settings
from app.security import require_api_key

router = APIRouter(
    prefix="/api/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(require_api_key)],
)

logger = logging.getLogger("cerberus.diagnostics")

_benchmark_result: dict | None = None
_benchmark_running = False
_benchmark_lock = asyncio.Lock()
_benchmark_progress_queues: list[asyncio.Queue] = []

try:
    from openvino import Core
    _openvino_core = Core()
except ImportError:
    _openvino_core = None


@router.get("/health-check")
async def health_check():
    modules_to_check = [
        "fastapi",
        "openvino",
        "openvino_genai",
        "paddleocr",
        "fitz",
        "transformers",
        "peft",
    ]
    module_availability = {}
    for module_name in modules_to_check:
        module_availability[module_name] = importlib.util.find_spec(module_name) is not None

    available_openvino_devices: list[str] = []
    if _openvino_core is not None:
        try:
            available_openvino_devices = list(_openvino_core.available_devices)
        except Exception:
            pass

    model_path_object = Path(settings.model.model_path)
    model_directory_exists = model_path_object.exists()

    requested_gpu_device = settings.model.device
    gpu_device_available = any(
        device.startswith("GPU") for device in available_openvino_devices
    )

    all_critical_modules_present = all(module_availability.values())
    system_is_healthy = all_critical_modules_present and model_directory_exists

    return JSONResponse({
        "python_version": sys.version,
        "platform": platform.platform(),
        "modules": module_availability,
        "openvino_devices": available_openvino_devices,
        "model_path": {"path": str(model_path_object), "exists": model_directory_exists},
        "gpu_device": {"requested": requested_gpu_device, "available": gpu_device_available},
        "status": "healthy" if system_is_healthy else "degraded",
    })


@router.get("/gpu-info")
async def gpu_info():
    try:
        if _openvino_core is None:
            return JSONResponse({"message": "OpenVINO yuklu degil veya calismiyor", "devices": []})

        gpu_device_names = [d for d in _openvino_core.available_devices if d.startswith("GPU")]
        if not gpu_device_names:
            return JSONResponse({"message": "GPU cihazi bulunamadi", "devices": []})

        gpu_device_details = []
        for device_name in gpu_device_names:
            device_properties: dict = {}
            try:
                supported_property_keys = _openvino_core.get_property(device_name, "SUPPORTED_PROPERTIES")
                for property_key in supported_property_keys:
                    try:
                        raw_value = _openvino_core.get_property(device_name, property_key)
                        device_properties[property_key] = str(raw_value)
                    except Exception:
                        pass
            except Exception:
                pass
            gpu_device_details.append({"name": device_name, "properties": device_properties})
        return JSONResponse({"devices": gpu_device_details})
    except Exception as openvino_error:
        return JSONResponse({"message": str(openvino_error), "devices": []})


async def _broadcast_benchmark_event(event: dict) -> None:
    dead_queues = []
    for queue in _benchmark_progress_queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead_queues.append(queue)
    for dead_queue in dead_queues:
        if dead_queue in _benchmark_progress_queues:
            _benchmark_progress_queues.remove(dead_queue)


async def _run_benchmark_task() -> None:
    global _benchmark_running, _benchmark_result

    benchmark_script_path = str(settings.base_dir / "scripts" / "benchmark_accuracy.py")
    benchmark_fixtures_directory = str(settings.base_dir / "tests" / "fixtures" / "qwen_benchmark")
    json_output_path = settings.logs_dir / "benchmark_latest.json"
    html_output_path = settings.logs_dir / "benchmark_latest.html"

    try:
        await _broadcast_benchmark_event({"status": "running", "progress": 0, "message": "Benchmark baslatiliyor..."})

        benchmark_process = await asyncio.create_subprocess_exec(
            sys.executable,
            benchmark_script_path,
            benchmark_fixtures_directory,
            "--output", str(json_output_path),
            "--html", str(html_output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        completed_cases = 0
        total_cases = 13

        while benchmark_process.stdout:
            line_bytes = await benchmark_process.stdout.readline()
            if not line_bytes:
                break
            decoded_line = line_bytes.decode("utf-8", errors="replace").strip()
            if not decoded_line:
                continue

            if "PASS" in decoded_line or "FAIL" in decoded_line or "ERROR" in decoded_line:
                completed_cases += 1
                progress_percentage = min(100, int((completed_cases / total_cases) * 100))
                await _broadcast_benchmark_event({
                    "status": "running",
                    "progress": progress_percentage,
                    "completed": completed_cases,
                    "total": total_cases,
                    "current_case": decoded_line[:120],
                })

        await benchmark_process.wait()

        if json_output_path.exists():
            _benchmark_result = json.loads(json_output_path.read_text(encoding="utf-8"))
            await _broadcast_benchmark_event({"status": "done", "result": _benchmark_result})
        else:
            await _broadcast_benchmark_event({"status": "error", "message": "Sonuc dosyasi olusturulamadi"})

    except Exception as benchmark_error:
        logger.exception("Benchmark hatasi: %s", benchmark_error)
        await _broadcast_benchmark_event({"status": "error", "message": str(benchmark_error)})
    finally:
        _benchmark_running = False


@router.post("/benchmark")
async def start_benchmark():
    global _benchmark_running

    if _benchmark_running:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Benchmark zaten calisiyor"},
        )

    from app.routes.processing import _active_pipeline_sessions, _batch_tasks

    active_batch_exists = any(not task.done() for task in _batch_tasks.values())
    if _active_pipeline_sessions or active_batch_exists:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Aktif belge isleme hatti var, benchmark baslatilamaz"},
        )

    _benchmark_running = True
    asyncio.create_task(_run_benchmark_task())

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "started"},
    )


@router.get("/benchmark/stream")
async def benchmark_stream():
    progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _benchmark_progress_queues.append(progress_queue)

    async def sse_event_generator():
        try:
            while True:
                event_data = await asyncio.wait_for(progress_queue.get(), timeout=600)
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                if event_data.get("status") in ("done", "error", "timeout"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'status': 'timeout'})}\n\n"
        finally:
            if progress_queue in _benchmark_progress_queues:
                _benchmark_progress_queues.remove(progress_queue)

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.get("/benchmark/result")
async def benchmark_result():
    if _benchmark_result is not None:
        return JSONResponse(_benchmark_result)

    json_output_path = settings.logs_dir / "benchmark_latest.json"
    if json_output_path.exists():
        try:
            return JSONResponse(json.loads(json_output_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Benchmark sonucu bulunamadi")


@router.get("/benchmark/download-html")
async def download_benchmark_html():
    html_report_path = settings.logs_dir / "benchmark_latest.html"
    if html_report_path.exists():
        return FileResponse(
            path=str(html_report_path),
            filename="benchmark_report.html",
            media_type="text/html",
        )
    raise HTTPException(status_code=404, detail="HTML rapor bulunamadi")


@router.get("/benchmark/download-json")
async def download_benchmark_json():
    json_report_path = settings.logs_dir / "benchmark_latest.json"
    if json_report_path.exists():
        return FileResponse(
            path=str(json_report_path),
            filename="benchmark_report.json",
            media_type="application/json",
        )
    raise HTTPException(status_code=404, detail="JSON rapor bulunamadi")


@router.post("/compare/{session_id}")
async def compare_session_with_cloud(session_id: str):
    from app.routes.processing import _processing_store, _session_models
    from app.utils.audit_logger import SESSION_ID_PATTERN

    if not SESSION_ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Gecersiz oturum kimliği")

    if session_id not in _processing_store:
        raise HTTPException(status_code=404, detail="Oturum bulunamadi")

    stored_result = _processing_store[session_id]
    stored_model = _session_models.get(session_id)

    local_extracted_data = {}
    if hasattr(stored_result, "extracted_data"):
        local_extracted_data = stored_result.extracted_data or {}
    elif isinstance(stored_result, dict):
        local_extracted_data = stored_result.get("extracted_data", {})

    cloud_review_data = {}
    if isinstance(stored_result, dict):
        cloud_review_data = stored_result.get("cloud_review", {})
    elif hasattr(stored_result, "cloud_review"):
        cloud_review_data = stored_result.cloud_review or {}

    return JSONResponse({
        "session_id": session_id,
        "local_extraction": local_extracted_data,
        "cloud_review": cloud_review_data,
        "has_cloud_review": bool(cloud_review_data),
    })
