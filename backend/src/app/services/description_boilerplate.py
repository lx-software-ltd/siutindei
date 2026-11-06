"""Import filler that readiness and search still treat as a template.

EDB, LCSD, and Places imports share one English closing and one
Cantonese closing. A unique description can keep a stale ``template``
tag. That tag no longer warns, and search shows the text. A blank
description on a ``template`` organization still hides activity copy
in search, because there is no replacement text yet.
"""

from __future__ import annotations

from collections.abc import Mapping

ENGLISH_IMPORT_BOILERPLATE = "for children and families"
CANTONESE_IMPORT_BOILERPLATE = "適合小朋友同家庭"
ENGLISH_IMPORT_STEMS = ("is a ", "is an ")


def description_is_import_boilerplate(description: str | None) -> bool:
    """True when this text is an import filler sentence."""
    text = description or ""
    if CANTONESE_IMPORT_BOILERPLATE in text:
        return True
    if ENGLISH_IMPORT_BOILERPLATE not in text:
        return False
    return any(stem in text for stem in ENGLISH_IMPORT_STEMS)


def leftover_chinese_boilerplate(translations: Mapping[str, str] | None) -> bool:
    """True when a Chinese translation is still the import filler."""
    stored = translations or {}
    return any(
        description_is_import_boilerplate(stored.get(language))
        for language in ("zh", "zh-HK")
    )


def source_attribution_message(
    source: str | None,
    description: str | None,
    translations: Mapping[str, str] | None,
) -> str | None:
    """Readiness copy when the description is still import filler or a source line."""
    if source == "template" and description_is_import_boilerplate(description):
        return "Description is a template"
    if leftover_chinese_boilerplate(translations):
        return "Chinese description is a template"
    if "Source:" in (description or ""):
        return "Description still contains a source line"
    return None


def omit_import_boilerplate(translations: dict[str, str]) -> dict[str, str]:
    """Drop filler sentences from a language map. Real copy stays."""
    return {
        key: value
        for key, value in translations.items()
        if not description_is_import_boilerplate(value)
    }


def hides_template_description(source: str | None, description: str | None) -> bool:
    """True when search should omit this organization's descriptions."""
    if source != "template":
        return False
    text = (description or "").strip()
    if not text:
        return True
    return description_is_import_boilerplate(text)
