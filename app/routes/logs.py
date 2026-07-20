from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.security import require_api_key
from app.utils.live_logs import live_log_buffer


router = APIRouter(
    prefix="/api",
    tags=["logs"],
    dependencies=[Depends(require_api_key)],
)


def _parse_last_event_id(value: str | None) -> int:
    try:
        return max(0, int(value or 0))
    except ValueError:
        return 0


def _encode_sse_entry(entry: dict) -> str:
    payload = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    return f"id: {entry['id']}\nevent: log\ndata: {payload}\n\n"


@router.get("/logs")
async def list_logs(
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
):
    return JSONResponse(
        content={"entries": live_log_buffer.snapshot(after_id=after_id, limit=limit)}
    )


@router.delete("/logs")
async def clear_logs():
    return JSONResponse(content={"cleared": live_log_buffer.clear()})


@router.get("/logs/stream")
async def stream_logs(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    initial_after_id = _parse_last_event_id(last_event_id)

    async def generate_events():
        queue = live_log_buffer.subscribe()
        emitted_id = initial_after_id
        try:
            for entry in live_log_buffer.snapshot(after_id=initial_after_id):
                emitted_id = max(emitted_id, entry["id"])
                yield _encode_sse_entry(entry)
            while not await request.is_disconnected():
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if entry["id"] <= emitted_id:
                    continue
                emitted_id = entry["id"]
                yield _encode_sse_entry(entry)
        finally:
            live_log_buffer.unsubscribe(queue)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
