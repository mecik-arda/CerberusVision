from __future__ import annotations

import json
from typing import Any, Dict, Literal, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.llm.inference import _extract_json


DOCUMENT_RELEVANCE_SYSTEM_PROMPT = (
    "You are a narrow topic and language filter. Decide only whether the supplied "
    "public document metadata and limited text excerpt are about a Shipping "
    "Instruction or Bill of Lading and whether the document is in English. Do "
    "not judge quality, accuracy, completeness, or extraction reliability. Never correct, replace, infer, "
    "extract, or generate document values. Return JSON only with relevant, "
    "english, document_type, and reason. reason must be one short sentence. Example JSON: "
    "{\"relevant\": true, \"english\": true, \"document_type\": \"bill_of_lading\", "
    "\"reason\": \"The document is a bill of lading sample.\"}. Do not return "
    "scores, corrected data, or additional fields."
)


class DocumentRelevanceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool
    english: bool
    document_type: Literal["shipping_instruction", "bill_of_lading", "other"]
    reason: str = Field(min_length=1, max_length=240)


def build_document_relevance_payload(
    source_title: str,
    source_snippet: str,
    source_url: str,
    text_excerpt: str,
) -> Dict[str, Any]:
    return {
        "task": "topic_and_english_filter_only_no_quality_scoring",
        "source": {
            "title": source_title[:300],
            "snippet": source_snippet[:600],
            "url": source_url[:1000],
        },
        "limited_text_excerpt": text_excerpt[
            : settings.document_search.max_review_chars
        ],
    }


def run_document_relevance_review(
    payload: Dict[str, Any],
) -> Tuple[DocumentRelevanceReview, str]:
    from openai import OpenAI

    if not settings.deepseek.api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")
    client = OpenAI(
        api_key=settings.deepseek.api_key,
        base_url=settings.deepseek.base_url,
        timeout=45,
    )
    last_error: Exception | None = None
    for attempt in range(2):
        user_content = json.dumps(payload, ensure_ascii=False)
        if attempt:
            user_content += "\nReturn one non-empty JSON object only."
        try:
            response = client.chat.completions.create(
                model=settings.deepseek.model_name,
                messages=[
                    {"role": "system", "content": DOCUMENT_RELEVANCE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=160,
                timeout=45,
            )
            raw_output = response.choices[0].message.content or ""
            if not raw_output.strip():
                raise ValueError("DeepSeek returned an empty relevance review.")
            review = DocumentRelevanceReview.model_validate(
                json.loads(_extract_json(raw_output))
            )
            return review, raw_output
        except (ValueError, json.JSONDecodeError) as error:
            last_error = error
    raise ValueError(f"DeepSeek relevance review failed: {last_error}")
