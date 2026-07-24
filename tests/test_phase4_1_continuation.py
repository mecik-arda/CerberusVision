import json

import pytest

from scripts import prepare_phase4_1_continuation


def _record(input_text, output):
    return {
        "instructions": "Extract",
        "input": input_text,
        "output": json.dumps(output),
    }


def test_hard_example_selection_is_deterministic_and_prefers_targeted_cases():
    records = [
        _record(
            "BOOKING BKG-1",
            {"carrier_booking_reference": "BKG-1"},
        ),
        _record(
            "YUKLEME LIMANI IZMIR KONTEYNER MSKU1234567",
            {
                "equipment_list": [
                    {"equipment_reference": "MSKU1234567"},
                    {"equipment_reference": "TGHU7654321"},
                ],
                "cargo_items": [
                    {"description_of_goods": "A"},
                    {"description_of_goods": "B"},
                ],
            },
        ),
        _record(
            "PORT OF LOADING HAMBURG",
            {
                "transport_plans": [
                    {
                        "port_of_loading": {
                            "location_name": "HAMBURG"
                        }
                    }
                ]
            },
        ),
    ]

    first = prepare_phase4_1_continuation.select_hard_examples(
        records,
        1,
    )
    second = prepare_phase4_1_continuation.select_hard_examples(
        list(reversed(records)),
        1,
    )

    assert first == second
    assert "MSKU1234567" in first[0]["input"]


def test_parent_adapter_hash_validation_fails_closed(
    tmp_path,
):
    (tmp_path / "adapter_model.safetensors").write_bytes(b"wrong")
    (tmp_path / "adapter_config.json").write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="adapter hash mismatch"):
        prepare_phase4_1_continuation._validate_parent_adapter(
            tmp_path
        )


def test_difficulty_features_reward_absent_transport_without_changing_labels():
    record = _record(
        "TALIMAT NO SI-1 NAVLUN BILGISI YOK",
        {
            "shipping_instruction_reference": "SI-1",
            "transport_plans": None,
            "transport_document_type": None,
            "freight_payment_term_code": None,
        },
    )

    features = prepare_phase4_1_continuation.difficulty_features(record)

    assert "transport_negative" in features
    assert "turkish" in features
    assert json.loads(record["output"])["transport_plans"] is None
