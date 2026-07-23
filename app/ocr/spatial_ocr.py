from __future__ import annotations
import io
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
from app.config import settings
from app.ocr.line_grouper import (
    build_line_text,
    group_boxes_into_lines,
    parse_ocr_boxes,
    reconstruct_layout_text,
    reconstruct_region_texts,
    segment_boxes_by_region,
    TextBox,
)

_BOTTOM_BOILERPLATE_RATIO = 0.8
_BOTTOM_BOILERPLATE_LINES = frozenset(
    {
        "bill of lading terms and conditions",
        "received by the carrier in apparent good order",
    }
)


def _normalize_boilerplate_line(text: str) -> str:
    return " ".join(text.split()).casefold()


def _filter_bottom_boilerplate_boxes(
    boxes: List[TextBox],
    page_height: float,
) -> List[TextBox]:
    if not boxes or page_height <= 0:
        return list(boxes)
    bottom_boundary = page_height * _BOTTOM_BOILERPLATE_RATIO
    excluded_box_ids: set[int] = set()
    for line_boxes in group_boxes_into_lines(boxes):
        if min(box.y_min for box in line_boxes) < bottom_boundary:
            continue
        line_text = _normalize_boilerplate_line(build_line_text(line_boxes))
        if line_text in _BOTTOM_BOILERPLATE_LINES:
            excluded_box_ids.update(id(box) for box in line_boxes)
    return [box for box in boxes if id(box) not in excluded_box_ids]


def _get_image_height(image_bytes: bytes) -> float:
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as image:
        return float(image.height)


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
    import io
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = ocr.ocr(np.array(img), cls=True)
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
        boxes = parse_ocr_boxes(raw_ocr)
        boxes = _filter_bottom_boilerplate_boxes(
            boxes,
            _get_image_height(img_bytes),
        )
        layout_text = reconstruct_layout_text(boxes)
        all_pages_text.append(layout_text)
        all_pages_boxes.append(boxes)
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join(all_pages_text)
    return combined_text, all_pages_boxes


def process_image_with_spatial_ocr(
    image_path: Path,
    lang: str = None,
) -> Tuple[str, List[List[TextBox]]]:
    image_bytes = image_path.read_bytes()
    raw_ocr = run_ocr_on_image(image_bytes, lang)
    boxes = parse_ocr_boxes(raw_ocr)
    boxes = _filter_bottom_boilerplate_boxes(
        boxes,
        _get_image_height(image_bytes),
    )
    layout_text = reconstruct_layout_text(boxes)
    return layout_text, [boxes]


def process_pdf_with_region_ocr(
    pdf_path: Path,
    lang: str = None,
    dpi: int = 200,
) -> Tuple[str, str, str, List[List[TextBox]]]:
    import fitz

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    upper_parts: List[str] = []
    middle_parts: List[str] = []
    lower_parts: List[str] = []
    all_pages_boxes: List[List[TextBox]] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            page_height = float(pix.height)
            raw_ocr = run_ocr_on_image(img_bytes, lang)
            boxes = parse_ocr_boxes(raw_ocr)
            boxes = _filter_bottom_boilerplate_boxes(boxes, page_height)
            all_pages_boxes.append(boxes)
            upper_text, middle_text, lower_text = reconstruct_region_texts(
                boxes, page_height
            )
            upper_parts.append(upper_text)
            middle_parts.append(middle_text)
            lower_parts.append(lower_text)
    assert all_pages_boxes, "PDF'den hic kutu cikarilamadi"
    assert len(all_pages_boxes) == len(upper_parts), (
        f"Sayfa sayisi tutarsiz: kutular=%d bolgeler=%d"
        % (len(all_pages_boxes), len(upper_parts))
    )
    combined_upper = "\n\n--- PAGE BREAK ---\n\n".join(upper_parts)
    combined_middle = "\n\n--- PAGE BREAK ---\n\n".join(middle_parts)
    combined_lower = "\n\n--- PAGE BREAK ---\n\n".join(lower_parts)
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(
        p for p in [combined_upper, combined_middle, combined_lower] if p.strip()
    )
    assert full_text.strip(), "Tum bolge metinleri bos"
    return combined_upper, combined_middle, combined_lower, all_pages_boxes


def process_pdf_with_florence_regions(
    pdf_path: Path,
    lang: str = None,
    dpi: int = 200,
    use_florence: bool = True,
) -> Tuple[str, str, str, List[List[TextBox]], Optional[Dict]]:
    import fitz

    from app.ocr.vlm_region import (
        detect_regions_with_florence,
        map_florence_regions_to_paddle_boxes,
    )

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    upper_parts: List[str] = []
    middle_parts: List[str] = []
    lower_parts: List[str] = []
    all_pages_boxes: List[List[TextBox]] = []
    florence_meta: Dict[str, Any] = {"pages": []}
    with fitz.open(str(pdf_path)) as doc:
        for page_idx, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            page_height = float(pix.height)
            raw_ocr = run_ocr_on_image(img_bytes, lang)
            boxes = parse_ocr_boxes(raw_ocr)
            boxes = _filter_bottom_boilerplate_boxes(boxes, page_height)
            all_pages_boxes.append(boxes)
            if use_florence and boxes:
                try:
                    florence_result = detect_regions_with_florence(img_bytes)
                    florence_meta["pages"].append({
                        "page": page_idx,
                        "text_regions": len(florence_result.get("text_regions", [])),
                        "tables": len(florence_result.get("tables", [])),
                    })
                    up, mid, low = map_florence_regions_to_paddle_boxes(
                        florence_result, boxes, page_height
                    )
                except Exception:
                    logger.warning(
                        "Florence-2 sayfa %d icin basarisiz, Y-orani yontemine dusuluyor",
                        page_idx,
                    )
                    florence_meta["pages"].append({
                        "page": page_idx, "error": "florence_failed"
                    })
                    up, mid, low = segment_boxes_by_region(boxes, page_height)
            else:
                up, mid, low = segment_boxes_by_region(boxes, page_height)
            upper_text = reconstruct_layout_text(up)
            middle_text = reconstruct_layout_text(mid)
            lower_text = reconstruct_layout_text(low)
            upper_parts.append(upper_text)
            middle_parts.append(middle_text)
            lower_parts.append(lower_text)
    assert all_pages_boxes, "PDF'den hic kutu cikarilamadi"
    assert len(all_pages_boxes) == len(upper_parts), (
        f"Sayfa sayisi tutarsiz: kutular=%d bolgeler=%d"
        % (len(all_pages_boxes), len(upper_parts))
    )
    combined_upper = "\n\n--- PAGE BREAK ---\n\n".join(upper_parts)
    combined_middle = "\n\n--- PAGE BREAK ---\n\n".join(middle_parts)
    combined_lower = "\n\n--- PAGE BREAK ---\n\n".join(lower_parts)
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(
        p for p in [combined_upper, combined_middle, combined_lower] if p.strip()
    )
    assert full_text.strip(), "Tum bolge metinleri bos"
    return (
        combined_upper,
        combined_middle,
        combined_lower,
        all_pages_boxes,
        florence_meta,
    )
