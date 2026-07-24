from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_phase4_1_continuation import (
    DEFAULT_OUTPUT_DIR,
    PARENT_ADAPTER_CONFIG_SHA256,
    PARENT_ADAPTER_SHA256,
    file_sha256,
    load_jsonl,
)


REQUIRED_RECORD_FIELDS = {"instructions", "input", "output"}


def normalized_document_hash(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_records(
    records: list[dict[str, Any]],
    split_name: str,
) -> None:
    for record_index, record in enumerate(records):
        if not REQUIRED_RECORD_FIELDS.issubset(record):
            raise ValueError(
                f"{split_name} record {record_index} has missing fields"
            )
        if not str(record["input"]).strip():
            raise ValueError(
                f"{split_name} record {record_index} has empty input"
            )
        output = json.loads(str(record["output"]))
        if not isinstance(output, dict):
            raise ValueError(
                f"{split_name} record {record_index} output is not an object"
            )


def validate_notebook(path: Path) -> dict[str, int]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    compiled_cells = 0
    for cell_index, source in enumerate(code_cells):
        if "trust_remote_code" in source:
            raise ValueError(
                f"Notebook cell {cell_index} enables remote code"
            )
        if "get_peft_model" in source:
            raise ValueError(
                f"Notebook cell {cell_index} creates a fresh adapter"
            )
        if any(
            line.lstrip().startswith("#")
            for line in source.splitlines()
        ):
            raise ValueError(
                f"Notebook cell {cell_index} contains code comments"
            )
        if source.lstrip().startswith("%"):
            continue
        compile(source, f"notebook-cell-{cell_index}", "exec")
        compiled_cells += 1
    return {
        "cells": len(notebook.get("cells", [])),
        "code_cells": len(code_cells),
        "compiled_cells": compiled_cells,
    }


def validate_package(package_dir: Path) -> dict[str, Any]:
    required_paths = {
        "train": package_dir / "continuation_train.jsonl",
        "validation": package_dir / "validation.jsonl",
        "hard_validation": package_dir / "hard_validation.jsonl",
        "selection": package_dir / "selection_manifest.json",
        "contract": package_dir / "phase4_1_contract.json",
        "manifest": package_dir / "phase4_1_manifest.json",
        "notebook": package_dir / "CerberusVision_Phase4_1_Devam.ipynb",
        "guide": package_dir / "PHASE4_1_EGITIM_REHBERI.md",
    }
    missing_paths = [
        str(path)
        for path in required_paths.values()
        if not path.is_file()
    ]
    if missing_paths:
        raise FileNotFoundError(
            "Missing Phase 4.1 package files: " + ", ".join(missing_paths)
        )
    manifest = json.loads(
        required_paths["manifest"].read_text(encoding="utf-8")
    )
    expected_hashes = manifest["files"]
    for file_name, expected_hash in expected_hashes.items():
        actual_hash = file_sha256(package_dir / file_name)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Phase 4.1 hash mismatch for {file_name}: {actual_hash}"
            )
    contract = json.loads(
        required_paths["contract"].read_text(encoding="utf-8")
    )
    parent_adapter = contract["parent_adapter"]
    if parent_adapter["adapter_model_sha256"] != PARENT_ADAPTER_SHA256:
        raise ValueError("Unexpected Phase 4 parent adapter hash")
    if (
        parent_adapter["adapter_config_sha256"]
        != PARENT_ADAPTER_CONFIG_SHA256
    ):
        raise ValueError("Unexpected Phase 4 parent config hash")
    train_records = load_jsonl(required_paths["train"])
    validation_records = load_jsonl(required_paths["validation"])
    hard_validation_records = load_jsonl(
        required_paths["hard_validation"]
    )
    validate_records(train_records, "continuation_train")
    validate_records(validation_records, "validation")
    validate_records(hard_validation_records, "hard_validation")
    dataset_contract = contract["dataset"]
    if (
        len(train_records)
        != dataset_contract["continuation_train_records"]
    ):
        raise ValueError("Continuation train record count mismatch")
    if len(validation_records) != dataset_contract["validation_records"]:
        raise ValueError("Validation record count mismatch")
    if (
        len(hard_validation_records)
        != dataset_contract["hard_validation_records"]
    ):
        raise ValueError("Hard validation record count mismatch")
    train_hashes = {
        normalized_document_hash(str(record["input"]))
        for record in train_records
    }
    validation_hashes = {
        normalized_document_hash(str(record["input"]))
        for record in validation_records
    }
    overlap = train_hashes & validation_hashes
    if overlap:
        raise ValueError(
            f"Phase 4.1 train validation overlap detected: {len(overlap)}"
        )
    validation_record_hashes = {
        hashlib.sha256(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        for record in validation_records
    }
    hard_validation_record_hashes = {
        hashlib.sha256(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        for record in hard_validation_records
    }
    if not hard_validation_record_hashes.issubset(
        validation_record_hashes
    ):
        raise ValueError("Hard validation is not a validation subset")
    selection = json.loads(
        required_paths["selection"].read_text(encoding="utf-8")
    )
    replay_records = selection["source_train_records"]
    hard_replay_records = selection["hard_replay_records"]
    if replay_records + hard_replay_records != len(train_records):
        raise ValueError("Replay composition count mismatch")
    replay_ratio = replay_records / len(train_records)
    if not 0.6 <= replay_ratio <= 0.7:
        raise ValueError(f"Unsafe replay ratio: {replay_ratio}")
    notebook_report = validate_notebook(required_paths["notebook"])
    return {
        "package_dir": str(package_dir.resolve()),
        "continuation_train_records": len(train_records),
        "validation_records": len(validation_records),
        "hard_validation_records": len(hard_validation_records),
        "normalized_train_validation_overlap": len(overlap),
        "replay_ratio": round(replay_ratio, 6),
        "hard_replay_ratio": round(1.0 - replay_ratio, 6),
        "parent_adapter_sha256": PARENT_ADAPTER_SHA256,
        "manifest_sha256": file_sha256(required_paths["manifest"]),
        "notebook": notebook_report,
        "acceptance_gate": contract["acceptance_gate"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Phase 4.1 continual QLoRA Colab package"
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = validate_package(args.package_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
