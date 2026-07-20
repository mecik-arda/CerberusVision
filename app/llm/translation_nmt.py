"""Lightweight NMT translation via Helsinki-NLP MarianMT models.

Replaces LLM-based translation for descriptive shipping fields
with a dedicated neural machine translation model (~300 MB).
Falls back to LLM when the NMT model is unavailable or fails.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.models import ShippingInstruction

logger = logging.getLogger(__name__)

_NMT_PIPELINE_CACHE: dict[str, tuple[object, object]] = {}

_MODEL_MAP = {
    ("tr", "en"): "Helsinki-NLP/opus-mt-tr-en",
    ("en", "tr"): "Helsinki-NLP/opus-mt-en-tr",
}


def _get_nmt_pipelines(
    source_lang: str, target_lang: str
) -> Optional[tuple[object, object]]:
    """Lazy-load cached MarianMT tokenizer + model for a language pair."""
    cache_key = f"{source_lang}-{target_lang}"
    if cache_key in _NMT_PIPELINE_CACHE:
        return _NMT_PIPELINE_CACHE[cache_key]

    model_name = _MODEL_MAP.get((source_lang, target_lang))
    if model_name is None:
        return None

    try:
        from transformers import MarianMTModel, MarianTokenizer

        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        _NMT_PIPELINE_CACHE[cache_key] = (tokenizer, model)
        logger.info("NMT model loaded: %s", model_name)
        return (tokenizer, model)
    except Exception as exc:
        logger.warning("Failed to load NMT model %s: %s", model_name, exc)
        return None


def translate_text(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Translate a single text string using MarianMT.

    Returns None if NMT is unavailable or fails.
    """
    if not text or not text.strip():
        return text

    pipelines = _get_nmt_pipelines(source_lang, target_lang)
    if pipelines is None:
        return None

    tokenizer, model = pipelines
    try:
        inputs = tokenizer([text], return_tensors="pt", padding=True, truncation=True)
        translated = model.generate(**inputs, max_new_tokens=512)
        result = tokenizer.batch_decode(translated, skip_special_tokens=True)
        return result[0] if result else None
    except Exception as exc:
        logger.warning("NMT translation failed: %s", exc)
        return None


def translate_descriptive_fields(
    instruction: ShippingInstruction,
    source_lang: str,
    target_lang: str,
) -> ShippingInstruction | None:
    """Translate descriptive (non-identifying) fields of a ShippingInstruction
    using NMT when available, leaving identifiers, codes, and numbers untouched.

    Returns None when NMT is unavailable for this language pair (caller should
    fall back to LLM). Returns the instruction unchanged when there are no
    translatable fields.

    Only translates the same target fields as the LLM-based translator:
    remarks, fta_declaration, verification_method, description_of_goods,
    and technical_name.
    """
    if not settings.nmt_enabled:
        return None

    if not is_nmt_available(source_lang, target_lang):
        return None

    translated = instruction.model_copy(deep=True)
    any_translated = False

    # Remarks
    if translated.remarks:
        result = translate_text(translated.remarks, source_lang, target_lang)
        if result is not None:
            translated.remarks = result.strip()
            any_translated = True

    # FTA declaration
    if (
        translated.customs_information
        and translated.customs_information.fta_declaration
    ):
        result = translate_text(
            translated.customs_information.fta_declaration,
            source_lang,
            target_lang,
        )
        if result is not None:
            translated.customs_information.fta_declaration = result.strip()

    # Equipment VGM verification methods
    for equipment in translated.equipment_list:
        if (
            equipment.verified_gross_mass
            and equipment.verified_gross_mass.verification_method
        ):
            result = translate_text(
                equipment.verified_gross_mass.verification_method,
                source_lang,
                target_lang,
            )
            if result is not None:
                equipment.verified_gross_mass.verification_method = result.strip()

    # Cargo descriptions and dangerous goods technical names
    for cargo_item in translated.cargo_items:
        if cargo_item.description_of_goods:
            result = translate_text(
                cargo_item.description_of_goods, source_lang, target_lang
            )
            if result is not None:
                cargo_item.description_of_goods = result.strip()

        for dg in cargo_item.dangerous_goods_list or []:
            if dg.technical_name:
                result = translate_text(
                    dg.technical_name, source_lang, target_lang
                )
                if result is not None:
                    dg.technical_name = result.strip()

    if not any_translated:
        return None
    return translated


def is_nmt_available(source_lang: str, target_lang: str) -> bool:
    """Check whether NMT is usable for a language pair."""
    return _get_nmt_pipelines(source_lang, target_lang) is not None
