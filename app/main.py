from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.routes.processing import router as processing_router


app = FastAPI(
    title="CerberusVision",
    description="Konşimento Talimatı İşleme Sistemi",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(processing_router)


@app.get("/")
async def root():
    index_path = settings.static_dir / "index.html"
    return FileResponse(str(index_path))


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "CerberusVision"}