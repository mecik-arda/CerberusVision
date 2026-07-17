from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.llm.cloud_inference import run_deepseek_review
from app.llm.inference import run_inference_with_fallback
from app.llm.local_audit import assess_local_result, should_run_automatic_cloud_review
from app.utils.audit_logger import create_session_id, log_cloud_review_report
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import check_mandatory_fields, validate_xml_against_xsd


def main():
    parser = argparse.ArgumentParser(
        description="CerberusVision audit: local Qwen plus short DeepSeek review"
    )
    parser.add_argument("--ocr-text", type=str, help="Path to OCR layout text file")
    parser.add_argument("--pdf", type=str, help="Path to PDF file (runs OCR first)")
    parser.add_argument("--output", type=str, help="Path to save audit report")
    parser.add_argument(
        "--cloud-review",
        action="store_true",
        help="Force one short DeepSeek review unless cloud review mode is off",
    )
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
    print(f"Audit session: {session_id}")
    print("[1/3] Running local Qwen inference...")
    instruction, local_raw_output = run_inference_with_fallback(ocr_text)

    print("[2/3] Running deterministic local checks...")
    xml_content = shipping_instruction_to_xml(instruction)
    is_xsd_valid, errors = validate_xml_against_xsd(xml_content)
    missing_fields = check_mandatory_fields(instruction)
    assessment = assess_local_result(
        instruction,
        ocr_text,
        is_xsd_valid,
        errors,
        missing_fields,
    )

    review = None
    raw_review = None
    sent_payload = None
    review_error = None
    cloud_requested = bool(settings.deepseek.api_key) and (
        settings.deepseek.review_mode != "off"
        and (
            args.cloud_review
            or should_run_automatic_cloud_review(
                assessment,
                settings.deepseek.api_key,
                settings.deepseek.review_mode,
            )
        )
    )
    if cloud_requested:
        print("[3/3] Running short DeepSeek audit (no extraction or corrections)...")
        try:
            review, raw_review, sent_payload = run_deepseek_review(
                instruction, assessment, ocr_text
            )
        except Exception as error:
            review_error = str(error)
            print(f"  DeepSeek review failed: {error}")
    else:
        print("[3/3] DeepSeek skipped by key, mode, or local-risk policy.")

    report_path = log_cloud_review_report(
        session_id,
        local_assessment=assessment.model_dump(mode="json"),
        cloud_review_used=review is not None,
        review=review.model_dump(mode="json") if review else None,
        sent_payload=sent_payload,
        raw_output=raw_review,
        error=review_error,
        label="manual",
    )
    report = {
        "session_id": session_id,
        "local_model": Path(settings.model.model_path).name,
        "local_device": settings.model.device,
        "local_raw_output": local_raw_output,
        "local_assessment": assessment.model_dump(mode="json"),
        "cloud_review": review.model_dump(mode="json") if review else None,
        "cloud_review_used": review is not None,
        "error": review_error,
    }
    print(f"Local risk score: {assessment.risk_score}")
    if review:
        print(f"DeepSeek audit score: {review.score}")
        print(f"DeepSeek summary: {review.summary}")
    print(f"Audit report saved to: {report_path}")

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Report also saved to: {output_path}")


if __name__ == "__main__":
    main()
