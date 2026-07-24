from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class EvidenceResult:
    field_path: str
    value: str
    evidence_score: float
    matched_fragments: tuple[str, ...]
    status: EvidenceStatus
    method: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


STRONG_FIELD_SUFFIXES = (
    "shipping_instruction_reference",
    "carrier_booking_reference",
    "export_declaration_number",
    "service_contract_reference",
    "equipment_reference",
    "reference_number",
    "phone_number",
    "email",
    "party_id",
)

FUZZY_NAME_SUFFIXES = (
    "party_name",
    "contact_details.name",
)

ADDRESS_FIELD_PARTS = (
    ".address.street",
    ".address.city",
    ".address.postal_code",
    ".address.country_code",
)


def normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def normalize_identifier(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def normalize_fuzzy_token(value: str) -> str:
    return normalize_identifier(value).translate(
        str.maketrans(
            {
                "0": "o",
                "1": "i",
                "5": "s",
                "8": "b",
            }
        )
    )


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous_row = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, 1):
        current_row = [left_index]
        for right_index, right_character in enumerate(right, 1):
            insertion_cost = current_row[right_index - 1] + 1
            deletion_cost = previous_row[right_index] + 1
            substitution_cost = (
                previous_row[right_index - 1]
                + (left_character != right_character)
            )
            current_row.append(
                min(insertion_cost, deletion_cost, substitution_cost)
            )
        previous_row = current_row
    return previous_row[-1]


def normalized_similarity(left: str, right: str) -> float:
    normalized_left = normalize_fuzzy_token(left)
    normalized_right = normalize_fuzzy_token(right)
    return _normalized_token_similarity(normalized_left, normalized_right)


def _normalized_token_similarity(
    normalized_left: str,
    normalized_right: str,
) -> float:
    maximum_length = max(len(normalized_left), len(normalized_right))
    if maximum_length == 0:
        return 1.0
    return 1.0 - (
        levenshtein_distance(normalized_left, normalized_right)
        / maximum_length
    )


def _flatten_scalar_values(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, str]]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        flattened: list[tuple[str, str]] = []
        for field_name, field_value in value.items():
            child_prefix = (
                f"{prefix}.{field_name}" if prefix else str(field_name)
            )
            flattened.extend(
                _flatten_scalar_values(field_value, child_prefix)
            )
        return flattened
    if isinstance(value, list):
        flattened = []
        for index, item in enumerate(value):
            flattened.extend(
                _flatten_scalar_values(item, f"{prefix}[{index}]")
            )
        return flattened
    if value is None or value is False or value == "":
        return []
    return [(prefix, str(value))]


def _matching_lines(
    ocr_lines: list[str],
    matched_tokens: set[str],
    normalized_value: str,
) -> tuple[str, ...]:
    fragments: list[str] = []
    normalized_identifier_value = normalize_identifier(normalized_value)
    for line in ocr_lines:
        normalized_line = normalize_evidence_text(line)
        line_tokens = set(normalized_line.split())
        identifier_line = normalize_identifier(line)
        if (
            matched_tokens & line_tokens
            or (
                normalized_identifier_value
                and normalized_identifier_value in identifier_line
            )
        ):
            stripped_line = line.strip()
            if stripped_line and stripped_line not in fragments:
                fragments.append(stripped_line)
    return tuple(fragments[:5])


def _strong_evidence(
    field_path: str,
    value: str,
    ocr_text: str,
    ocr_lines: list[str],
) -> EvidenceResult:
    normalized_value = normalize_identifier(value)
    normalized_ocr = normalize_identifier(ocr_text)
    supported = bool(
        normalized_value and normalized_value in normalized_ocr
    )
    status = (
        EvidenceStatus.SUPPORTED
        if supported
        else EvidenceStatus.UNSUPPORTED
    )
    fragments = _matching_lines(
        ocr_lines,
        set(normalize_evidence_text(value).split()),
        value,
    )
    return EvidenceResult(
        field_path=field_path,
        value=value,
        evidence_score=1.0 if supported else 0.0,
        matched_fragments=fragments,
        status=status,
        method="normalized_strong_match",
    )


def _token_coverage_evidence(
    field_path: str,
    value: str,
    ocr_text: str,
    ocr_lines: list[str],
    token_similarity_threshold: float,
    supported_threshold: float,
    uncertain_threshold: float,
    method: str,
) -> EvidenceResult:
    value_tokens = normalize_evidence_text(value).split()
    ocr_tokens = set(normalize_evidence_text(ocr_text).split())
    normalized_ocr_tokens = {
        ocr_token: normalize_fuzzy_token(ocr_token)
        for ocr_token in ocr_tokens
    }
    if not value_tokens:
        score = 0.0
        matched_ocr_tokens: set[str] = set()
    else:
        matched_ocr_tokens = set()
        matched_count = 0
        for value_token in value_tokens:
            if value_token in ocr_tokens:
                matched_count += 1
                matched_ocr_tokens.add(value_token)
                continue
            normalized_value_token = normalize_fuzzy_token(value_token)
            best_token = ""
            best_similarity = 0.0
            for ocr_token, normalized_ocr_token in (
                normalized_ocr_tokens.items()
            ):
                similarity = _normalized_token_similarity(
                    normalized_value_token,
                    normalized_ocr_token,
                )
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_token = ocr_token
            if best_similarity >= token_similarity_threshold:
                matched_count += 1
                if best_token:
                    matched_ocr_tokens.add(best_token)
        score = matched_count / len(value_tokens)
    if score >= supported_threshold:
        status = EvidenceStatus.SUPPORTED
    elif score >= uncertain_threshold:
        status = EvidenceStatus.UNCERTAIN
    else:
        status = EvidenceStatus.UNSUPPORTED
    return EvidenceResult(
        field_path=field_path,
        value=value,
        evidence_score=round(score, 4),
        matched_fragments=_matching_lines(
            ocr_lines,
            matched_ocr_tokens,
            value,
        ),
        status=status,
        method=method,
    )


def validate_field_evidence(
    field_path: str,
    value: str,
    ocr_text: str,
    token_similarity_threshold: float = 0.8,
    supported_threshold: float = 0.8,
    uncertain_threshold: float = 0.5,
) -> EvidenceResult:
    ocr_lines = ocr_text.splitlines()
    if field_path.endswith(STRONG_FIELD_SUFFIXES):
        return _strong_evidence(
            field_path,
            value,
            ocr_text,
            ocr_lines,
        )
    if field_path.endswith(FUZZY_NAME_SUFFIXES):
        method = "fuzzy_name_token_coverage"
    elif any(part in field_path for part in ADDRESS_FIELD_PARTS):
        method = "multiline_address_token_coverage"
    else:
        method = "generic_token_coverage"
    return _token_coverage_evidence(
        field_path,
        value,
        ocr_text,
        ocr_lines,
        token_similarity_threshold,
        supported_threshold,
        uncertain_threshold,
        method,
    )


def validate_instruction_evidence(
    instruction: Any,
    ocr_text: str,
    token_similarity_threshold: float = 0.8,
    supported_threshold: float = 0.8,
    uncertain_threshold: float = 0.5,
) -> list[EvidenceResult]:
    return [
        validate_field_evidence(
            field_path,
            value,
            ocr_text,
            token_similarity_threshold,
            supported_threshold,
            uncertain_threshold,
        )
        for field_path, value in _flatten_scalar_values(instruction)
    ]
