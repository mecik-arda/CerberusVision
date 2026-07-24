from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 3407

LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "target_modules": [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
}

TRAINING_ARGS = {
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 4,
    "warmup_ratio": 0.05,
    "num_train_epochs": 10,
    "learning_rate": 2e-4,
    "fp16": True,
    "logging_steps": 10,
    "eval_strategy": "steps",
    "eval_steps": 10,
    "save_strategy": "steps",
    "save_steps": 10,
    "save_total_limit": 3,
    "load_best_model_at_end": True,
    "metric_for_best_model": "eval_loss",
    "greater_is_better": False,
    "seed": DEFAULT_SEED,
    "data_seed": DEFAULT_SEED,
    "report_to": "none",
}

QLORA_CONFIG = {
    "load_in_4bit": True,
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_compute_dtype": "float16",
    "bnb_4bit_use_double_quant": True,
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_records(jsonl_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, 1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            record = json.loads(stripped_line)
            missing_fields = {
                field_name
                for field_name in ("instructions", "input", "output")
                if not record.get(field_name)
            }
            if missing_fields:
                raise ValueError(
                    f"{jsonl_path}:{line_number} missing fields: "
                    + ",".join(sorted(missing_fields))
                )
            records.append(record)
    if not records:
        raise ValueError(f"Dataset is empty: {jsonl_path}")
    return records


def validate_manifest(
    manifest_path: Path,
    train_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = manifest.get("files", {})
    actual_hashes = {
        "train.jsonl": file_sha256(train_path),
        "validation.jsonl": file_sha256(validation_path),
    }
    for file_name, actual_hash in actual_hashes.items():
        expected_hash = expected_files.get(file_name)
        if expected_hash != actual_hash:
            raise ValueError(
                f"Manifest hash mismatch for {file_name}: "
                f"expected={expected_hash} actual={actual_hash}"
            )
    return manifest


def validate_split_inputs(
    train_records: list[dict[str, Any]],
    validation_records: list[dict[str, Any]],
) -> None:
    train_hashes = {
        hashlib.sha256(
            " ".join(record["input"].casefold().split()).encode("utf-8")
        ).hexdigest()
        for record in train_records
    }
    validation_hashes = {
        hashlib.sha256(
            " ".join(record["input"].casefold().split()).encode("utf-8")
        ).hexdigest()
        for record in validation_records
    }
    overlap = train_hashes & validation_hashes
    if overlap:
        raise ValueError(
            f"Train and validation contain {len(overlap)} exact normalized overlaps"
        )


def format_for_chat(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": record["instructions"]},
            {"role": "user", "content": record["input"]},
            {"role": "assistant", "content": record["output"]},
        ]
    }


def git_run_metadata() -> dict[str, Any]:
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    diff_result = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    status_text = status_result.stdout
    return {
        "commit_sha": commit_result.stdout.strip() or None,
        "working_tree_dirty": bool(status_text.strip()),
        "working_tree_status_sha256": hashlib.sha256(
            status_text.encode("utf-8")
        ).hexdigest(),
        "tracked_diff_sha256": hashlib.sha256(diff_result.stdout).hexdigest(),
    }


def build_run_metadata(
    base_model: str,
    train_path: Path,
    validation_path: Path,
    manifest_path: Path,
    train_records: list[dict[str, Any]],
    validation_records: list[dict[str, Any]],
    use_4bit: bool,
) -> dict[str, Any]:
    return {
        "git": git_run_metadata(),
        "base_model": base_model,
        "qlora": use_4bit,
        "datasets": {
            "train_path": str(train_path.resolve()),
            "train_sha256": file_sha256(train_path),
            "train_records": len(train_records),
            "validation_path": str(validation_path.resolve()),
            "validation_sha256": file_sha256(validation_path),
            "validation_records": len(validation_records),
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": file_sha256(manifest_path),
        },
        "lora_config": LORA_CONFIG,
        "training_args": TRAINING_ARGS,
    }


def load_model_with_quantization(
    base_model: str,
    use_4bit: bool = True,
) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if use_4bit:
        from transformers import BitsAndBytesConfig

        quantization_config = BitsAndBytesConfig(**QLORA_CONFIG)
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=quantization_config,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto",
        )
    if model is None or tokenizer is None or tokenizer.pad_token is None:
        raise RuntimeError("Model or tokenizer initialization failed")
    return model, tokenizer


def export_to_openvino(
    adapter_path: Path,
    base_model_id: str,
    output_path: Path,
) -> Path:
    import shutil
    import sys
    import tempfile

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if output_path.exists() and any(output_path.iterdir()):
        raise FileExistsError(
            f"OpenVINO output directory must be empty: {output_path}"
        )
    output_path.mkdir(parents=True, exist_ok=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    merged_model = model.merge_and_unload()
    with tempfile.TemporaryDirectory() as temporary_directory:
        merged_path = Path(temporary_directory) / "merged"
        merged_model.save_pretrained(str(merged_path))
        tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_path),
        )
        tokenizer.save_pretrained(str(merged_path))
        export_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "optimum.exporters.openvino",
                "--model",
                str(merged_path),
                "--task",
                "text-generation-with-past",
                "--weight-format",
                "int4",
                "--group-size",
                "128",
                "--ratio",
                "0.8",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        if export_result.returncode != 0:
            raise RuntimeError(
                f"OpenVINO export failed with exit {export_result.returncode}: "
                f"stdout={export_result.stdout} stderr={export_result.stderr}"
            )
    adapter_config = adapter_path / "adapter_config.json"
    if adapter_config.exists():
        shutil.copy2(
            str(adapter_config),
            str(output_path / "adapter_config.json"),
        )
    required_files = [
        output_path / "openvino_model.xml",
        output_path / "openvino_model.bin",
    ]
    missing_files = [str(path) for path in required_files if not path.exists()]
    if missing_files:
        raise RuntimeError(
            "OpenVINO export missing files: " + ", ".join(missing_files)
        )
    export_manifest = {
        path.name: file_sha256(path)
        for path in required_files
    }
    (output_path / "export_manifest.json").write_text(
        json.dumps(export_manifest, indent=2),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train Qwen LoRA with isolated train and validation data"
    )
    parser.add_argument("--train-data", type=Path, required=True)
    parser.add_argument("--validation-data", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--base-model",
        type=str,
        default="Qwen/Qwen2.5-7B-Instruct",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--export-openvino", type=Path)
    args = parser.parse_args()

    for required_path in (
        args.train_data,
        args.validation_data,
        args.manifest,
    ):
        if not required_path.exists():
            raise SystemExit(f"Required file not found: {required_path}")

    train_records = load_records(args.train_data)
    validation_records = load_records(args.validation_data)
    validate_manifest(
        args.manifest,
        args.train_data,
        args.validation_data,
    )
    validate_split_inputs(train_records, validation_records)
    run_metadata = build_run_metadata(
        args.base_model,
        args.train_data,
        args.validation_data,
        args.manifest,
        train_records,
        validation_records,
        args.qlora,
    )
    print(json.dumps(run_metadata, ensure_ascii=False, indent=2))

    if args.dry_run:
        return 0
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(
            f"Training output directory must be new or empty: {args.output}"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        from peft import LoraConfig, get_peft_model
        from transformers import (
            EarlyStoppingCallback,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as import_error:
        raise SystemExit(f"Missing training dependency: {import_error}")

    model, tokenizer = load_model_with_quantization(
        args.base_model,
        use_4bit=args.qlora,
    )
    model = get_peft_model(model, LoraConfig(**LORA_CONFIG))
    model.print_trainable_parameters()
    training_args = TrainingArguments(
        output_dir=str(args.output),
        **TRAINING_ARGS,
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=[format_for_chat(record) for record in train_records],
        eval_dataset=[
            format_for_chat(record) for record in validation_records
        ],
        tokenizer=tokenizer,
        max_seq_length=4096,
        callbacks=[
            EarlyStoppingCallback(early_stopping_patience=3)
        ],
    )
    trainer.train()
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    run_metadata["training_result"] = {
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_metric": trainer.state.best_metric,
        "global_step": trainer.state.global_step,
        "epoch": trainer.state.epoch,
    }
    (args.output / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.export_openvino is not None:
        export_to_openvino(
            args.output,
            args.base_model,
            args.export_openvino,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
