from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Header, HTTPException, Request

from app.config import settings


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        now: Optional[float] = None,
    ) -> Optional[int]:
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - window_seconds
        async with self._lock:
            if len(self._events) >= 1000:
                stale_keys = [
                    event_key
                    for event_key, event_times in self._events.items()
                    if not event_times or event_times[-1] <= cutoff
                ]
                for event_key in stale_keys:
                    self._events.pop(event_key, None)
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, int(window_seconds - (timestamp - events[0])))
            events.append(timestamp)
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._events.clear()


upload_rate_limiter = SlidingWindowRateLimiter()


async def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_cerberus_api_key: Optional[str] = Header(default=None),
) -> None:
    expected = settings.server.api_key
    if not expected:
        return
    supplied = x_cerberus_api_key
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail="A valid CerberusVision API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def enforce_upload_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    retry_after = await upload_rate_limiter.check(
        client_host,
        settings.server.upload_rate_limit,
        settings.server.upload_rate_window_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Upload rate limit exceeded.",
            headers={"Retry-After": str(retry_after)},
        )
