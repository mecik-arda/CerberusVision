from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.security import require_api_key

router = APIRouter(
    prefix="/api/discovery",
    tags=["discovery"],
    dependencies=[Depends(require_api_key)],
)

logger = logging.getLogger("cerberus.discovery")

_discovery_results: list[dict] = []
_discovery_running = False
_discovery_lock = asyncio.Lock()
_discovery_progress_queues: list[asyncio.Queue] = []


class DiscoverySearchRequest(BaseModel):
    query: str = Field(max_length=500)
    provider: str = Field(default="auto")
    max_results: int = Field(default=10, ge=1, le=50)


async def _broadcast_discovery_event(event: dict) -> None:
    dead_queues = []
    for queue in _discovery_progress_queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead_queues.append(queue)
    for dead_queue in dead_queues:
        if dead_queue in _discovery_progress_queues:
            _discovery_progress_queues.remove(dead_queue)


async def _run_discovery_task(search_request: DiscoverySearchRequest) -> None:
    global _discovery_running, _discovery_results

    discovery_script_path = str(settings.base_dir / "scripts" / "find_shipping_documents.py")
    output_directory = str(settings.document_search.output_dir)

    resolved_provider = search_request.provider
    if resolved_provider == "auto":
        if settings.document_search.brave_api_key:
            resolved_provider = "brave"
        elif settings.document_search.google_api_key:
            resolved_provider = "google"
        else:
            resolved_provider = "brave"

    command_arguments = [
        sys.executable,
        discovery_script_path,
        "--provider", resolved_provider,
        "--max-results", str(search_request.max_results),
        "--output-dir", output_directory,
        "--json",
    ]

    if search_request.query:
        command_arguments.extend(["--query", search_request.query])

    environment_variables = dict()
    import os
    environment_variables.update(os.environ)

    if settings.document_search.brave_api_key:
        environment_variables["BRAVE_SEARCH_API_KEY"] = settings.document_search.brave_api_key
    if settings.document_search.google_api_key:
        environment_variables["GOOGLE_SEARCH_API_KEY"] = settings.document_search.google_api_key
    if settings.document_search.google_engine_id:
        environment_variables["GOOGLE_SEARCH_ENGINE_ID"] = settings.document_search.google_engine_id
    if settings.deepseek.api_key:
        environment_variables["DEEPSEEK_API_KEY"] = settings.deepseek.api_key

    try:
        await _broadcast_discovery_event({
            "status": "running",
            "progress": 0,
            "message": "Arama baslatiliyor...",
        })

        discovery_process = await asyncio.create_subprocess_exec(
            *command_arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment_variables,
        )

        raw_output_lines: list[str] = []
        while discovery_process.stdout:
            line_bytes = await discovery_process.stdout.readline()
            if not line_bytes:
                break
            decoded_line = line_bytes.decode("utf-8", errors="replace").strip()
            if decoded_line:
                raw_output_lines.append(decoded_line)
                await _broadcast_discovery_event({
                    "status": "running",
                    "message": decoded_line[:200],
                })

        await discovery_process.wait()

        parsed_results: list[dict] = []
        full_output = "\n".join(raw_output_lines)
        try:
            json_output = json.loads(full_output)
            if isinstance(json_output, list):
                parsed_results = json_output
            elif isinstance(json_output, dict) and "results" in json_output:
                parsed_results = json_output["results"]
        except json.JSONDecodeError:
            for single_line in raw_output_lines:
                try:
                    line_json = json.loads(single_line)
                    if isinstance(line_json, dict):
                        parsed_results.append(line_json)
                except json.JSONDecodeError:
                    continue

        _discovery_results = parsed_results
        await _broadcast_discovery_event({
            "status": "done",
            "total_found": len(parsed_results),
        })

    except Exception as discovery_error:
        logger.exception("Belge kesif hatasi: %s", discovery_error)
        await _broadcast_discovery_event({
            "status": "error",
            "message": str(discovery_error),
        })
    finally:
        _discovery_running = False


@router.post("/search")
async def start_discovery_search(request: DiscoverySearchRequest):
    global _discovery_running, _discovery_results

    if _discovery_running:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Arama zaten devam ediyor"},
        )

    valid_providers = {"auto", "brave", "google"}
    if request.provider not in valid_providers:
        return JSONResponse(
            status_code=422,
            content={"error": "Gecersiz saglayici. Kullanilabilir: auto, brave, google"},
        )

    has_brave_key = bool(settings.document_search.brave_api_key)
    has_google_key = bool(settings.document_search.google_api_key)

    if request.provider == "brave" and not has_brave_key:
        return JSONResponse(
            status_code=422,
            content={"error": "Brave Search API anahtari ayarlanmamis. Ayarlar panelinden giriniz."},
        )
    if request.provider == "google" and not has_google_key:
        return JSONResponse(
            status_code=422,
            content={"error": "Google Search API anahtari ayarlanmamis. Ayarlar panelinden giriniz."},
        )
    if request.provider == "auto" and not has_brave_key and not has_google_key:
        return JSONResponse(
            status_code=422,
            content={"error": "Hicbir arama API anahtari ayarlanmamis. Ayarlar panelinden bir anahtar giriniz."},
        )

    _discovery_running = True
    _discovery_results = []
    asyncio.create_task(_run_discovery_task(request))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "started"},
    )


@router.get("/search/stream")
async def discovery_search_stream():
    progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _discovery_progress_queues.append(progress_queue)

    async def sse_event_generator():
        try:
            while True:
                event_data = await asyncio.wait_for(progress_queue.get(), timeout=300)
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                if event_data.get("status") in ("done", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'status': 'timeout'})}\n\n"
        finally:
            if progress_queue in _discovery_progress_queues:
                _discovery_progress_queues.remove(progress_queue)

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.get("/results")
async def get_discovery_results():
    return JSONResponse({
        "results": _discovery_results,
        "total": len(_discovery_results),
        "is_searching": _discovery_running,
    })


@router.post("/accept/{file_index}")
async def accept_discovered_file(file_index: int):
    if file_index < 0 or file_index >= len(_discovery_results):
        raise HTTPException(status_code=404, detail="Dosya bulunamadi")

    target_file_info = _discovery_results[file_index]

    file_path_str = target_file_info.get("local_path", target_file_info.get("path", ""))
    if not file_path_str:
        raise HTTPException(status_code=400, detail="Dosya yolu eksik")

    source_path = Path(file_path_str)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Dosya diskte bulunamadi")

    accepted_directory = Path(settings.document_search.output_dir) / "accepted"
    accepted_directory.mkdir(parents=True, exist_ok=True)

    destination_path = accepted_directory / f"{source_path.stem}_{int(time.time())}{source_path.suffix}"
    import shutil
    shutil.move(str(source_path), str(destination_path))

    target_file_info["status"] = "accepted"
    target_file_info["accepted_path"] = str(destination_path)

    return JSONResponse({
        "status": "accepted",
        "filename": source_path.name,
        "accepted_path": str(destination_path),
    })
