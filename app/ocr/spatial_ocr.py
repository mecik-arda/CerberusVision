from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from typing import List, Optional, Tuple
from app.config import settings
from app.ocr.line_grouper import process_ocr_results_to_layout_text, TextBox


@lru_cache(maxsize=2)
def _get_cached_ocr_engine(lang: str):
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)


def get_ocr_engine(lang: str = None):
    return _get_cached_ocr_engine(lang or settings.ocr_lang)


def render_pdf_pages_to_images(
    pdf_path: Path,
    dpi: int = 200,
) -> List[bytes]:
    import fitz

    images: List[bytes] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
    return images


def run_ocr_on_image(image_bytes: bytes, lang: str = None) -> List:
    ocr = get_ocr_engine(lang)
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        result = ocr.ocr(tmp_path, cls=True)
    finally:
        os.unlink(tmp_path)
    if result and isinstance(result, list) and len(result) > 0:
        return result[0] if isinstance(result[0], list) else result
    return []


def process_pdf_with_spatial_ocr(
    pdf_path: Path,
    lang: str = None,
    dpi: int = 200,
) -> Tuple[str, List[List[TextBox]]]:
    images = render_pdf_pages_to_images(pdf_path, dpi)
    all_pages_text: List[str] = []
    all_pages_boxes: List[List[TextBox]] = []
    for img_bytes in images:
        raw_ocr = run_ocr_on_image(img_bytes, lang)
        layout_text, boxes = process_ocr_results_to_layout_text(raw_ocr)
        all_pages_text.append(layout_text)
        all_pages_boxes.append(boxes)
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join(all_pages_text)
    return combined_text, all_pages_boxes


def process_image_with_spatial_ocr(
    image_path: Path,
    lang: str = None,
) -> Tuple[str, List[List[TextBox]]]:
    raw_ocr = run_ocr_on_image(image_path.read_bytes(), lang)
    layout_text, boxes = process_ocr_results_to_layout_text(raw_ocr)
    return layout_text, [boxes]
