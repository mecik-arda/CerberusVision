#!/usr/bin/env python3
"""LoRA fine-tuning script for Qwen 2.5 7B on shipping instruction data.

Requires: peft, transformers, datasets, torch
GPU with ≥16 GB VRAM recommended.

Usage:
    python scripts/train_lora.py \
        --data veriler/si_training.jsonl \
        --base-model Qwen/Qwen2.5-7B-Instruct \
        --output models/qwen-7b-shipping-lora
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],
}

TRAINING_ARGS = {
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 4,
    "warmup_steps": 100,
    "num_train_epochs": 3,
    "learning_rate": 2e-4,
    "fp16": True,
    "logging_steps": 10,
    "save_steps": 200,
    "eval_steps": 200,
    "save_total_limit": 2,
    "load_best_model_at_end": True,
    "report_to": "none",
}

QLORA_CONFIG = {
    "load_in_4bit": True,
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_compute_dtype": "float16",
    "bnb_4bit_use_double_quant": True,
}


def load_dataset(jsonl_path: Path, train_split: float = 0.9) -> tuple[list, list]:
    """Load JSONL data and split into train/validation."""
    records = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    split = int(len(records) * train_split)
    return records[:split], records[split:]


def format_for_chat(record: dict) -> dict:
    """Format record as Qwen chat template."""
    return {
        "messages": [
            {"role": "system", "content": record["instructions"]},
            {"role": "user", "content": record["input"]},
            {"role": "assistant", "content": record["output"]},
        ]
    }


def load_model_with_quantization(
    base_model: str,
    use_4bit: bool = True,
) -> tuple:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if use_4bit:
        from transformers import BitsAndBytesConfig

        bnb_config = BitsAndBytesConfig(**QLORA_CONFIG)
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
    assert model is not None, "Model yuklenemedi"
    assert tokenizer is not None, "Tokenizer yuklenemedi"
    assert tokenizer.pad_token is not None, "Pad token ayarlanamadi"
    return model, tokenizer


def export_to_openvino(
    adapter_path: Path,
    base_model_id: str,
    output_path: Path,
) -> Path:
    import shutil
    import subprocess
    import sys
    import tempfile

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    output_path.mkdir(parents=True, exist_ok=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    merged = model.merge_and_unload()
    with tempfile.TemporaryDirectory() as tmpdir:
        merged_path = Path(tmpdir) / "merged"
        merged.save_pretrained(str(merged_path))
        tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_path), trust_remote_code=True
        )
        tokenizer.save_pretrained(str(merged_path))
        result = subprocess.run(
            [
                sys.executable, "-m", "optimum.exporters.openvino",
                "--model", str(merged_path),
                "--task", "text-generation-with-past",
                "--weight-format", "int4",
                "--group-size", "128",
                "--ratio", "0.8",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OpenVINO export basarisiz (exit {result.returncode}):\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
    adapter_config = adapter_path / "adapter_config.json"
    if adapter_config.exists():
        shutil.copy2(str(adapter_config), str(output_path / "adapter_config.json"))
    assert (output_path / "openvino_model.xml").exists(), (
        "openvino_model.xml olusturulamadi"
    )
    assert (output_path / "openvino_model.bin").exists(), (
        "openvino_model.bin olusturulamadi"
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LoRA fine-tune Qwen 2.5 for shipping instructions"
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--output", type=Path, default=Path("models/qwen-7b-shipping-lora"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate data only, skip training")
    parser.add_argument("--qlora", action="store_true",
                        help="Use QLoRA 4-bit quantization")
    parser.add_argument("--export-openvino", type=Path, default=None,
                        help="Export trained adapter to OpenVINO IR at this path")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Dataset not found: {args.data}")

    train_data, val_data = load_dataset(args.data)
    print(f"Train samples: {len(train_data)}")
    print(f"Validation samples: {len(val_data)}")
    print(f"LoRA config: {json.dumps(LORA_CONFIG, indent=2)}")
    print(f"Training args: {json.dumps(TRAINING_ARGS, indent=2)}")

    if args.dry_run:
        print("\nDry run complete. Data is valid. Use without --dry-run to train.")
        return 0

    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
        )
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
    except ImportError as e:
        raise SystemExit(
            f"Missing dependency: {e}\n"
            "Install with: pip install peft transformers datasets trl torch"
        )

    print(f"\nLoading base model: {args.base_model}")
    if args.qlora:
        print("QLoRA 4-bit quantization enabled")
    model, tokenizer = load_model_with_quantization(
        args.base_model, use_4bit=args.qlora
    )

    lora_config = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(args.output),
        eval_strategy="steps",
        **TRAINING_ARGS,
    )

    train_formatted = [format_for_chat(r) for r in train_data]
    val_formatted = [format_for_chat(r) for r in val_data]

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_formatted,
        eval_dataset=val_formatted,
        tokenizer=tokenizer,
        max_seq_length=4096,
    )

    print("\nStarting training...")
    trainer.train()

    # Save adapter
    model.save_pretrained(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    print(f"\nLoRA adapter saved to: {args.output}")
    if args.export_openvino:
        print(f"\nExporting to OpenVINO: {args.export_openvino}")
        ov_path = export_to_openvino(
            args.output, args.base_model, args.export_openvino
        )
        print(f"OpenVINO model exported to: {ov_path}")
    else:
        print(
            "\nTo use with OpenVINO: merge adapter, then convert with optimum-cli:\n"
            "  optimum-cli export openvino --model <merged-model> <output-dir>"
            "\nOr re-run with --export-openvino <output-dir>"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
