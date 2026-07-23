import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.llm import inference as inference_module
from app.llm.evidence_validator import (
    EvidenceStatus,
    validate_field_evidence,
)
from scripts import benchmark_accuracy
from scripts import prepare_training_data
from scripts import train_lora


def _source_record(
    session_id: str,
    input_text: str,
    party_name: str,
) -> dict:
    return {
        "instructions": prepare_training_data.DEFAULT_INSTRUCTIONS,
        "input": input_text,
        "output": json.dumps(
            {
                "parties": [
                    {
                        "party_name": party_name,
                    }
                ]
            }
        ),
        "session_id": session_id,
        "source_hash": prepare_training_data.document_fingerprint(input_text),
    }


def test_prepare_splits_groups_sources_before_train_only_augmentation(
    monkeypatch,
    tmp_path,
):
    records = [
        _source_record(
            "session-a",
            "SHIPPER ALPHA LOGISTICS BOOKING A100 PORT IZMIR",
            "ALPHA LOGISTICS",
        ),
        _source_record(
            "session-a-repeat",
            "SHIPPER ALPHA LOGISTICS BOOKING A100 PORT IZMIR",
            "ALPHA LOGISTICS",
        ),
        _source_record(
            "session-b",
            "SHIPPER BETA SHIPPING BOOKING B200 PORT MERSIN",
            "BETA SHIPPING",
        ),
        _source_record(
            "session-c",
            "SHIPPER GAMMA TRADE BOOKING C300 PORT ANTALYA",
            "GAMMA TRADE",
        ),
    ]
    monkeypatch.setattr(
        prepare_training_data,
        "_load_source_records",
        lambda max_samples: (records, len(records), 0),
    )
    monkeypatch.setattr(
        prepare_training_data,
        "_load_fixture_texts",
        lambda fixture_dirs: [],
    )

    report = prepare_training_data.prepare_splits(
        output_dir=tmp_path,
        augment_factor=2,
        validation_ratio=0.34,
        seed=3407,
    )

    manifest = json.loads(
        (tmp_path / "manifest.json").read_text(encoding="utf-8")
    )
    train_lines = (
        tmp_path / "train.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    validation_lines = (
        tmp_path / "validation.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    train_groups = {
        record["source_group_id"]
        for record in manifest["records"]
        if record["split"] == "train"
    }
    validation_groups = {
        record["source_group_id"]
        for record in manifest["records"]
        if record["split"] == "validation"
    }

    assert train_groups.isdisjoint(validation_groups)
    assert len(train_lines) == report["train_source_records"] * 3
    assert len(validation_lines) == report["validation_records"]
    assert manifest["train_augmented_records"] == (
        report["train_source_records"] * 2
    )


def test_augmentation_that_matches_validation_is_skipped(
    monkeypatch,
    tmp_path,
):
    records = [
        _source_record(
            "session-train",
            "SHIPPER ALPHA LOGISTICS BOOKING A100 PORT IZMIR",
            "ALPHA LOGISTICS",
        ),
        _source_record(
            "session-validation",
            "SHIPPER BETA SHIPPING BOOKING B200 PORT MERSIN",
            "BETA SHIPPING",
        ),
    ]
    monkeypatch.setattr(
        prepare_training_data,
        "_load_source_records",
        lambda max_samples: (records, len(records), 0),
    )
    monkeypatch.setattr(
        prepare_training_data,
        "_load_fixture_texts",
        lambda fixture_dirs: [],
    )
    monkeypatch.setattr(
        prepare_training_data,
        "split_source_groups",
        lambda grouped_records, validation_ratio, seed: (
            grouped_records[:1],
            grouped_records[1:],
        ),
    )
    monkeypatch.setattr(
        prepare_training_data,
        "_clean_ocr_for_augmentation",
        lambda text, rng: records[1]["input"],
    )

    report = prepare_training_data.prepare_splits(
        output_dir=tmp_path,
        augment_factor=1,
        validation_ratio=0.5,
        seed=3407,
    )

    assert report["train_records"] == 1
    assert report["skipped_augmented_overlaps"] == 1


def test_forbidden_fixture_overlap_fails_closed():
    record = _source_record(
        "session-a",
        "SHIPPER ALPHA LOGISTICS BOOKING A100",
        "ALPHA LOGISTICS",
    )
    fixture = {
        "name": "sealed-holdout.json",
        "text": record["input"],
        "source_hash": record["source_hash"],
    }

    with pytest.raises(ValueError, match="Forbidden evaluation overlap"):
        prepare_training_data.assert_no_forbidden_overlap(
            [record],
            [fixture],
            0.9,
        )


