from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)([\"']?(?:api[_-]?key|token|secret)[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;}]+"
    ),
    re.compile(r"(?i)([?&](?:api[_-]?key|token|secret)=)[^&\s]+"),
)


def redact_log_message(message: Any) -> str:
    sanitized = str(message).replace("\r", " ").replace("\n", " ")
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", sanitized)
    return sanitized[:4000]


class LiveLogBuffer:
    def __init__(self, max_entries: int = 500, subscriber_queue_size: int = 250):
        self._entries: deque[dict] = deque(maxlen=max_entries)
        self._subscriber_queue_size = subscriber_queue_size
        self._subscribers: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    def publish(self, level: str, source: str, message: Any) -> dict:
        entry_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
            "level": str(level).upper(),
            "source": redact_log_message(source),
            "message": redact_log_message(message),
        }
        with self._lock:
            entry = {"id": self._next_id, **entry_data}
            self._next_id += 1
            self._entries.append(entry)
            subscribers = tuple(self._subscribers.items())
        for queue, event_loop in subscribers:
            try:
                event_loop.call_soon_threadsafe(self._deliver, queue, entry)
            except RuntimeError:
                self.unsubscribe(queue)
        return entry.copy()

    def snapshot(self, after_id: int = 0, limit: int = 500) -> list[dict]:
        normalized_limit = max(1, min(limit, self._entries.maxlen or limit))
        with self._lock:
            matching_entries = [
                entry.copy() for entry in self._entries if entry["id"] > after_id
            ]
        return matching_entries[-normalized_limit:]

    def clear(self) -> int:
        with self._lock:
            cleared_count = len(self._entries)
            self._entries.clear()
        return cleared_count

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=self._subscriber_queue_size)
        event_loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers[queue] = event_loop
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)

    @staticmethod
    def _deliver(queue: asyncio.Queue, entry: dict) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(entry.copy())
        except asyncio.QueueFull:
            pass


class LiveLogHandler(logging.Handler):
    def __init__(self, buffer: LiveLogBuffer | None = None):
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "cerberus_live_captured", False):
            return
        record.cerberus_live_captured = True
        try:
            target_buffer = self._buffer or live_log_buffer
            target_buffer.publish(record.levelname, record.name, record.getMessage())
        except Exception:
            self.handleError(record)


live_log_buffer = LiveLogBuffer()
_live_log_handler = LiveLogHandler()
_live_log_handler.setLevel(logging.NOTSET)


def install_live_log_handler() -> None:
    cerberus_logger = logging.getLogger("cerberus")
    cerberus_logger.setLevel(logging.INFO)
    for logger_name in ("", "cerberus", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target_logger = logging.getLogger(logger_name)
        if _live_log_handler not in target_logger.handlers:
            target_logger.addHandler(_live_log_handler)
