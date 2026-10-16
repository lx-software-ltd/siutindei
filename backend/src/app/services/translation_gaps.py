"""Which name and description languages still need a translation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.utils.translations import build_translation_map

LANGUAGES = ("en", "zh", "zh-HK")
FIELDS = ("name", "description")
LANGUAGE_LABELS = {
    "en": "English",
    "zh": "Chinese",
    "zh-HK": "Hong Kong",
}


def text_value(value: Any) -> str:
    """Return stripped text. Non-strings become empty."""
    if isinstance(value, str):
        return value.strip()
    return ""


def language_map(base: Any, translations: Any) -> dict[str, str]:
    """English from the base column, Chinese and Hong Kong from the map."""
    raw = translations if isinstance(translations, dict) else None
    english = text_value(base)
    built = build_translation_map(english or None, raw)
    found: dict[str, str] = {}
    for key in LANGUAGES:
        value = text_value(built.get(key))
        if value:
            found[key] = value
    return found


def field_gap(base: Any, translations: Any) -> dict[str, Any] | None:
    """A gap when one required language exists and another is missing."""
    present = language_map(base, translations)
    missing = [lang for lang in LANGUAGES if lang not in present]
    if not present or not missing:
        return None
    return {"source": present, "missing": missing}


def entity_gaps(entity: Any) -> dict[str, dict[str, Any]]:
    """Name and description gaps for an organization or activity."""
    gaps: dict[str, dict[str, Any]] = {}
    name = field_gap(
        getattr(entity, "name", None), getattr(entity, "name_translations", None)
    )
    if name is not None:
        gaps["name"] = name
    description = field_gap(
        getattr(entity, "description", None),
        getattr(entity, "description_translations", None),
    )
    if description is not None:
        gaps["description"] = description
    return gaps


def source_hash(
    *,
    entity_type: str,
    entity_id: Any,
    field: str,
    source: dict[str, str],
) -> str:
    """Fingerprint the text a translation was made from."""
    payload = {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "field": field,
        "source": {key: source[key] for key in sorted(source)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def language_list(codes: list[str] | tuple[str, ...]) -> str:
    """Sentence-case language names in required-language order."""
    return ", ".join(LANGUAGE_LABELS[code] for code in LANGUAGES if code in set(codes))


_REVIEW_WARNINGS = {
    ("name", "en"): ("missing_en_name", "English name is missing"),
    ("name", "zh"): ("missing_zh_name", "Chinese name is missing"),
    ("name", "zh-HK"): ("missing_zh_hk_name", "Hong Kong name is missing"),
    ("description", "en"): (
        "missing_en_description",
        "English description is missing",
    ),
    ("description", "zh"): (
        "missing_zh_description",
        "Chinese description is missing",
    ),
    ("description", "zh-HK"): (
        "missing_zh_hk_description",
        "Hong Kong description is missing",
    ),
}


def note_review_gaps(organization, org_id: str, add, note) -> None:
    """Warn when a review snapshot is missing a required language."""
    for field in ("name", "description"):
        gap = field_gap(
            getattr(organization, field),
            getattr(organization, f"{field}_translations"),
        )
        missing = set(gap["missing"]) if gap else set()
        for language in LANGUAGES:
            note()
            if language not in missing:
                continue
            code, message = _REVIEW_WARNINGS[(field, language)]
            add(code, "warning", "organization", org_id, message)


def text_label(values: dict[str, Any] | None, *, limit: int = 160) -> str:
    """One line of language-tagged text for a table cell."""
    raw = values if isinstance(values, dict) else {}
    parts = []
    for code in LANGUAGES:
        value = text_value(raw.get(code))
        if value:
            parts.append(f"{LANGUAGE_LABELS[code]}: {value}")
    text = " · ".join(parts)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
