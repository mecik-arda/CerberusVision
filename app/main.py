from __future__ import annotations
from pathlib import Path
import importlib.util
from functools import lru_cache
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.routes.processing import router as processing_router


app = FastAPI(
    title="CerberusVision",
    description="Konşimento Talimatı İşleme Sistemi",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(processing_router)


@lru_cache(maxsize=1)
def _get_openvino_devices() -> tuple[str, ...]:
    from openvino import Core

    return tuple(Core().available_devices)


@app.get("/")
async def root():
    index_path = settings.static_dir / "index.html"
    return FileResponse(
        str(index_path),
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/health")
async def health():
    dependency_checks = {
        "paddleocr": importlib.util.find_spec("paddleocr") is not None,
        "pymupdf": importlib.util.find_spec("fitz") is not None,
        "openvino_genai": importlib.util.find_spec("openvino_genai") is not None,
    }
    model_path = Path(settings.model.model_path)
    devices = []
    device_ready = False
    try:
        devices = list(_get_openvino_devices())
        requested_device = settings.model.device.split(".", 1)[0].upper()
        device_ready = any(
            device.split(".", 1)[0].upper() == requested_device for device in devices
        )
    except Exception:
        device_ready = False

    checks = {
        "dependencies": dependency_checks,
        "model_path": {"ready": model_path.exists(), "path": str(model_path)},
        "openvino_device": {
            "ready": device_ready,
            "requested": settings.model.device,
            "available": devices,
        },
        "deepseek": {
            "configured": bool(settings.deepseek.api_key),
            "required": False,
            "review_mode": settings.deepseek.review_mode,
            "risk_threshold": settings.deepseek.risk_threshold,
        },
    }
    ready = all(dependency_checks.values()) and model_path.exists() and device_ready
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": "CerberusVision",
            "checks": checks,
        },
    )
