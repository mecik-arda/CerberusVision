from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_REGRESSION_DIR = PROJECT_ROOT / "tests" / "fixtures" / "qwen_benchmark"
DEFAULT_INSTRUCTIONS = "Extract shipping instruction data from OCR text as JSON."


def _session_dirs() -> list[Path]:
    session_pattern = re.compile(r"^\d{8}_\d{6}_\d{6}$")
    return sorted(
        [
            path
            for path in LOGS_DIR.iterdir()
            if path.is_dir() and session_pattern.match(path.name)
        ]
    )


def _load_ocr_text(session_dir: Path) -> str | None:
    ocr_path = session_dir / "ocr_layout_text.txt"
    if not ocr_path.exists():
        return None
    return ocr_path.read_text(encoding="utf-8").strip()


def _load_approved_json(session_dir: Path) -> dict[str, Any] | None:
    approved_path = session_dir / "approved_instruction.json"
    if not approved_path.exists():
        return None
    try:
        return json.loads(approved_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None


def normalize_document_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def document_fingerprint(text: str) -> str:
    normalized = normalize_document_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _token_set(text: str) -> set[str]:
    return set(normalize_document_text(text).split())


def _token_set_jaccard_similarity(
    left_tokens: set[str],
    right_tokens: set[str],
) -> float:
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def token_jaccard_similarity(left: str, right: str) -> float:
    return _token_set_jaccard_similarity(
        _token_set(left),
        _token_set(right),
    )


def _clean_ocr_for_augmentation(text: str, rng: random.Random) -> str:
    substitutions = [
        ("0", "O"),
        ("O", "0"),
        ("I", "1"),
        ("1", "I"),
        ("l", "1"),
        ("S", "5"),
        ("5", "S"),
        ("B", "8"),
        ("\n\n", "\n"),
        (",", "."),
        ("  ", " "),
    ]
    augmented_text = text
    for _ in range(rng.randint(1, 4)):
        old_value, new_value = rng.choice(substitutions)
        augmented_text = augmented_text.replace(old_value, new_value)
    return augmented_text


def _load_source_records(max_samples: int) -> tuple[list[dict[str, Any]], int, int]:
    session_dirs = _session_dirs()
    records: list[dict[str, Any]] = []
    skipped = 0
    for session_dir in session_dirs:
        if len(records) >= max_samples:
            break
        ocr_text = _load_ocr_text(session_dir)
        approved = _load_approved_json(session_dir)
        if not ocr_text or not approved or len(ocr_text) < 50:
            skipped += 1
            continue
        records.append(
            {
                "instructions": DEFAULT_INSTRUCTIONS,
                "input": ocr_text,
                "output": json.dumps(approved, ensure_ascii=False),
                "session_id": session_dir.name,
                "source_hash": document_fingerprint(ocr_text),
            }
        )
    return records, len(session_dirs), skipped


def _load_jsonl_source_records(
    source_path: Path,
    max_samples: int,
) -> tuple[list[dict[str, Any]], int, int]:
    records: list[dict[str, Any]] = []
    skipped = 0
    with source_path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, 1):
            if len(records) >= max_samples:
                break
            stripped_line = line.strip()
            if not stripped_line:
                continue
            source_record = json.loads(stripped_line)
            ocr_text = str(source_record.get("input", "")).strip()
            output = source_record.get("output")
            instructions = str(
                source_record.get("instructions", DEFAULT_INSTRUCTIONS)
            ).strip()
            if not ocr_text or output in (None, "") or len(ocr_text) < 50:
                skipped += 1
                continue
            serialized_output = (
                output
                if isinstance(output, str)
                else json.dumps(output, ensure_ascii=False)
            )
            records.append(
                {
                    "instructions": instructions or DEFAULT_INSTRUCTIONS,
                    "input": ocr_text,
                    "output": serialized_output,
                    "session_id": f"jsonl-line-{line_number}",
                    "source_hash": document_fingerprint(ocr_text),
                }
            )
    return records, len(records) + skipped, skipped


def _load_fixture_texts(fixture_dirs: Iterable[Path]) -> list[dict[str, str]]:
    fixtures: list[dict[str, str]] = []
    for fixture_dir in fixture_dirs:
        if not fixture_dir.exists():
            continue
        for fixture_path in sorted(fixture_dir.glob("*.json")):
            fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
            ocr_text = fixture_data.get("ocr_text")
            ocr_fixture = fixture_data.get("ocr_fixture")
            if ocr_text is None and ocr_fixture:
                frozen_path = (PROJECT_ROOT / str(ocr_fixture)).resolve()
                if frozen_path.exists():
                    ocr_text = frozen_path.read_text(encoding="utf-8")
            if ocr_text:
                fixtures.append(
                    {
                        "name": fixture_path.name,
                        "text": str(ocr_text),
                        "source_hash": document_fingerprint(str(ocr_text)),
                    }
                )
    return fixtures


