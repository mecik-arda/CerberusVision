from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_training_data import (
    _load_fixture_texts,
    assert_no_forbidden_overlap,
    document_fingerprint,
)
from scripts.validate_phase4_colab_package import validate_package


DEFAULT_SOURCE_DIR = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "CerberusVision_Phase4_1_Colab"
DEFAULT_PARENT_ADAPTER_DIR = (
    PROJECT_ROOT / "models" / "Qwen-2.5-7B-Instruct-Phase4-LoRA"
)
BENCHMARK_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "qwen_benchmark"
BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
BASE_MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
PARENT_ADAPTER_SHA256 = (
    "ef99c4313a98dc1060e7aa97aa8b92962b13b24a65a6a8d7840c32095c0e5faf"
)
PARENT_ADAPTER_CONFIG_SHA256 = (
    "78cd1b0760239244d9036be3ca56224ec4515d141009c71f7fe71f68a5cadbcb"
)
TURKISH_TERMS = frozenset(
    {
        "alici",
        "alıcı",
        "bosaltma",
        "boşaltma",
        "brut",
        "gonderici",
        "gönderici",
        "konsimento",
        "konşimento",
        "limani",
        "limanı",
        "navlun",
        "talimat",
        "tarih",
        "vergi",
        "yukleme",
        "yükleme",
    }
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    serialized_records = [
        json.dumps(record, ensure_ascii=False, sort_keys=True)
        for record in records
    ]
    path.write_text("\n".join(serialized_records) + "\n", encoding="utf-8")


def _payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(str(record["output"]))
    if not isinstance(payload, dict):
        raise ValueError("Training output must be a JSON object")
    return payload


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def difficulty_features(record: dict[str, Any]) -> tuple[str, ...]:
    payload = _payload(record)
    input_text = str(record["input"])
    normalized_words = {
        word.casefold()
        for word in re.findall(r"[^\W\d_]+", input_text)
    }
    equipment_count = len(payload.get("equipment_list") or [])
    cargo_count = len(payload.get("cargo_items") or [])
    transport_fields = (
        payload.get("transport_plans"),
        payload.get("transport_document_type"),
        payload.get("freight_payment_term_code"),
    )
    populated_top_level = sum(
        1 for value in payload.values() if _has_value(value)
    )
    features: list[str] = []
    if not any(_has_value(value) for value in transport_fields):
        features.append("transport_negative")
    if normalized_words & TURKISH_TERMS:
        features.append("turkish")
    if equipment_count > 1:
        features.append("multi_equipment")
    if cargo_count > 1:
        features.append("multi_cargo")
    if len(input_text) >= 1800:
        features.append("long_document")
    if populated_top_level <= 4:
        features.append("sparse_optional_fields")
    if re.search(r"\b[A-Z]{2,}[0-9][A-Z0-9]{2,}\b", input_text):
        features.append("ocr_alphanumeric_noise")
    return tuple(features)


def difficulty_score(record: dict[str, Any]) -> int:
    weights = {
        "transport_negative": 10,
        "turkish": 8,
        "multi_equipment": 7,
        "multi_cargo": 7,
        "long_document": 5,
        "sparse_optional_fields": 6,
        "ocr_alphanumeric_noise": 4,
    }
    return sum(weights[feature] for feature in difficulty_features(record))


def select_hard_examples(
    records: list[dict[str, Any]],
    selected_count: int,
) -> list[dict[str, Any]]:
    if selected_count < 1 or selected_count > len(records):
        raise ValueError("Hard example count is outside dataset bounds")
    ranked_records = sorted(
        records,
        key=lambda record: (
            -difficulty_score(record),
            document_fingerprint(str(record["input"])),
            hashlib.sha256(str(record["output"]).encode("utf-8")).hexdigest(),
        ),
    )
    return ranked_records[:selected_count]


def _provenance_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **record,
            "session_id": f"phase4-replay-{record_index}",
            "source_hash": document_fingerprint(str(record["input"])),
        }
        for record_index, record in enumerate(records)
    ]


def _validate_parent_adapter(parent_adapter_dir: Path) -> dict[str, str]:
    adapter_model_path = parent_adapter_dir / "adapter_model.safetensors"
    adapter_config_path = parent_adapter_dir / "adapter_config.json"
    if not adapter_model_path.is_file() or not adapter_config_path.is_file():
        raise FileNotFoundError(
            f"Phase 4 parent adapter is incomplete: {parent_adapter_dir}"
        )
    actual_model_hash = file_sha256(adapter_model_path)
    actual_config_hash = file_sha256(adapter_config_path)
    if actual_model_hash != PARENT_ADAPTER_SHA256:
        raise ValueError(
            f"Phase 4 adapter hash mismatch: {actual_model_hash}"
        )
    if actual_config_hash != PARENT_ADAPTER_CONFIG_SHA256:
        raise ValueError(
            f"Phase 4 adapter config hash mismatch: {actual_config_hash}"
        )
    return {
        "adapter_model_sha256": actual_model_hash,
        "adapter_config_sha256": actual_config_hash,
    }


