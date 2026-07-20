#!/usr/bin/env python3
"""Prepare a fine-tuning dataset from approved CerberusVision sessions.

Reads completed/approved sessions from logs/, extracts OCR text and
validated ground-truth JSON, and exports a JSONL file suitable for
OpenAI-compatible fine-tuning or PEFT/LoRA training.

Usage:
    python scripts/prepare_training_data.py --output data/si_training.jsonl
    python scripts/prepare_training_data.py --output data/si_training.jsonl --augment 3
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"


def _session_dirs() -> list[Path]:
    pattern = re.compile(r"^\d{8}_\d{6}_\d{6}$")
    return sorted(
        [p for p in LOGS_DIR.iterdir() if p.is_dir() and pattern.match(p.name)],
        reverse=True,
    )


def _load_ocr_text(session_dir: Path) -> str | None:
    path = session_dir / "ocr_layout_text.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _load_approved_json(session_dir: Path) -> dict[str, Any] | None:
    path = session_dir / "approved_instruction.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None


def _clean_ocr_for_augmentation(text: str) -> str:
    """Apply synthetic OCR-like perturbations to simulate varied inputs."""
    subs = [
        ("0", "O"), ("O", "0"), ("I", "1"), ("1", "I"),
        ("l", "1"), ("S", "5"), ("5", "S"), ("B", "8"),
        ("\n\n", "\n"), (",", "."), ("  ", " "),
    ]
    text_list = list(text)
    for _ in range(random.randint(1, 4)):
        old, new = random.choice(subs)
        text = text.replace(old, new)
    return text


def prepare_dataset(
    output_path: Path,
    augment_factor: int = 0,
    max_samples: int = 1000,
) -> dict[str, Any]:
    sessions = _session_dirs()
    records: list[dict[str, str]] = []
    skipped = 0

    for session_dir in sessions:
        if len(records) >= max_samples:
            break

        ocr_text = _load_ocr_text(session_dir)
        approved = _load_approved_json(session_dir)
        if not ocr_text or not approved or len(ocr_text) < 50:
            skipped += 1
            continue

        record = {
            "instructions": "Extract shipping instruction data from OCR text as JSON.",
            "input": ocr_text,
            "output": json.dumps(approved, ensure_ascii=False),
        }
        records.append(record)

        # Augment with synthetic OCR variations
        for i in range(augment_factor):
            if len(records) >= max_samples:
                break
            records.append({
                "instructions": record["instructions"],
                "input": _clean_ocr_for_augmentation(ocr_text),
                "output": record["output"],
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "records": len(records),
        "sessions_scanned": len(sessions),
        "skipped": skipped,
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare shipping-instruction fine-tuning dataset"
    )
    parser.add_argument("--output", type=Path, default=Path("veriler/si_training.jsonl"))
    parser.add_argument("--augment", type=int, default=0,
                        help="Synthetic OCR variation copies per real sample")
    parser.add_argument("--max-samples", type=int, default=1000)
    args = parser.parse_args()

    report = prepare_dataset(args.output, args.augment, args.max_samples)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
