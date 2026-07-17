from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_MODULES = (
    "fastapi",
    "fitz",
    "lxml",
    "openvino",
    "openvino_genai",
    "paddleocr",
    "paddle",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="CerberusVision WSL smoke checks")
    parser.add_argument("--pdf", type=Path, help="Run OCR against a PDF")
    parser.add_argument(
        "--require-model", action="store_true", help="Fail when QWEN_MODEL_PATH is absent"
    )
    parser.add_argument(
        "--probe-model", action="store_true", help="Load the model and generate a short response"
    )
    args = parser.parse_args()

    report: dict[str, object] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "wsl": "microsoft" in platform.release().lower(),
        "modules": {},
    }
    failed = False
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            report["modules"][name] = "ok"  # type: ignore[index]
        except Exception as error:
            report["modules"][name] = f"error: {error}"  # type: ignore[index]
            failed = True

    try:
        from openvino import Core

        report["openvino_devices"] = Core().available_devices
    except Exception as error:
        report["openvino_devices"] = [f"error: {error}"]
        failed = True

    model_path = Path(
        os.environ.get(
            "QWEN_MODEL_PATH", "models/Qwen-2.5-7B-Instruct-INT4"
        )
    ).expanduser()
    report["model_path"] = str(model_path)
    report["model_present"] = model_path.exists()
    if args.require_model and not model_path.exists():
        failed = True

    if args.probe_model:
        if not model_path.exists():
            report["model_probe"] = "error: model path is absent"
            failed = True
        else:
            try:
                from app.llm.inference import get_llm_pipeline

                pipeline = get_llm_pipeline()
                response = pipeline.generate("Reply with only OK.", max_new_tokens=8)
                report["model_probe"] = {"status": "ok", "response": str(response)}
            except Exception as error:
                report["model_probe"] = f"error: {error}"
                failed = True

    if args.pdf:
        from app.ocr.spatial_ocr import process_pdf_with_spatial_ocr

        text, boxes = process_pdf_with_spatial_ocr(args.pdf)
        report["ocr"] = {
            "characters": len(text),
            "pages": len(boxes),
            "boxes": sum(len(page) for page in boxes),
        }
        if not text.strip():
            failed = True

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