def test_training_manifest_hashes_and_split_overlap_are_enforced(
    tmp_path,
):
    train_path = tmp_path / "train.jsonl"
    validation_path = tmp_path / "validation.jsonl"
    train_path.write_text(
        json.dumps(
            {
                "instructions": "Extract",
                "input": "TRAIN DOCUMENT ALPHA",
                "output": "{}",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    validation_path.write_text(
        json.dumps(
            {
                "instructions": "Extract",
                "input": "VALIDATION DOCUMENT BETA",
                "output": "{}",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    "train.jsonl": train_lora.file_sha256(train_path),
                    "validation.jsonl": train_lora.file_sha256(
                        validation_path
                    ),
                }
            }
        ),
        encoding="utf-8",
    )

    train_records = train_lora.load_records(train_path)
    validation_records = train_lora.load_records(validation_path)

    train_lora.validate_manifest(
        manifest_path,
        train_path,
        validation_path,
    )
    train_lora.validate_split_inputs(train_records, validation_records)

    validation_path.write_text(
        train_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="normalized overlaps"):
        train_lora.validate_split_inputs(
            train_records,
            train_lora.load_records(validation_path),
        )


def test_training_configuration_uses_early_stopping_compatible_steps():
    assert train_lora.TRAINING_ARGS["eval_strategy"] == "steps"
    assert train_lora.TRAINING_ARGS["save_strategy"] == "steps"
    assert train_lora.TRAINING_ARGS["eval_steps"] == 10
    assert train_lora.TRAINING_ARGS["save_steps"] == 10
    assert train_lora.TRAINING_ARGS["load_best_model_at_end"] is True
    assert train_lora.TRAINING_ARGS["metric_for_best_model"] == "eval_loss"
    assert train_lora.TRAINING_ARGS["greater_is_better"] is False
    assert train_lora.TRAINING_ARGS["warmup_ratio"] == 0.05


def test_frozen_ocr_hash_is_verified(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark_accuracy, "PROJECT_ROOT", tmp_path)
    fixture_path = tmp_path / "frozen.json"
    fixture_path.write_text(
        json.dumps(
            {
                "upper": "SHIPPER ALPHA",
                "middle": "PORT IZMIR",
                "lower": "BILL OF LADING",
            }
        ),
        encoding="utf-8",
    )
    expected_hash = benchmark_accuracy._sha256_bytes(
        fixture_path.read_bytes()
    )

    full_text, segmented, actual_hash = (
        benchmark_accuracy._load_frozen_ocr(
            "frozen.json",
            expected_hash,
        )
    )

    assert "SHIPPER ALPHA" in full_text
    assert segmented == (
        "SHIPPER ALPHA",
        "PORT IZMIR",
        "BILL OF LADING",
    )
    assert actual_hash == expected_hash

    with pytest.raises(ValueError, match="hash mismatch"):
        benchmark_accuracy._load_frozen_ocr(
            "frozen.json",
            "0" * 64,
        )


def test_fuzzy_evidence_marks_ocr_confusion_as_supported():
    result = validate_field_evidence(
        "parties[0].party_name",
        "FORENTIS GLOBAL",
        "SHIPPER: F0RENT1S GLOBAL",
    )

    assert result.status == EvidenceStatus.SUPPORTED
    assert result.evidence_score == 1.0
    assert result.method == "fuzzy_name_token_coverage"


def test_low_evidence_is_flagged_without_mutating_value():
    result = validate_field_evidence(
        "remarks",
        "CARGO RELEASED WITHOUT ORIGINAL DOCUMENTS",
        "SHIPPER ALPHA LOGISTICS",
    )

    assert result.status == EvidenceStatus.UNSUPPORTED
    assert result.value == "CARGO RELEASED WITHOUT ORIGINAL DOCUMENTS"
    assert result.evidence_score == 0.0


def test_multiline_address_uses_token_coverage():
    result = validate_field_evidence(
        "parties[0].address.street",
        "YESILYURT MAH 4306 SOK NO 3",
        "YESILYURT MAH.\n4306 S0K.\nNO:3",
    )

    assert result.status == EvidenceStatus.SUPPORTED
    assert result.method == "multiline_address_token_coverage"


def test_benchmark_provenance_distinguishes_llm_and_layout_adapter(
    tmp_path,
    monkeypatch,
):
    model_dir = tmp_path / "qwen_openvino"
    layout_adapter_dir = tmp_path / "florence_layout_adapter"
    model_dir.mkdir()
    layout_adapter_dir.mkdir()
    (model_dir / "model.xml").write_text("model", encoding="utf-8")
    (layout_adapter_dir / "adapter.json").write_text("adapter", encoding="utf-8")

    monkeypatch.setattr(
        benchmark_accuracy.settings.model,
        "model_path",
        str(model_dir),
    )
    monkeypatch.setattr(
        benchmark_accuracy.settings,
        "lora_adapter_path",
        str(layout_adapter_dir),
    )
    monkeypatch.setattr(benchmark_accuracy.settings, "lora_enabled", True)

    provenance = benchmark_accuracy._benchmark_provenance()

    assert provenance["llm_model"]["path"] == str(model_dir)
    assert provenance["llm_adapter"]["path"] is None
    assert provenance["llm_adapter"]["runtime_mode"] == "merged_openvino_model"
    assert provenance["layout_adapter"]["path"] == str(layout_adapter_dir)
    assert provenance["layout_lora_enabled"] is True


def test_benchmark_single_stream_configuration(
    tmp_path,
    monkeypatch,
):
    model_dir = tmp_path / "qwen_openvino"
    model_dir.mkdir()
    captured = {}

    def create_pipeline(model_path, device, config):
        captured["model_path"] = model_path
        captured["device"] = device
        captured["config"] = config
        return object()

    fake_openvino_genai = SimpleNamespace(LLMPipeline=create_pipeline)
    monkeypatch.setitem(sys.modules, "openvino_genai", fake_openvino_genai)
    monkeypatch.setattr(
        inference_module.settings.model,
        "model_path",
        str(model_dir),
    )
    monkeypatch.setenv("CERBERUS_BENCHMARK_DETERMINISTIC", "1")
    inference_module.reset_llm_pipeline()

    inference_module.get_llm_pipeline()

    assert captured["config"]["NUM_STREAMS"] == "1"
    assert "INFERENCE_NUM_THREADS" not in captured["config"]
    inference_module.reset_llm_pipeline()
