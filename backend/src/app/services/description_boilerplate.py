"""Import filler that readiness and search still treat as a template.

The English and Cantonese phrases are the catalog import sentence.
A unique description can keep a stale ``template`` tag. That tag no
longer warns, and search shows the text. A blank description on a
``template`` organization still hides activity copy in search, because
there is no replacement text yet.
"""

from __future__ import annotations

ENGLISH_IMPORT_BOILERPLATE = "is a class or early-years centre in"
CANTONESE_IMPORT_BOILERPLATE = "幼兒或興趣班，適合小朋友同家庭"


def description_is_import_boilerplate(description: str | None) -> bool:
    """True when this text is the import filler sentence."""
    text = description or ""
    return ENGLISH_IMPORT_BOILERPLATE in text or CANTONESE_IMPORT_BOILERPLATE in text


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
