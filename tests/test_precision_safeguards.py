from app.llm.inference import (
    _deduplicate_bl_document_references,
    _normalize_party_addresses,
)
from app.models import (
    Address,
    DocumentReference,
    Party,
    PartyRoleCode,
    ShippingInstruction,
)
from app.ocr.line_grouper import TextBox
from app.ocr.spatial_ocr import _filter_bottom_boilerplate_boxes
from scripts import prepare_training_data


def test_non_alphanumeric_address_values_are_removed():
    instruction = ShippingInstruction(
        parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                address=Address(
                    street=" --- ",
                    city="İstanbul",
                    postal_code="...",
                    country_code="TR",
                ),
            )
        ]
    )

    _normalize_party_addresses(instruction)

    address = instruction.parties[0].address
    assert address is not None
    assert address.street is None
    assert address.city == "İstanbul"
    assert address.postal_code is None
    assert address.country_code == "TR"


def test_bl_references_only_merge_after_conservative_normalization():
    instruction = ShippingInstruction(
        document_references=[
            DocumentReference(type_code="BL", reference_number="ABC-123"),
            DocumentReference(type_code=" bl ", reference_number="  abc-123  "),
            DocumentReference(type_code="BL", reference_number="ABC 123"),
            DocumentReference(type_code="CR", reference_number="ABC-123"),
        ]
    )

    _deduplicate_bl_document_references(instruction)

    retained = [
        (reference.type_code, reference.reference_number)
        for reference in instruction.document_references
    ]
    assert retained == [
        ("BL", "ABC-123"),
        ("BL", "ABC 123"),
        ("CR", "ABC-123"),
    ]


def test_exact_boilerplate_line_is_removed_only_from_bottom_region():
    boxes = [
        TextBox(
            text="BILL OF LADING TERMS AND CONDITIONS",
            x_min=0,
            y_min=100,
            x_max=400,
            y_max=120,
        ),
        TextBox(
            text="BILL OF LADING TERMS AND CONDITIONS",
            x_min=0,
            y_min=850,
            x_max=400,
            y_max=870,
        ),
        TextBox(
            text="BILL OF LADING TERMS AND CONDITIONS REF 42",
            x_min=0,
            y_min=900,
            x_max=500,
            y_max=920,
        ),
    ]

    filtered = _filter_bottom_boilerplate_boxes(boxes, page_height=1000)

    assert filtered == [boxes[0], boxes[2]]


def test_benchmark_fixtures_are_excluded_from_training_data(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(prepare_training_data, "_session_dirs", lambda: [])
    output_path = tmp_path / "training.jsonl"

    report = prepare_training_data.prepare_dataset(output_path)

    assert report["records"] == 0
    assert output_path.read_text(encoding="utf-8") == ""
