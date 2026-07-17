from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.models import ShippingInstruction
from app.utils.audit_logger import create_session_id, log_benchmark_report


SYSTEM_PROMPT = (
    "You are a shipping instruction document parser. "
    "Extract structured data from the OCR text of a shipping instruction / bill of lading document. "
    "Return ONLY valid JSON matching the provided schema. "
    "If a field is not present in the document, set it to null. "
    "Do not fabricate data."
)


def build_prompt(ocr_text: str) -> str:
    schema = ShippingInstruction.model_json_schema()
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    return (
        f"System: {SYSTEM_PROMPT}\n\n"
        f"JSON Schema:\n{schema_str}\n\n"
        f"OCR Text (layout-preserved):\n{ocr_text}\n\n"
        f"Extract the shipping instruction data as JSON:"
    )


def run_deepseek_inference(ocr_text: str) -> dict:
    from openai import OpenAI

    api_key = settings.deepseek.api_key
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key, base_url=settings.deepseek.base_url, timeout=120)
    prompt = build_prompt(ocr_text)

    response = client.chat.completions.create(
        model=settings.deepseek.model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2048,
        timeout=120,
    )

    raw_output = response.choices[0].message.content
    return {"raw_output": raw_output, "model": settings.deepseek.model_name}


def run_local_qwen_inference(ocr_text: str) -> dict:
    from app.llm.inference import run_guided_inference

    raw_output = run_guided_inference(ocr_text)
    return {"raw_output": raw_output, "model": "Qwen-2.5-14B-Instruct-INT4"}


def compare_results(local_result: dict, deepseek_result: dict) -> dict:
    comparison = {
        "local_valid_json": False,
        "deepseek_valid_json": False,
        "field_match_count": 0,
        "field_mismatch_count": 0,
        "field_details": [],
    }

    try:
        local_data = json.loads(local_result["raw_output"])
        local_si = ShippingInstruction.model_validate(local_data)
        comparison["local_valid_json"] = True
    except Exception as e:
        comparison["local_error"] = str(e)
        local_si = None

    try:
        deepseek_data = json.loads(deepseek_result["raw_output"])
        deepseek_si = ShippingInstruction.model_validate(deepseek_data)
        comparison["deepseek_valid_json"] = True
    except Exception as e:
        comparison["deepseek_error"] = str(e)
        deepseek_si = None

    if local_si and deepseek_si:
        local_dict = local_si.model_dump()
        deepseek_dict = deepseek_si.model_dump()

        all_keys = set(local_dict.keys()) | set(deepseek_dict.keys())
        for key in sorted(all_keys):
            local_val = local_dict.get(key)
            deepseek_val = deepseek_dict.get(key)
            match = local_val == deepseek_val
            if match:
                comparison["field_match_count"] += 1
            else:
                comparison["field_mismatch_count"] += 1
            comparison["field_details"].append({
                "field": key,
                "match": match,
                "local_value": str(local_val)[:200],
                "deepseek_value": str(deepseek_val)[:200],
            })

    return comparison


def main():
    parser = argparse.ArgumentParser(description="CerberusVision Benchmark: Local Qwen vs DeepSeek")
    parser.add_argument("--ocr-text", type=str, help="Path to OCR layout text file")
    parser.add_argument("--pdf", type=str, help="Path to PDF file (will run OCR first)")
    parser.add_argument("--output", type=str, help="Path to save benchmark report")
    args = parser.parse_args()

    if not args.ocr_text and not args.pdf:
        print("Error: Either --ocr-text or --pdf must be provided.")
        sys.exit(1)

    if args.ocr_text:
        ocr_text = Path(args.ocr_text).read_text(encoding="utf-8")
    else:
        from app.ocr.spatial_ocr import process_pdf_with_spatial_ocr
        ocr_text, _ = process_pdf_with_spatial_ocr(Path(args.pdf))

    session_id = create_session_id()
    print(f"Benchmark session: {session_id}")
    print(f"OCR text length: {len(ocr_text)} characters")

    print("\n[1/3] Running local Qwen inference...")
    try:
        local_result = run_local_qwen_inference(ocr_text)
        print(f"  Local output length: {len(local_result['raw_output'])} chars")
    except Exception as e:
        print(f"  Local inference failed: {e}")
        local_result = {"raw_output": "", "model": "Qwen-2.5-14B-Instruct-INT4", "error": str(e)}

    print("\n[2/3] Running DeepSeek inference...")
    try:
        deepseek_result = run_deepseek_inference(ocr_text)
        print(f"  DeepSeek output length: {len(deepseek_result['raw_output'])} chars")
    except Exception as e:
        print(f"  DeepSeek inference failed: {e}")
        deepseek_result = {"raw_output": "", "model": "deepseek-chat", "error": str(e)}

    print("\n[3/3] Comparing results...")
    comparison = compare_results(local_result, deepseek_result)
    print(f"  Local valid JSON:    {comparison['local_valid_json']}")
    print(f"  DeepSeek valid JSON: {comparison['deepseek_valid_json']}")
    print(f"  Field matches:       {comparison['field_match_count']}")
    print(f"  Field mismatches:    {comparison['field_mismatch_count']}")

    report_path = log_benchmark_report(session_id, local_result, deepseek_result, comparison)
    print(f"\nBenchmark report saved to: {report_path}")

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(
                {"session_id": session_id, "local": local_result, "deepseek": deepseek_result, "comparison": comparison},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Report also saved to: {output_path}")


if __name__ == "__main__":
    main()