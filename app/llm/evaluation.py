from __future__ import annotations

from typing import Any


def flatten_values(value: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            flattened.update(flatten_values(child, path))
        return flattened
    if isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            flattened.update(flatten_values(child, path))
        return flattened
    flattened[prefix] = value
    return flattened


def normalized_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, float):
        return round(value, 6)
    return value


def evaluate_expected_fields(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    expected_fields = flatten_values(expected)
    actual_fields = flatten_values(actual)
    correct_fields: list[str] = []
    missing_fields: list[str] = []
    mismatched_fields: list[dict[str, Any]] = []
    for path, expected_value in expected_fields.items():
        if path not in actual_fields:
            missing_fields.append(path)
            continue
        actual_value = actual_fields[path]
        if actual_value is None and expected_value is not None:
            missing_fields.append(path)
            continue
        if normalized_value(expected_value) == normalized_value(actual_value):
            correct_fields.append(path)
        else:
            mismatched_fields.append({
                "field_path": path,
                "expected": expected_value,
                "actual": actual_value,
            })
    total = len(expected_fields)
    accuracy = round((len(correct_fields) / total * 100.0) if total else 100.0, 2)
    return {
        "accuracy": accuracy,
        "total_fields": total,
        "correct_fields": correct_fields,
        "missing_fields": missing_fields,
        "mismatched_fields": mismatched_fields,
    }


def aggregate_evaluations(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_fields = sum(result["total_fields"] for result in results)
    correct_fields = sum(len(result["correct_fields"]) for result in results)
    missing_fields = sum(len(result["missing_fields"]) for result in results)
    mismatched_fields = sum(len(result["mismatched_fields"]) for result in results)
    accuracy = round((correct_fields / total_fields * 100.0) if total_fields else 100.0, 2)
    return {
        "documents": len(results),
        "accuracy": accuracy,
        "total_fields": total_fields,
        "correct_fields": correct_fields,
        "missing_fields": missing_fields,
        "mismatched_fields": mismatched_fields,
        "results": results,
    }
