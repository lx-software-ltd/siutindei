"""Which name and description languages still need a translation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

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
    found: dict[str, str] = {}
    english = text_value(base)
    if english:
        found["en"] = english
    raw = translations if isinstance(translations, dict) else {}
    for key in ("zh", "zh-HK"):
        value = text_value(raw.get(key))
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
