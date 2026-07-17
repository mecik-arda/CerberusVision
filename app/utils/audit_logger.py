from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from app.config import settings


def create_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def get_session_dir(session_id: str) -> Path:
    session_dir = settings.logs_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def log_ocr_result(session_id: str, layout_text: str, boxes_data: Optional[dict] = None) -> Path:
    session_dir = get_session_dir(session_id)
    ocr_path = session_dir / "ocr_layout_text.txt"
    ocr_path.write_text(layout_text, encoding="utf-8")
    if boxes_data:
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
        },
    }
    summary_path = session_dir / "processing_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary_path


def log_benchmark_report(
    session_id: str,
    local_result: dict,
    deepseek_result: dict,
    comparison: dict,
) -> Path:
    session_dir = get_session_dir(session_id)
    report = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "local_qwen_result": local_result,
        "deepseek_result": deepseek_result,
        "comparison": comparison,
    }
    report_path = session_dir / "benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path