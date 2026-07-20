import io
import json
from zipfile import ZipFile

import pytest
from fastapi import UploadFile

from app.config import settings
from app.document_ingestion import (
    DocumentValidationError,
    copy_and_validate_upload,
    extract_text_document,
    validate_supported_filename,
)
from app.models import ProcessingStatus
from app.routes import processing
from tests.test_validator import create_complete_si


@pytest.fixture(autouse=True)
def isolate_qwen_post_processing(monkeypatch):
    monkeypatch.setattr(settings.model, "refinement_enabled", False)
    monkeypatch.setattr(
        processing,
        "translate_instruction_content",
        lambda instruction, output_language: (instruction, ""),
    )


def _docx_bytes(text: str) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("sample.pdf", b"%PDF-1.7\n"),
        ("sample.png", b"\x89PNG\r\n\x1a\ncontent"),
        ("sample.jpg", b"\xff\xd8\xff\xe0content"),
        ("sample.jpeg", b"\xff\xd8\xff\xe1content"),
        ("sample.xml", b"<?xml version='1.0'?><root><port>Karachi</port></root>"),
    ],
)
def test_copy_and_validate_supported_documents(tmp_path, filename, content):
    upload = UploadFile(filename=filename, file=io.BytesIO(content))
    destination = tmp_path / filename

    extension = copy_and_validate_upload(upload, destination, 1024 * 1024)

    assert extension == destination.suffix
    assert destination.read_bytes() == content


def test_docx_text_is_extracted_without_office_dependency(tmp_path):
    content = _docx_bytes("PORT OF DISCHARGE KARACHI")
    upload = UploadFile(filename="shipping.docx", file=io.BytesIO(content))
    destination = tmp_path / "shipping.docx"

    copy_and_validate_upload(upload, destination, 1024 * 1024)

    assert extract_text_document(destination, ".docx") == "PORT OF DISCHARGE KARACHI"


def test_xml_text_preserves_element_names(tmp_path):
    destination = tmp_path / "shipping.xml"
    destination.write_text(
        "<shipping><portOfLoading>Aliaga</portOfLoading><portOfDischarge>Karachi</portOfDischarge></shipping>",
        encoding="utf-8",
    )

    text = extract_text_document(destination, ".xml")

    assert "portOfLoading: Aliaga" in text
    assert "portOfDischarge: Karachi" in text


def test_unsupported_and_malformed_documents_are_rejected(tmp_path):
    with pytest.raises(DocumentValidationError, match="Unsupported file type"):
        validate_supported_filename("malware.exe")

    upload = UploadFile(filename="broken.xml", file=io.BytesIO(b"<broken>"))
    destination = tmp_path / "broken.xml"
    with pytest.raises(DocumentValidationError, match="not a valid XML"):
        copy_and_validate_upload(upload, destination, 1024)
    assert not destination.exists()


@pytest.mark.asyncio
async def test_xml_pipeline_bypasses_ocr_and_runs_inference(tmp_path, monkeypatch):
    instruction = create_complete_si()
    document_path = tmp_path / "source.xml"
    document_path.write_text(
        "<shipping><portOfLoading>Aliaga</portOfLoading><portOfDischarge>Karachi</portOfDischarge></shipping>",
        encoding="utf-8",
    )
    queue = processing.asyncio.Queue()

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", None)
    monkeypatch.setattr(settings.deepseek, "review_mode", "off")
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda *args: (_ for _ in ()).throw(AssertionError("PDF OCR must not run")),
    )
    monkeypatch.setattr(
        processing,
        "process_image_with_spatial_ocr",
        lambda *args: (_ for _ in ()).throw(AssertionError("Image OCR must not run")),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text, document_language, output_language: (
            instruction,
            instruction.model_dump_json(),
        ),
    )

    await processing.process_document_pipeline(
        document_path,
        "xml-pipeline-test",
        "source.xml",
        queue,
    )

    events = []
    while True:
        item = queue.get_nowait()
        if item is None:
            break
        events.append(json.loads(item))

    assert events[-1]["status"] == ProcessingStatus.COMPLETED.value
    assert "portOfLoading: Aliaga" in events[-1]["data"]["raw_ocr_text"]
    assert not document_path.exists()
    processing._processing_store.pop("xml-pipeline-test", None)
    processing._session_models.pop("xml-pipeline-test", None)
