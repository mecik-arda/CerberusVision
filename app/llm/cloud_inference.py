from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.llm.inference import _extract_json
from app.models import CloudAuditResponse, LocalAuditAssessment, ShippingInstruction


REVIEW_SYSTEM_PROMPT = (
    "You are a conservative shipping-document auditor. Review only the supplied "
    "local warnings, critical values, and limited OCR excerpts. Never correct, "
    "replace, infer, or generate shipping data. Return only JSON with: score "
    "(0-100 confidence that the local extraction is reliable), summary (at most "
    "two short sentences), and suspicious_fields (field paths only). Do not "
    "include corrected values or additional fields."
)


def _get_path_value(data: Dict[str, Any], path: str) -> Any:
    if path in {"xml", "ocr_text", "parties", "cargo_items"} or "role=" in path:
        return None
    parts = [
        part
        for part in path.replace("]", "").replace("[", ".").split(".")
        if part
    ]
    current: Any = data
    for part in parts:
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _build_ocr_excerpt(
    ocr_text: str,
    paths: List[str],
    values: Dict[str, Any],
) -> str:
    keyword_map = {
        "parties": ["shipper", "consignee", "notify"],
        "equipment": ["container", "equipment"],
        "weight": ["weight", "gross", "kg", "kgs"],
        "port": ["port", "loading", "discharge"],
        "date": ["date"],
        "booking": ["booking"],
        "package": ["package", "packages", "qty", "quantity"],
    }
    terms = set()
    for path in paths:
        lowered_path = path.casefold()
        for key, keywords in keyword_map.items():
            if key in lowered_path:
                terms.update(keywords)
    for value in values.values():
        if isinstance(value, (str, int, float)) and len(str(value).strip()) >= 3:
            terms.add(str(value).strip().casefold())

    selected = []
    for line in ocr_text.splitlines():
        stripped = line.strip()
        lowered = stripped.casefold()
        if stripped and any(term in lowered for term in terms):
            selected.append(stripped)
    excerpt = "\n".join(dict.fromkeys(selected))
    return excerpt[: settings.deepseek.max_ocr_excerpt_chars]


def build_review_payload(
    local_result: ShippingInstruction,
    assessment: LocalAuditAssessment,
    ocr_text: str,
) -> Dict[str, Any]:
    local_data = local_result.model_dump(mode="json", exclude_none=True)
    flagged_paths = list(
        dict.fromkeys(finding.field_path for finding in assessment.findings)
    )
    critical_values = {
        path: value
        for path in flagged_paths
        if (value := _get_path_value(local_data, path)) is not None
    }
    return {
        "task": "audit_only_no_corrections",
        "local_risk_score": assessment.risk_score,
        "local_findings": [
            {
                "field_path": finding.field_path,
                "code": finding.code,
                "message": finding.message,
            }
            for finding in assessment.findings
        ],
        "critical_values": critical_values,
        "limited_ocr_excerpt": _build_ocr_excerpt(
            ocr_text, flagged_paths, critical_values
        ),
    }


def run_deepseek_review(
    local_result: ShippingInstruction,
    assessment: LocalAuditAssessment,
    ocr_text: str,
) -> Tuple[CloudAuditResponse, str, Dict[str, Any]]:
    """Ask DeepSeek for a short audit only; it cannot modify the local result."""
    from openai import OpenAI

    if not settings.deepseek.api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")
    payload = build_review_payload(local_result, assessment, ocr_text)
    client = OpenAI(
        api_key=settings.deepseek.api_key,
        base_url=settings.deepseek.base_url,
        timeout=45,
    )
    response = client.chat.completions.create(
        model=settings.deepseek.model_name,
        messages=[
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=256,
        timeout=45,
    )
    raw_output = response.choices[0].message.content or ""
    review = CloudAuditResponse.model_validate(
        json.loads(_extract_json(raw_output))
    )
    return review, raw_output, payload
