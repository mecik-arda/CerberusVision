from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm.evaluation import aggregate_evaluations, evaluate_expected_fields
from app.llm.inference import run_inference_with_fallback


def evaluate_case(path: Path) -> dict:
    case = json.loads(path.read_text(encoding="utf-8"))
    instruction, raw_output = run_inference_with_fallback(
        case["ocr_text"],
        case.get("document_language", "auto"),
        case.get("output_language", "en"),
    )
    result = evaluate_expected_fields(
        case["expected"],
        instruction.model_dump(mode="json"),
    )
    result["case"] = path.name
    result["raw_output"] = raw_output
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path("tests/fixtures/qwen_benchmark"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case_paths = sorted(args.dataset.glob("*.json"))
    if not case_paths:
        raise SystemExit(f"No benchmark cases found in {args.dataset}")
    report = aggregate_evaluations([evaluate_case(path) for path in case_paths])
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
