import json

from app.llm import translation
from tests.test_validator import create_complete_si


class TranslationPipeline:
    def generate(self, prompt, config):
        return json.dumps({
            "values": [
                {
                    "path": "cargo_items[0].description_of_goods",
                    "value": "LAMİNE ZEMİN",
                },
                {
                    "path": "equipment_list[0].equipment_reference",
                    "value": "CHANGED",
                },
            ]
        }, ensure_ascii=False)


def test_translation_changes_only_descriptive_whitelisted_fields(monkeypatch):
    instruction = create_complete_si()
    original_reference = instruction.equipment_list[0].equipment_reference
    monkeypatch.setattr(translation, "get_llm_pipeline", lambda: TranslationPipeline())
    monkeypatch.setattr(
        translation,
        "_build_generation_config_for_schema",
        lambda schema: object(),
    )

    translated, raw_output = translation.translate_instruction_content(
        instruction,
        "tr",
    )

    assert translated.cargo_items[0].description_of_goods == "LAMİNE ZEMİN"
    assert translated.equipment_list[0].equipment_reference == original_reference
    assert instruction.cargo_items[0].description_of_goods != "LAMİNE ZEMİN"
    assert "description_of_goods" in raw_output
