from __future__ import annotations

import json
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.llm.inference import (
    _build_generation_config_for_schema,
    _extract_json,
    _parse_json_with_fallback,
    get_llm_pipeline,
)
from app.models import ShippingInstruction


class TranslatedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: Optional[str] = None


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[TranslatedValue] = Field(default_factory=list)


_language_names = {"tr": "Turkish", "en": "English"}


def _translation_targets(
    instruction: ShippingInstruction,
) -> Dict[str, tuple[object, str]]:
    targets: Dict[str, tuple[object, str]] = {}
    if instruction.remarks:
        targets["remarks"] = (instruction, "remarks")
    if instruction.customs_information and instruction.customs_information.fta_declaration:
        targets["customs_information.fta_declaration"] = (
            instruction.customs_information,
            "fta_declaration",
        )
    for equipment_index, equipment in enumerate(instruction.equipment_list):
        if equipment.verified_gross_mass and equipment.verified_gross_mass.verification_method:
            targets[
                f"equipment_list[{equipment_index}].verified_gross_mass.verification_method"
            ] = (equipment.verified_gross_mass, "verification_method")
    for cargo_index, cargo_item in enumerate(instruction.cargo_items):
        if cargo_item.description_of_goods:
            targets[f"cargo_items[{cargo_index}].description_of_goods"] = (
                cargo_item,
                "description_of_goods",
            )
        for goods_index, dangerous_goods in enumerate(
            cargo_item.dangerous_goods_list or []
        ):
            if dangerous_goods.technical_name:
                targets[
                    f"cargo_items[{cargo_index}].dangerous_goods_list[{goods_index}].technical_name"
                ] = (dangerous_goods, "technical_name")
    return targets


def translate_instruction_content(
    instruction: ShippingInstruction,
    output_language: str,
) -> tuple[ShippingInstruction, str]:
    translated_instruction = instruction.model_copy(deep=True)
    targets = _translation_targets(translated_instruction)
    if not targets:
        return translated_instruction, ""
    source_values = {
        path: getattr(target, attribute)
        for path, (target, attribute) in targets.items()
    }
    target_language = _language_names.get(output_language, "English")
    prompt = (
        "Translate every supplied descriptive value into "
        f"{target_language}. Preserve paths exactly. Do not change company names, personal names, addresses, "
        "locations, identifiers, reference numbers, codes, shipping marks, measurement units, or numeric values. "
        "Keep text already written in the target language unchanged. Return only JSON matching the schema.\n\n"
        f"Values:\n{json.dumps(source_values, ensure_ascii=False)}"
    )
    schema = TranslationResult.model_json_schema()
    raw_output = str(
        get_llm_pipeline().generate(
            prompt,
            _build_generation_config_for_schema(schema),
        )
    )
    try:
        parsed = json.loads(_extract_json(raw_output))
    except json.JSONDecodeError:
        parsed = _parse_json_with_fallback(_extract_json(raw_output))
    result = TranslationResult.model_validate(parsed)
    for translated_value in result.values:
        target = targets.get(translated_value.path)
        if target and translated_value.value:
            setattr(target[0], target[1], translated_value.value.strip())
    return translated_instruction, raw_output
