"""Helpers for translation maps."""

from __future__ import annotations

from collections.abc import Mapping


def build_translation_map(
    base_value: str | None,
    translations: Mapping[str, str] | None,
) -> dict[str, str]:
    """Build a language map with English fallback.

    Args:
        base_value: The English value stored on the base column.
        translations: The non-English translation map stored in JSONB.

    Returns:
        Language map that always includes English when base_value is present.
    """
    result: dict[str, str] = {}
    if base_value:
        result["en"] = base_value
    if translations:
        for key, value in translations.items():
            if not value:
                continue
            if key == "en":
                continue
            result[key] = value
    return result