def find_forbidden_overlaps(
    records: list[dict[str, Any]],
    forbidden_fixtures: list[dict[str, str]],
    near_duplicate_threshold: float,
) -> list[dict[str, Any]]:
    overlaps: list[dict[str, Any]] = []
    record_token_sets = [_token_set(record["input"]) for record in records]
    fixture_token_sets = [
        _token_set(fixture["text"]) for fixture in forbidden_fixtures
    ]
    for record, record_tokens in zip(records, record_token_sets):
        best_overlap: dict[str, Any] | None = None
        for fixture, fixture_tokens in zip(
            forbidden_fixtures,
            fixture_token_sets,
        ):
            if record["source_hash"] == fixture["source_hash"]:
                best_overlap = {
                    "session_id": record["session_id"],
                    "fixture": fixture["name"],
                    "match": "exact",
                    "similarity": 1.0,
                }
                break
            similarity = _token_set_jaccard_similarity(
                record_tokens,
                fixture_tokens,
            )
            if similarity >= near_duplicate_threshold and (
                best_overlap is None
                or similarity > best_overlap["similarity"]
            ):
                best_overlap = {
                    "session_id": record["session_id"],
                    "fixture": fixture["name"],
                    "match": "near_duplicate",
                    "similarity": round(similarity, 4),
                }
        if best_overlap is not None:
            overlaps.append(best_overlap)
    return overlaps


def assert_no_forbidden_overlap(
    records: list[dict[str, Any]],
    forbidden_fixtures: list[dict[str, str]],
    near_duplicate_threshold: float,
) -> None:
    overlaps = find_forbidden_overlaps(
        records,
        forbidden_fixtures,
        near_duplicate_threshold,
    )
    if overlaps:
        overlap_messages = [
            f"{overlap['session_id']}={overlap['fixture']}:"
            f"{overlap['similarity']:.4f}"
            for overlap in overlaps
        ]
        raise ValueError(
            "Forbidden evaluation overlap detected: "
            + ", ".join(overlap_messages)
        )


