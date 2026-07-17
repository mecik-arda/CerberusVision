from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
from app.config import settings


@dataclass
class TextBox:
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2.0

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2.0

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


def parse_ocr_boxes(raw_results: List) -> List[TextBox]:
    boxes: List[TextBox] = []
    if not raw_results:
        return boxes
    for entry in raw_results:
        if not entry or len(entry) < 2:
            continue
        box_coords = entry[0]
        text_info = entry[1]
        if not box_coords or not text_info:
            continue
        text = text_info[0] if isinstance(text_info, (list, tuple)) and len(text_info) > 0 else str(text_info)
        xs = [pt[0] for pt in box_coords]
        ys = [pt[1] for pt in box_coords]
        boxes.append(
            TextBox(
                text=text,
                x_min=min(xs),
                y_min=min(ys),
                x_max=max(xs),
                y_max=max(ys),
            )
        )
    return boxes


def group_boxes_into_lines(
    boxes: List[TextBox],
    y_threshold: float = None,
) -> List[List[TextBox]]:
    if not boxes:
        return []
    if y_threshold is None:
        y_threshold = settings.line_grouping_y_threshold
    sorted_by_y = sorted(boxes, key=lambda b: b.center_y)
    lines: List[List[TextBox]] = []
    current_line: List[TextBox] = [sorted_by_y[0]]
    line_anchor_y = sorted_by_y[0].center_y
    for box in sorted_by_y[1:]:
        if abs(box.center_y - line_anchor_y) <= y_threshold:
            current_line.append(box)
        else:
            lines.append(current_line)
            current_line = [box]
            line_anchor_y = box.center_y
    if current_line:
        lines.append(current_line)
    return lines


def build_line_text(
    line_boxes: List[TextBox],
    space_factor: float = None,
) -> str:
    if not line_boxes:
        return ""
    if space_factor is None:
        space_factor = settings.horizontal_space_factor
    sorted_boxes = sorted(line_boxes, key=lambda b: b.x_min)
    parts: List[str] = []
    for i, box in enumerate(sorted_boxes):
        if i == 0:
            parts.append(box.text)
            continue
        prev_box = sorted_boxes[i - 1]
        gap = box.x_min - prev_box.x_max
        avg_char_width = max(prev_box.width / max(len(prev_box.text), 1), 1.0)
        num_spaces = max(1, int(gap / avg_char_width * space_factor))
        parts.append(" " * num_spaces + box.text)
    return "".join(parts)


def reconstruct_layout_text(
    boxes: List[TextBox],
    y_threshold: float = None,
    space_factor: float = None,
) -> str:
    lines = group_boxes_into_lines(boxes, y_threshold)
    page_texts: List[str] = []
    for line in lines:
        page_texts.append(build_line_text(line, space_factor))
    return "\n".join(page_texts)


def process_ocr_results_to_layout_text(
    raw_results: List,
    y_threshold: float = None,
    space_factor: float = None,
) -> Tuple[str, List[TextBox]]:
    boxes = parse_ocr_boxes(raw_results)
    layout_text = reconstruct_layout_text(boxes, y_threshold, space_factor)
    return layout_text, boxes