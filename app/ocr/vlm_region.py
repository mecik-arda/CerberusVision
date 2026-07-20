from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.ocr.line_grouper import TextBox, segment_boxes_by_region

logger = logging.getLogger(__name__)

_florence_pipeline = None


def get_florence_pipeline():
    global _florence_pipeline
    if _florence_pipeline is not None:
        return _florence_pipeline
    import torch
    from transformers import AutoProcessor, AutoModelForCausalLM

    model_id = "microsoft/Florence-2-base"
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        trust_remote_code=True,
    ).to("cpu")
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    _florence_pipeline = (model, processor)
    assert model is not None, "Florence-2 modeli yuklenemedi"
    assert processor is not None, "Florence-2 processor yuklenemedi"
    return _florence_pipeline


def reset_florence_pipeline() -> None:
    global _florence_pipeline
    _florence_pipeline = None


def detect_regions_with_florence(
    image_bytes: bytes,
) -> Dict[str, Any]:
    import io

    from PIL import Image

    model, processor = get_florence_pipeline()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_width, img_height = image.size
    task_prompt = "<OD>"
    inputs = processor(text=task_prompt, images=image, return_tensors="pt")
    generated_ids = model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=1024,
        num_beams=3,
        do_sample=False,
    )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    result = processor.post_process_generation(
        generated_text, task=task_prompt, image_size=(img_width, img_height)
    )
    parsed = result.get(task_prompt, {})
    labels_list = parsed.get("labels", [])
    bboxes_list = parsed.get("bboxes", [])
    text_regions: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    for label, bbox in zip(labels_list, bboxes_list):
        region = {"label": label, "bbox": bbox}
        if label in ("table", "table column", "table row", "table cell"):
            tables.append(region)
        else:
            text_regions.append(region)
    for bbox in bboxes_list:
        assert len(bbox) == 4, f"Florence bounding box format hatasi: {bbox}"
        assert bbox[0] < bbox[2] and bbox[1] < bbox[3], (
            f"Florence gecersiz bounding box: {bbox}"
        )
    return {
        "text_regions": text_regions,
        "tables": tables,
        "image_width": img_width,
        "image_height": img_height,
    }


def map_florence_regions_to_paddle_boxes(
    florence_result: Dict[str, Any],
    paddle_boxes: List[TextBox],
    page_height: float,
) -> Tuple[List[TextBox], List[TextBox], List[TextBox]]:
    tables = florence_result.get("tables", [])
    text_regions = florence_result.get("text_regions", [])
    upper_boxes: List[TextBox] = []
    middle_boxes: List[TextBox] = []
    lower_boxes: List[TextBox] = []
    assigned_indices: set[int] = set()
    table_regions = []
    for table in tables:
        bbox = table["bbox"]
        table_regions.append((bbox[1], bbox[3], bbox[0], bbox[2]))
    header_regions = []
    for region in text_regions:
        label = region.get("label", "")
        bbox = region["bbox"]
        if label in ("title", "header", "section-header"):
            header_regions.append((bbox[1], bbox[3], bbox[0], bbox[2]))
    for i, box in enumerate(paddle_boxes):
        box_center_x = box.center_x
        box_center_y = box.center_y
        assigned = False
        for top, bottom, left, right in table_regions:
            if top <= box_center_y <= bottom and left <= box_center_x <= right:
                lower_boxes.append(box)
                assigned_indices.add(i)
                assigned = True
                break
        if assigned:
            continue
        for top, bottom, left, right in header_regions:
            if top <= box_center_y <= bottom and left <= box_center_x <= right:
                upper_boxes.append(box)
                assigned_indices.add(i)
                assigned = True
                break
    remaining_boxes = [
        box for i, box in enumerate(paddle_boxes) if i not in assigned_indices
    ]
    if remaining_boxes:
        ru, rm, rl = segment_boxes_by_region(remaining_boxes, page_height)
        upper_boxes.extend(ru)
        middle_boxes.extend(rm)
        lower_boxes.extend(rl)
    total = len(upper_boxes) + len(middle_boxes) + len(lower_boxes)
    assert total == len(paddle_boxes), (
        f"Florence esleme kutu kaybina yol acti: "
        f"ust={len(upper_boxes)} orta={len(middle_boxes)} "
        f"alt={len(lower_boxes)} toplam={total} beklenen={len(paddle_boxes)}"
    )
    assigned_ids = set()
    for box in upper_boxes:
        assigned_ids.add(id(box))
    for box in middle_boxes:
        assigned_ids.add(id(box))
    for box in lower_boxes:
        assigned_ids.add(id(box))
    for box in paddle_boxes:
        assert id(box) in assigned_ids, f"Kutu kayboldu: {box.text[:30]}"
    return upper_boxes, middle_boxes, lower_boxes
