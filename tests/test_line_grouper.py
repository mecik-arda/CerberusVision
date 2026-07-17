import pytest
from app.ocr.line_grouper import (
    TextBox,
    parse_ocr_boxes,
    group_boxes_into_lines,
    build_line_text,
    reconstruct_layout_text,
    process_ocr_results_to_layout_text,
)


class TestTextBox:
    def test_center_y(self):
        box = TextBox(text="hello", x_min=0, y_min=10, x_max=20, y_max=30)
        assert box.center_y == 20.0

    def test_center_x(self):
        box = TextBox(text="hello", x_min=0, y_min=10, x_max=20, y_max=30)
        assert box.center_x == 10.0

    def test_width(self):
        box = TextBox(text="hello", x_min=0, y_min=10, x_max=20, y_max=30)
        assert box.width == 20.0

    def test_height(self):
        box = TextBox(text="hello", x_min=0, y_min=10, x_max=20, y_max=30)
        assert box.height == 20.0


class TestParseOcrBoxes:
    def test_parse_valid_results(self):
        raw_results = [
            [
                [[0, 0], [50, 0], [50, 20], [0, 20]],
                ["hello", 0.95],
            ],
            [
                [[60, 0], [100, 0], [100, 20], [60, 20]],
                ["world", 0.90],
            ],
        ]
        boxes = parse_ocr_boxes(raw_results)
        assert len(boxes) == 2
        assert boxes[0].text == "hello"
        assert boxes[1].text == "world"

    def test_parse_empty_results(self):
        assert parse_ocr_boxes([]) == []
        assert parse_ocr_boxes(None) == []

    def test_parse_malformed_entry(self):
        raw_results = [
            None,
            [],
            [[[0, 0], [10, 0], [10, 10], [0, 10]], ["valid", 0.9]],
        ]
        boxes = parse_ocr_boxes(raw_results)
        assert len(boxes) == 1
        assert boxes[0].text == "valid"


class TestGroupBoxesIntoLines:
    def test_group_single_line(self):
        boxes = [
            TextBox(text="A", x_min=0, y_min=0, x_max=10, y_max=10),
            TextBox(text="B", x_min=20, y_min=2, x_max=30, y_max=12),
            TextBox(text="C", x_min=40, y_min=1, x_max=50, y_max=11),
        ]
        lines = group_boxes_into_lines(boxes, y_threshold=15.0)
        assert len(lines) == 1
        assert len(lines[0]) == 3

    def test_group_multiple_lines(self):
        boxes = [
            TextBox(text="A", x_min=0, y_min=0, x_max=10, y_max=10),
            TextBox(text="B", x_min=0, y_min=50, x_max=10, y_max=60),
            TextBox(text="C", x_min=20, y_min=52, x_max=30, y_max=62),
        ]
        lines = group_boxes_into_lines(boxes, y_threshold=15.0)
        assert len(lines) == 2
        assert lines[0][0].text == "A"
        assert len(lines[1]) == 2

    def test_group_empty(self):
        assert group_boxes_into_lines([]) == []

    def test_group_single_box(self):
        boxes = [TextBox(text="solo", x_min=0, y_min=0, x_max=10, y_max=10)]
        lines = group_boxes_into_lines(boxes, y_threshold=15.0)
        assert len(lines) == 1
        assert len(lines[0]) == 1


class TestBuildLineText:
    def test_build_adjacent_boxes(self):
        boxes = [
            TextBox(text="hello", x_min=0, y_min=0, x_max=30, y_max=10),
            TextBox(text="world", x_min=35, y_min=0, x_max=65, y_max=10),
        ]
        text = build_line_text(boxes, space_factor=0.15)
        assert "hello" in text
        assert "world" in text
        assert text.index("hello") < text.index("world")

    def test_build_widely_spaced_boxes_adds_spaces(self):
        boxes = [
            TextBox(text="A", x_min=0, y_min=0, x_max=10, y_max=10),
            TextBox(text="B", x_min=200, y_min=0, x_max=210, y_max=10),
        ]
        text = build_line_text(boxes, space_factor=0.15)
        assert " " in text
        assert text.startswith("A")
        assert text.endswith("B")

    def test_build_empty(self):
        assert build_line_text([]) == ""

    def test_build_single_box(self):
        boxes = [TextBox(text="solo", x_min=0, y_min=0, x_max=30, y_max=10)]
        assert build_line_text(boxes) == "solo"


class TestReconstructLayoutText:
    def test_reconstruct_multi_line(self):
        boxes = [
            TextBox(text="Line1A", x_min=0, y_min=0, x_max=40, y_max=10),
            TextBox(text="Line1B", x_min=50, y_min=2, x_max=90, y_max=12),
            TextBox(text="Line2A", x_min=0, y_min=50, x_max=40, y_max=60),
        ]
        text = reconstruct_layout_text(boxes, y_threshold=15.0, space_factor=0.15)
        lines = text.split("\n")
        assert len(lines) == 2
        assert "Line1A" in lines[0]
        assert "Line1B" in lines[0]
        assert "Line2A" in lines[1]

    def test_reconstruct_preserves_column_order(self):
        boxes = [
            TextBox(text="Col1", x_min=0, y_min=0, x_max=30, y_max=10),
            TextBox(text="Col3", x_min=200, y_min=1, x_max=230, y_max=11),
            TextBox(text="Col2", x_min=100, y_min=2, x_max=130, y_max=12),
        ]
        text = reconstruct_layout_text(boxes, y_threshold=15.0, space_factor=0.15)
        assert text.index("Col1") < text.index("Col2")
        assert text.index("Col2") < text.index("Col3")

    def test_reconstruct_empty(self):
        assert reconstruct_layout_text([]) == ""


class TestProcessOcrResultsToLayoutText:
    def test_full_pipeline(self):
        raw_results = [
            [
                [[0, 0], [40, 0], [40, 10], [0, 10]],
                ["MSKU1875698", 0.95],
            ],
            [
                [[100, 1], [160, 1], [160, 11], [100, 11]],
                ["26080.00", 0.93],
            ],
            [
                [[0, 50], [80, 50], [80, 60], [0, 60]],
                ["PALLET", 0.91],
            ],
        ]
        text, boxes = process_ocr_results_to_layout_text(raw_results, y_threshold=15.0, space_factor=0.15)
        assert len(boxes) == 3
        lines = text.split("\n")
        assert len(lines) == 2
        assert "MSKU1875698" in lines[0]
        assert "26080.00" in lines[0]
        assert "PALLET" in lines[1]