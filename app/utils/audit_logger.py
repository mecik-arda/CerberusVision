from __future__ import annotations
import json
import re
import shutil
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Tuple
from app.config import settings


_SESSION_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}_\d{6}$")

_PII_FIELDS = {"party_name", "party_id", "email", "phone_number", "name",
               "street", "postal_code", "PartyName", "PartyID", "Email",
               "PhoneNumber", "Name", "Street", "PostalCode"}


def _mask_pii(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in _PII_FIELDS and isinstance(v, str) and v.strip():
                result[k] = v[:2] + "***" + v[-1] if len(v) > 3 else "***"
            else:
                result[k] = _mask_pii(v)
        return result
    if isinstance(data, list):
        return [_mask_pii(item) for item in data]
    return data
_last_cleanup_at: Optional[float] = None


def cleanup_expired_sessions(now: Optional[float] = None) -> int:
    timestamp = time.time() if now is None else now
    cutoff = timestamp - settings.server.log_retention_days * 86400
    removed = 0
    if not settings.logs_dir.exists():
        return removed
    for session_dir in settings.logs_dir.iterdir():
        try:
            if (
                session_dir.is_dir()
                and _SESSION_DIR_PATTERN.fullmatch(session_dir.name)
                and session_dir.stat().st_mtime < cutoff
            ):
                shutil.rmtree(session_dir)
                removed += 1
        except OSError:
            continue
    return removed


def _maybe_cleanup_expired_sessions() -> None:
    global _last_cleanup_at
    timestamp = time.monotonic()
    if _last_cleanup_at is not None and timestamp - _last_cleanup_at < 86400:
        return
    try:
        cleanup_expired_sessions()
    except OSError:
        pass
    _last_cleanup_at = timestamp


def create_session_id() -> str:
    _maybe_cleanup_expired_sessions()
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def get_session_dir(session_id: str) -> Path:
    session_dir = settings.logs_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def log_ocr_result(session_id: str, layout_text: str, boxes_data: Optional[Any] = None) -> Path:
    session_dir = get_session_dir(session_id)
    ocr_path = session_dir / "ocr_layout_text.txt"
    ocr_path.write_text(layout_text, encoding="utf-8")
    if boxes_data is not None:
        boxes_path = session_dir / "ocr_boxes.json"
        boxes_path.write_text(json.dumps(boxes_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return ocr_path


def log_llm_result(session_id: str, raw_json: str) -> Path:
    session_dir = get_session_dir(session_id)
    llm_path = session_dir / "llm_raw_output.json"
    llm_path.write_text(raw_json, encoding="utf-8")
    return llm_path


def log_xml_result(session_id: str, xml_content: str) -> Path:
    session_dir = get_session_dir(session_id)
    xml_path = session_dir / "shipping_instruction_output.xml"
    xml_path.write_text(xml_content, encoding="utf-8")
    return xml_path


def log_validation_report(
    session_id: str,
    is_valid: bool,
    errors: List[str],
    missing_fields: List[dict],
    status: str,
) -> Path:
    session_dir = get_session_dir(session_id)
    report = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "status": status,
        "xsd_valid": is_valid,
        "xsd_errors": errors,
        "missing_mandatory_fields": missing_fields,
    }
    report_path = session_dir / "validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path


def log_processing_summary(
    session_id: str,
    filename: str,
    status: str,
    ocr_path: Optional[str] = None,
    llm_path: Optional[str] = None,
    xml_path: Optional[str] = None,
    validation_path: Optional[str] = None,
    cloud_review_path: Optional[str] = None,
) -> Path:
    session_dir = get_session_dir(session_id)
    summary = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "filename": filename,
        "status": status,
        "artifacts": {
            "ocr_layout_text": ocr_path,
            "llm_raw_json": llm_path,
            "xml_output": xml_path,
            "validation_report": validation_path,
            "cloud_review_report": cloud_review_path,
        },
    }
    summary_path = session_dir / "processing_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary_path


def log_cloud_review_report(
    session_id: str,
    local_assessment: dict,
    cloud_review_used: bool,
    review: Optional[dict] = None,
    sent_payload: Optional[dict] = None,
    raw_output: Optional[str] = None,
    error: Optional[str] = None,
    label: str = "initial",
) -> Path:
    session_dir = get_session_dir(session_id)
    report = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "review_mode": settings.deepseek.review_mode,
        "risk_threshold": settings.deepseek.risk_threshold,
        "cloud_review_used": cloud_review_used,
        "local_assessment": local_assessment,
        "cloud_review": review,
        "sent_payload": sent_payload,
        "cloud_raw_output": raw_output,
        "error": error,
    }
    safe_label = label if label in {"initial", "manual", "draft", "approved"} else "initial"
    report_path = session_dir / f"{safe_label}_cloud_review_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report_path


def log_user_revision(
    session_id: str,
    action: str,
    instruction_data: dict,
    xml_content: str,
    is_valid: bool,
    errors: List[str],
    missing_fields: List[dict],
) -> Tuple[Path, Path, Path]:
    session_dir = get_session_dir(session_id)
    safe_action = "approved" if action == "approved" else "draft"
    json_path = session_dir / f"{safe_action}_instruction.json"
    xml_path = session_dir / f"{safe_action}_shipping_instruction.xml"
    validation_path = session_dir / f"{safe_action}_validation_report.json"
    json_path.write_text(
        json.dumps(_mask_pii(deepcopy(instruction_data)), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    xml_path.write_text(xml_content, encoding="utf-8")
    validation_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "action": safe_action,
                "xsd_valid": is_valid,
                "xsd_errors": errors,
                "missing_mandatory_fields": missing_fields,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return json_path, xml_path, validation_path
