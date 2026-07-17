from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from lxml import etree


SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xml", ".png", ".jpg", ".jpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_DOCUMENT_EXTENSIONS = {".docx", ".xml"}
_DOCX_XML_LIMIT = 16 * 1024 * 1024


class DocumentValidationError(ValueError):
    pass


class UploadSizeLimitError(ValueError):
    pass


class SizeLimitedReader:
    def __init__(self, raw_file, max_size: int):
        self.raw_file = raw_file
        self.max_size = max_size
        self.total = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.raw_file.read(size)
        self.total += len(chunk)
        if self.total > self.max_size:
            raise UploadSizeLimitError
        return chunk


def normalized_extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def validate_supported_filename(filename: str | None) -> str:
    extension = normalized_extension(filename)
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise DocumentValidationError(f"Unsupported file type. Supported: {supported}.")
    return extension


def copy_and_validate_upload(upload, destination: Path, max_size: int) -> str:
    extension = validate_supported_filename(upload.filename)
    source = upload.file
    source.seek(0)
    reader = SizeLimitedReader(source, max_size)
    try:
        with destination.open("wb") as output:
            shutil.copyfileobj(reader, output, length=1024 * 1024)
        validate_document(destination, extension)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return extension


def validate_document(path: Path, extension: str) -> None:
    with path.open("rb") as document:
        header = document.read(12)
    if extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise DocumentValidationError("The uploaded file is not a valid PDF.")
    if extension == ".png" and header[:8] != b"\x89PNG\r\n\x1a\n":
        raise DocumentValidationError("The uploaded file is not a valid PNG image.")
    if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
        raise DocumentValidationError("The uploaded file is not a valid JPEG image.")
    if extension == ".docx":
        _validate_docx(path)
    if extension == ".xml":
        _parse_xml(path)


def _validate_docx(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise DocumentValidationError("The uploaded file is not a valid DOCX document.")
            if archive.getinfo("word/document.xml").file_size > _DOCX_XML_LIMIT:
                raise DocumentValidationError("The DOCX document content is too large.")
    except (BadZipFile, KeyError) as error:
        raise DocumentValidationError("The uploaded file is not a valid DOCX document.") from error


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)


def _parse_xml(path: Path):
    try:
        return etree.parse(str(path), _xml_parser())
    except (etree.XMLSyntaxError, OSError) as error:
        raise DocumentValidationError("The uploaded file is not a valid XML document.") from error


def extract_text_document(path: Path, extension: str) -> str:
    if extension == ".docx":
        with ZipFile(path) as archive:
            content = archive.read("word/document.xml")
        root = etree.fromstring(content, _xml_parser())
        paragraphs = [" ".join(p.xpath(".//*[local-name()='t']/text()")).strip() for p in root.xpath(".//*[local-name()='p']")]
        return "\n".join(paragraph for paragraph in paragraphs if paragraph)
    tree = _parse_xml(path)
    lines = []
    for element in tree.getroot().iter():
        if not isinstance(element.tag, str):
            continue
        text = (element.text or "").strip()
        if text:
            lines.append(f"{etree.QName(element).localname}: {text}")
    return "\n".join(lines)
