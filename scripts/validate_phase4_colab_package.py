from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti"
REQUIRED_RECORD_FIELDS = {"instructions", "input", "output"}
EXPECTED_PHASE4_CONTRACT_SHA256 = (
    "b6d941b577881324d4dc5275681d90aced27deca6215055190c49f1ef6afd0ee"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_document_hash(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
        json.loads(str(record["output"]))


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
        if "si_training.jsonl" in source:
            raise ValueError(
                f"Notebook cell {cell_index} uses legacy dataset"
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
        "train": package_dir / "train.jsonl",
        "validation": package_dir / "validation.jsonl",
        "manifest": package_dir / "manifest.json",
        "contract": package_dir / "phase4_contract.json",
        "notebook": package_dir / "CerberusVision_Qwen_LoRA.ipynb",
        "guide": package_dir / "PHASE4_EGITIM_REHBERI.md",
    }
    missing_paths = [
        str(path)
        for path in required_paths.values()
        if not path.exists()
    ]
    if missing_paths:
        raise FileNotFoundError(
            "Missing Phase 4 package files: " + ", ".join(missing_paths)
        )
    legacy_path = package_dir / "si_training.jsonl"
    if legacy_path.exists():
        raise ValueError(
            f"Legacy combined dataset must be removed: {legacy_path}"
        )

    contract = json.loads(
        required_paths["contract"].read_text(encoding="utf-8")
    )
    contract_hash = file_sha256(required_paths["contract"])
    if contract_hash != EXPECTED_PHASE4_CONTRACT_SHA256:
        raise ValueError(
            f"Phase 4 contract hash mismatch: {contract_hash}"
        )
    manifest = json.loads(
        required_paths["manifest"].read_text(encoding="utf-8")
    )
    dataset_contract = contract["dataset"]
    actual_hashes = {
        "train.jsonl": file_sha256(required_paths["train"]),
        "validation.jsonl": file_sha256(required_paths["validation"]),
        "manifest.json": file_sha256(required_paths["manifest"]),
    }
    expected_hashes = {
        "train.jsonl": dataset_contract["train_sha256"],
        "validation.jsonl": dataset_contract["validation_sha256"],
        "manifest.json": dataset_contract["split_manifest_sha256"],
    }
    if actual_hashes != expected_hashes:
        raise ValueError(
            f"Phase 4 package hash mismatch: "
            f"expected={expected_hashes} actual={actual_hashes}"
        )
    if manifest["files"]["train.jsonl"] != actual_hashes["train.jsonl"]:
        raise ValueError("Split manifest train hash mismatch")
    if (
        manifest["files"]["validation.jsonl"]
        != actual_hashes["validation.jsonl"]
    ):
        raise ValueError("Split manifest validation hash mismatch")

    train_records = load_jsonl(required_paths["train"])
    validation_records = load_jsonl(required_paths["validation"])
    validate_records(train_records, "train")
    validate_records(validation_records, "validation")
    if len(train_records) != dataset_contract["train_records"]:
        raise ValueError("Phase 4 train record count mismatch")
    if len(validation_records) != dataset_contract["validation_records"]:
        raise ValueError("Phase 4 validation record count mismatch")

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
            f"Phase 4 train validation overlap detected: {len(overlap)}"
        )

    notebook_report = validate_notebook(required_paths["notebook"])
    return {
        "package_dir": str(package_dir.resolve()),
        "train_records": len(train_records),
        "validation_records": len(validation_records),
        "normalized_overlap": len(overlap),
        "hashes": actual_hashes,
        "contract_sha256": contract_hash,
        "notebook": notebook_report,
        "strategy": contract["training_strategy"],
        "legacy_adapter_policy": contract["legacy_adapter_policy"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the CerberusVision Phase 4 Colab package"
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=DEFAULT_PACKAGE_DIR,
    )
    args = parser.parse_args()
    report = validate_package(args.package_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
