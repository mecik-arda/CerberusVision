from io import BytesIO

import torch
from PIL import Image

from app.ocr import vlm_region
from app.ocr.line_grouper import TextBox


class FakeFlorenceModel:
    def __init__(self):
        self.model_parameter = torch.nn.Parameter(
            torch.ones(1, dtype=torch.float16)
        )
        self.received_inputs = None

    def parameters(self):
        yield self.model_parameter

    def generate(self, **inputs):
        self.received_inputs = inputs
        return torch.tensor([[1, 2, 3]])


class FakeFlorenceProcessor:
    def __call__(self, **kwargs):
        return {
            "input_ids": torch.tensor([[1, 2]], dtype=torch.int64),
            "attention_mask": torch.tensor([[1, 1]], dtype=torch.int64),
            "pixel_values": torch.ones((1, 3, 8, 8), dtype=torch.float32),
        }

    def batch_decode(self, generated_ids, skip_special_tokens):
        return ["florence-output"]

    def post_process_generation(self, generated_text, task, image_size):
        return {
            task: {
                "labels": ["header"],
                "bboxes": [[0, 0, image_size[0], image_size[1]]],
            }
        }


def test_detect_regions_moves_processor_tensors_to_model_runtime(monkeypatch):
    model = FakeFlorenceModel()
    processor = FakeFlorenceProcessor()
    monkeypatch.setattr(
        vlm_region,
        "get_florence_pipeline",
        lambda: (model, processor),
    )
    image_buffer = BytesIO()
    Image.new("RGB", (16, 12), color="white").save(
        image_buffer,
        format="PNG",
    )

    result = vlm_region.detect_regions_with_florence(
        image_buffer.getvalue()
    )

    assert model.received_inputs["input_ids"].dtype == torch.int64
    assert model.received_inputs["attention_mask"].dtype == torch.int64
    assert model.received_inputs["pixel_values"].dtype == torch.float16
    assert result["image_width"] == 16
    assert result["image_height"] == 12
    assert result["text_regions"][0]["label"] == "header"


def test_table_regions_do_not_trigger_false_box_loss():
    table_box = TextBox("table value", 10, 10, 30, 30)
    regular_box = TextBox("regular value", 10, 70, 30, 80)
    florence_result = {
        "tables": [{"label": "table", "bbox": [0, 0, 50, 50]}],
        "text_regions": [],
    }

    upper_boxes, middle_boxes, lower_boxes = (
        vlm_region.map_florence_regions_to_paddle_boxes(
            florence_result,
            [table_box, regular_box],
            100,
        )
    )

    segmented_boxes = upper_boxes + middle_boxes + lower_boxes
    assert table_box not in segmented_boxes
    assert regular_box in segmented_boxes