def remove_forbidden_overlaps(
    records: list[dict[str, Any]],
    forbidden_fixtures: list[dict[str, str]],
    near_duplicate_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overlaps = find_forbidden_overlaps(
        records,
        forbidden_fixtures,
        near_duplicate_threshold,
    )
    removed_session_ids = {
        overlap["session_id"] for overlap in overlaps
    }
    retained_records = [
        record
        for record in records
        if record["session_id"] not in removed_session_ids
    ]
    assert_no_forbidden_overlap(
        retained_records,
        forbidden_fixtures,
        near_duplicate_threshold,
    )
    return retained_records, overlaps


def assign_source_groups(
    records: list[dict[str, Any]],
    near_duplicate_threshold: float,
) -> list[dict[str, Any]]:
    parents = list(range(len(records)))
    record_token_sets = [_token_set(record["input"]) for record in records]

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root = find(left_index)
        right_root = find(right_index)
        if left_root != right_root:
            parents[right_root] = left_root

    for left_index, left_record in enumerate(records):
        for right_index in range(left_index + 1, len(records)):
            right_record = records[right_index]
            if left_record["source_hash"] == right_record["source_hash"]:
                union(left_index, right_index)
                continue
            similarity = _token_set_jaccard_similarity(
                record_token_sets[left_index],
                record_token_sets[right_index],
            )
            if similarity >= near_duplicate_threshold:
                union(left_index, right_index)

    grouped_records = [dict(record) for record in records]
    group_members: dict[int, list[int]] = {}
    for record_index in range(len(records)):
        group_members.setdefault(find(record_index), []).append(record_index)
    for member_indices in group_members.values():
        group_hash = hashlib.sha256(
            "|".join(
                sorted(records[index]["source_hash"] for index in member_indices)
            ).encode("utf-8")
        ).hexdigest()
        for member_index in member_indices:
            grouped_records[member_index]["source_group_id"] = group_hash
    return grouped_records


def split_source_groups(
    records: list[dict[str, Any]],
    validation_ratio: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.0 < validation_ratio < 1.0:
        raise ValueError("validation_ratio must be between 0 and 1")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["source_group_id"], []).append(record)
    if len(grouped) < 2:
        raise ValueError("At least two independent source groups are required")
    group_ids = sorted(grouped)
    random.Random(seed).shuffle(group_ids)
    target_validation_records = max(1, round(len(records) * validation_ratio))
    validation_group_ids: set[str] = set()
    validation_count = 0
    for group_id in group_ids:
        if len(validation_group_ids) == len(group_ids) - 1:
            break
        validation_group_ids.add(group_id)
        validation_count += len(grouped[group_id])
        if validation_count >= target_validation_records:
            break
    train_records: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []
    for record in records:
        target = (
            validation_records
            if record["source_group_id"] in validation_group_ids
            else train_records
        )
        target.append(dict(record))
    assert train_records
    assert validation_records
    return train_records, validation_records


def assert_split_isolation(
    train_records: list[dict[str, Any]],
    validation_records: list[dict[str, Any]],
    near_duplicate_threshold: float,
) -> None:
    train_groups = {record["source_group_id"] for record in train_records}
    validation_groups = {
        record["source_group_id"] for record in validation_records
    }
    if train_groups & validation_groups:
        raise AssertionError("Source groups overlap across train and validation")
    for train_record in train_records:
        for validation_record in validation_records:
            similarity = token_jaccard_similarity(
                train_record["input"],
                validation_record["input"],
            )
            if similarity >= near_duplicate_threshold:
                raise AssertionError(
                    "Near duplicate crossed train and validation: "
                    f"{train_record['session_id']}="
                    f"{validation_record['session_id']}:{similarity:.4f}"
                )


def _training_record(record: dict[str, Any]) -> dict[str, str]:
    return {
        "instructions": record["instructions"],
        "input": record["input"],
        "output": record["output"],
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    serialized = "".join(
        json.dumps(_training_record(record), ensure_ascii=False) + "\n"
        for record in records
    )
    path.write_text(serialized, encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field_presence(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        output_data = json.loads(record["output"])
        for field_name, field_value in output_data.items():
            if field_value not in (None, "", [], {}):
                counts[field_name] += 1
    return dict(sorted(counts.items()))


def prepare_splits(
    output_dir: Path,
    augment_factor: int = 0,
    max_samples: int = 1000,
    validation_ratio: float = 0.1,
    seed: int = 3407,
    near_duplicate_threshold: float = 0.9,
    forbidden_dirs: Iterable[Path] | None = None,
    source_data: Path | None = None,
    drop_forbidden_overlaps: bool = False,
    sanitized_source_output: Path | None = None,
) -> dict[str, Any]:
    if source_data is None:
        source_records, sessions_scanned, skipped = _load_source_records(
            max_samples
        )
        source_kind = "approved_sessions"
        source_path = str(LOGS_DIR.resolve())
        source_sha256 = None
    else:
        source_records, sessions_scanned, skipped = (
            _load_jsonl_source_records(source_data, max_samples)
        )
        source_kind = "jsonl"
        source_path = str(source_data.resolve())
        source_sha256 = _file_sha256(source_data)
    if len(source_records) < 2:
        raise ValueError("At least two approved source documents are required")
    effective_forbidden_dirs = list(
        forbidden_dirs
        if forbidden_dirs is not None
        else [DEFAULT_REGRESSION_DIR]
    )
    forbidden_fixtures = _load_fixture_texts(effective_forbidden_dirs)
    if drop_forbidden_overlaps:
        source_records, removed_overlaps = remove_forbidden_overlaps(
            source_records,
            forbidden_fixtures,
            near_duplicate_threshold,
        )
    else:
        assert_no_forbidden_overlap(
            source_records,
            forbidden_fixtures,
            near_duplicate_threshold,
        )
        removed_overlaps = []
    if sanitized_source_output is not None:
        sanitized_source_output.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(sanitized_source_output, source_records)
    grouped_records = assign_source_groups(
        source_records,
        near_duplicate_threshold,
    )
    train_base, validation_records = split_source_groups(
        grouped_records,
        validation_ratio,
        seed,
    )
    assert_split_isolation(
        train_base,
        validation_records,
        near_duplicate_threshold,
    )
    rng = random.Random(seed)
    train_records = [dict(record) for record in train_base]
    skipped_augmented_overlaps = 0
    for record in train_base:
        for augmentation_index in range(augment_factor):
            augmented_record = dict(record)
            augmented_record["input"] = _clean_ocr_for_augmentation(
                record["input"],
                rng,
            )
            if any(
                token_jaccard_similarity(
                    augmented_record["input"],
                    validation_record["input"],
                )
                >= near_duplicate_threshold
                for validation_record in validation_records
            ):
                skipped_augmented_overlaps += 1
                continue
            augmented_record["augmentation_index"] = augmentation_index + 1
            train_records.append(augmented_record)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    validation_path = output_dir / "validation.jsonl"
    manifest_path = output_dir / "manifest.json"
    _write_jsonl(train_path, train_records)
    _write_jsonl(validation_path, validation_records)
    manifest_records = [
        {
            "session_id": record["session_id"],
            "source_hash": record["source_hash"],
            "source_group_id": record["source_group_id"],
            "split": split_name,
        }
        for split_name, split_records in (
            ("train", train_base),
            ("validation", validation_records),
        )
        for record in split_records
    ]
    manifest = {
        "schema_version": 1,
        "source": {
            "kind": source_kind,
            "path": source_path,
            "sha256": source_sha256,
        },
        "seed": seed,
        "validation_ratio": validation_ratio,
        "near_duplicate_threshold": near_duplicate_threshold,
        "source_records": len(source_records),
        "source_groups": len(
            {record["source_group_id"] for record in grouped_records}
        ),
        "train_source_records": len(train_base),
        "train_augmented_records": len(train_records) - len(train_base),
        "skipped_augmented_overlaps": skipped_augmented_overlaps,
        "validation_records": len(validation_records),
        "forbidden_fixture_count": len(forbidden_fixtures),
        "removed_forbidden_overlap_count": len(removed_overlaps),
        "removed_forbidden_overlaps": removed_overlaps,
        "forbidden_dirs": [
            str(path.resolve()) for path in effective_forbidden_dirs
        ],
        "field_presence": {
            "train": _field_presence(train_base),
            "validation": _field_presence(validation_records),
        },
        "records": manifest_records,
        "files": {
            "train.jsonl": _file_sha256(train_path),
            "validation.jsonl": _file_sha256(validation_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "train_records": len(train_records),
        "train_source_records": len(train_base),
        "validation_records": len(validation_records),
        "sessions_scanned": sessions_scanned,
        "skipped": skipped,
        "manifest": str(manifest_path),
        "train": str(train_path),
        "validation": str(validation_path),
        "removed_forbidden_overlaps": len(removed_overlaps),
        "skipped_augmented_overlaps": skipped_augmented_overlaps,
        "sanitized_source": (
            str(sanitized_source_output)
            if sanitized_source_output is not None
            else None
        ),
    }


def prepare_dataset(
    output_path: Path,
    augment_factor: int = 0,
    max_samples: int = 1000,
) -> dict[str, Any]:
    source_records, sessions_scanned, skipped = _load_source_records(max_samples)
    rng = random.Random(3407)
    records = [dict(record) for record in source_records]
    for record in source_records:
        for augmentation_index in range(augment_factor):
            augmented_record = dict(record)
            augmented_record["input"] = _clean_ocr_for_augmentation(
                record["input"],
                rng,
            )
            augmented_record["augmentation_index"] = augmentation_index + 1
            records.append(augmented_record)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_path, records)
    return {
        "records": len(records),
        "sessions_scanned": sessions_scanned,
        "skipped": skipped,
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare isolated train and validation datasets"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("veriler/splits"),
    )
    parser.add_argument("--augment", type=int, default=0)
    parser.add_argument("--max-samples", type=int, default=1000)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument(
        "--near-duplicate-threshold",
        type=float,
        default=0.9,
    )
    parser.add_argument("--holdout-dir", type=Path)
    parser.add_argument("--source-data", type=Path)
    parser.add_argument(
        "--drop-forbidden-overlaps",
        action="store_true",
    )
    parser.add_argument("--sanitized-source-output", type=Path)
    args = parser.parse_args()
    forbidden_dirs = [DEFAULT_REGRESSION_DIR]
    if args.holdout_dir is not None:
        forbidden_dirs.append(args.holdout_dir)
    report = prepare_splits(
        output_dir=args.output_dir,
        augment_factor=args.augment,
        max_samples=args.max_samples,
        validation_ratio=args.validation_ratio,
        seed=args.seed,
        near_duplicate_threshold=args.near_duplicate_threshold,
        forbidden_dirs=forbidden_dirs,
        source_data=args.source_data,
        drop_forbidden_overlaps=args.drop_forbidden_overlaps,
        sanitized_source_output=args.sanitized_source_output,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