def build_continuation_package(
    source_dir: Path,
    output_dir: Path,
    parent_adapter_dir: Path,
) -> dict[str, Any]:
    source_report = validate_package(source_dir)
    parent_hashes = _validate_parent_adapter(parent_adapter_dir)
    source_train = load_jsonl(source_dir / "train.jsonl")
    validation_records = load_jsonl(source_dir / "validation.jsonl")
    hard_train_count = math.ceil(len(source_train) / 2)
    hard_validation_count = min(16, max(1, math.ceil(len(validation_records) / 2)))
    hard_train_records = select_hard_examples(
        source_train,
        hard_train_count,
    )
    hard_validation_records = select_hard_examples(
        validation_records,
        hard_validation_count,
    )
    continuation_train = [
        dict(record) for record in source_train
    ] + [
        dict(record) for record in hard_train_records
    ]
    forbidden_fixtures = _load_fixture_texts([BENCHMARK_FIXTURE_DIR])
    assert_no_forbidden_overlap(
        _provenance_records(source_train),
        forbidden_fixtures,
        0.92,
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Phase 4.1 output directory must be empty: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    continuation_train_path = output_dir / "continuation_train.jsonl"
    validation_path = output_dir / "validation.jsonl"
    hard_validation_path = output_dir / "hard_validation.jsonl"
    write_jsonl(continuation_train_path, continuation_train)
    write_jsonl(validation_path, validation_records)
    write_jsonl(hard_validation_path, hard_validation_records)
    feature_counts = Counter(
        feature
        for record in hard_train_records
        for feature in difficulty_features(record)
    )
    selection_manifest = {
        "schema_version": 1,
        "selection_method": "deterministic_weighted_hard_replay",
        "source_train_records": len(source_train),
        "hard_replay_records": len(hard_train_records),
        "continuation_train_records": len(continuation_train),
        "replay_ratio": round(
            len(source_train) / len(continuation_train),
            6,
        ),
        "hard_replay_ratio": round(
            len(hard_train_records) / len(continuation_train),
            6,
        ),
        "hard_validation_records": len(hard_validation_records),
        "hard_feature_counts": dict(sorted(feature_counts.items())),
        "hard_record_hashes": [
            document_fingerprint(str(record["input"]))
            for record in hard_train_records
        ],
        "hard_validation_hashes": [
            document_fingerprint(str(record["input"]))
            for record in hard_validation_records
        ],
    }
    selection_manifest_path = output_dir / "selection_manifest.json"
    selection_manifest_path.write_text(
        json.dumps(selection_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    contract = {
        "schema_version": 1,
        "phase": "4.1",
        "run_name": "cerberus_qwen25_7b_phase4_1_continual_v1",
        "training_strategy": "continual_qlora_from_phase4_adapter",
        "base_model": {
            "model_id": BASE_MODEL,
            "revision": BASE_MODEL_REVISION,
            "trust_remote_code": False,
        },
        "parent_adapter": {
            "directory_name": "phase4_adapter",
            **parent_hashes,
            "source_archive_sha256": (
                "9465948e92d7fe9b7a0a66b4de7c245801d1d86c6de231c0a85ee75c27656769"
            ),
            "legacy_adapter_used": False,
        },
        "dataset": {
            "continuation_train_file": continuation_train_path.name,
            "continuation_train_sha256": file_sha256(
                continuation_train_path
            ),
            "continuation_train_records": len(continuation_train),
            "validation_file": validation_path.name,
            "validation_sha256": file_sha256(validation_path),
            "validation_records": len(validation_records),
            "hard_validation_file": hard_validation_path.name,
            "hard_validation_sha256": file_sha256(
                hard_validation_path
            ),
            "hard_validation_records": len(hard_validation_records),
            "selection_manifest_file": selection_manifest_path.name,
            "selection_manifest_sha256": file_sha256(
                selection_manifest_path
            ),
            "benchmark_fixture_policy": "forbidden_from_training",
            "near_duplicate_threshold": 0.92,
        },
        "training": {
            "maximum_epochs": 2,
            "learning_rate": 0.00002,
            "per_device_train_batch_size": 4,
            "per_device_eval_batch_size": 4,
            "gradient_accumulation_steps": 4,
            "effective_batch_size": 16,
            "warmup_steps": 3,
            "weight_decay": 0.01,
            "evaluation_steps": 5,
            "save_steps": 5,
            "early_stopping_patience": 2,
            "early_stopping_threshold": 0.0002,
            "metric_for_best_model": "eval_loss",
            "greater_is_better": False,
            "completion_only_loss": True,
            "maximum_sequence_length": 2048,
        },
        "acceptance_gate": {
            "benchmark_cases": 13,
            "minimum_precision": 58.0,
            "minimum_recall": 90.0,
            "minimum_f1_score": 69.0,
            "minimum_xsd_valid_cases": 13,
            "maximum_inference_errors": 0,
            "maximum_deterministic_mismatches": 0,
        },
        "source_phase4_report": source_report,
    }
    contract_path = output_dir / "phase4_1_contract.json"
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    package_manifest = {
        "schema_version": 1,
        "phase": "4.1",
        "files": {
            continuation_train_path.name: file_sha256(
                continuation_train_path
            ),
            validation_path.name: file_sha256(validation_path),
            hard_validation_path.name: file_sha256(
                hard_validation_path
            ),
            selection_manifest_path.name: file_sha256(
                selection_manifest_path
            ),
            contract_path.name: file_sha256(contract_path),
        },
    }
    package_manifest_path = output_dir / "phase4_1_manifest.json"
    package_manifest_path.write_text(
        json.dumps(package_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "output_dir": str(output_dir.resolve()),
        "continuation_train_records": len(continuation_train),
        "replay_records": len(source_train),
        "hard_replay_records": len(hard_train_records),
        "validation_records": len(validation_records),
        "hard_validation_records": len(hard_validation_records),
        "benchmark_fixture_count": len(forbidden_fixtures),
        "parent_adapter_sha256": parent_hashes["adapter_model_sha256"],
        "manifest_sha256": file_sha256(package_manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Phase 4.1 continual QLoRA Colab package"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--parent-adapter-dir",
        type=Path,
        default=DEFAULT_PARENT_ADAPTER_DIR,
    )
    args = parser.parse_args()
    report = build_continuation_package(
        args.source_dir,
        args.output_dir,
        args.parent_adapter_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
