from app.llm.evaluation import aggregate_evaluations, evaluate_expected_fields


def test_field_evaluation_separates_missing_and_mismatched_values():
    expected = {
        "reference": "SI-1",
        "cargo": {"weight": 1200.0, "description": "LAMINATE FLOOR"},
    }
    actual = {
        "reference": "si-1",
        "cargo": {"weight": 1250.0, "description": None},
    }

    result = evaluate_expected_fields(expected, actual)

    assert result["accuracy"] == 33.33
    assert result["correct_fields"] == ["reference"]
    assert result["missing_fields"] == ["cargo.description"]
    assert result["mismatched_fields"][0]["field_path"] == "cargo.weight"


def test_aggregate_evaluation_uses_field_weighted_accuracy():
    report = aggregate_evaluations([
        {
            "total_fields": 2,
            "correct_fields": ["a"],
            "missing_fields": ["b"],
            "mismatched_fields": [],
        },
        {
            "total_fields": 1,
            "correct_fields": ["a"],
            "missing_fields": [],
            "mismatched_fields": [],
        },
    ])

    assert report["documents"] == 2
    assert report["accuracy"] == 66.67
    assert report["missing_fields"] == 1
