"""Outbound webhook to deliver approved DCSA XML to external systems.

Fire-and-forget with exponential backoff retry. Failures are logged
but never block the approval flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("cerberus.webhook")

_MAX_RETRIES = 3
_BACKOFF_SECONDS = 2.0
_TIMEOUT_SECONDS = 30


def webhook_log_path(session_id: str) -> Path:
    return settings.logs_dir / session_id / "webhook_delivery.json"


def log_webhook_attempt(session_id: str, attempt: int, status: str, detail: str) -> None:
    record = {
        "session_id": session_id,
        "attempt": attempt,
        "status": status,
        "detail": detail,
    }
    log_path = webhook_log_path(session_id)
    tmp_path = log_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, log_path)


async def deliver_approved_xml(
    session_id: str,
    xml_content: str,
    shipping_instruction: dict,
) -> bool:
    """Send approved DCSA XML to configured webhook endpoint.

    Returns True on success, False after exhausted retries.
    """
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        return False
    if not webhook_url.startswith("https://") and not webhook_url.startswith("http://localhost"):
        logger.warning("Webhook URL must use HTTPS (or localhost for testing)")
        return False
    env = os.environ.get("ENVIRONMENT", "development").lower()
    if env == "production" and webhook_url.startswith("http://localhost"):
        logger.warning("Webhook localhost is blocked in production environment")
        return False
    if env == "production":
        blocked = ("http://10.", "http://192.168.", "http://172.16.", "http://127.")
        if any(webhook_url.startswith(prefix) for prefix in blocked):
            logger.warning("Webhook internal IP is blocked in production environment")
            return False

    api_key = os.environ.get("WEBHOOK_API_KEY")
    enabled = os.environ.get("WEBHOOK_ENABLED", "0") == "1"
    if not enabled:
        return False

    payload = {
        "session_id": session_id,
        "status": "approved",
        "dcsa_xml": xml_content,
        "metadata": {
            "shipping_instruction_reference": shipping_instruction.get(
                "shipping_instruction_reference"
            ),
            "carrier_booking_reference": shipping_instruction.get(
                "carrier_booking_reference"
            ),
        },
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)
                if 200 <= response.status_code < 300:
                    log_webhook_attempt(
                        session_id, attempt, "success",
                        f"HTTP {response.status_code}",
                    )
                    logger.info(
                        "Webhook delivered for session %s (attempt %d/%d)",
                        session_id, attempt, _MAX_RETRIES,
                    )
                    return True
                detail = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            detail = str(exc)[:200]

        log_webhook_attempt(session_id, attempt, "failed", detail)
        logger.warning(
            "Webhook attempt %d/%d failed for session %s: %s",
            attempt, _MAX_RETRIES, session_id, detail,
        )
        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    return False
