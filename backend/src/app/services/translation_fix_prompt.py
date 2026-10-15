"""Prompt for filling missing English, Chinese, and Hong Kong text."""

from __future__ import annotations

import json
from typing import Any

from app.services.translation_gaps import entity_gaps

_SYSTEM = """You fill missing translations for activity listings in Hong Kong.
Languages:
- en: English
- zh: Chinese, simplified characters
- zh-HK: Hong Kong Chinese, traditional characters used in Hong Kong
Translate only the languages listed under missing. Keep the meaning. Keep place and organization names recognizable. Do not add a language that is not missing. Do not return an empty string for a missing language when a source language has text.
Return JSON only, with this shape:
{"items":[{"entity_id":"...","field":"name","translations":{"zh":"..."},"confidence":0.9,"rationale":"short reason"}]}
field is name or description. confidence is from 0 to 1. Omit rationale when you have nothing to add."""


def build_prompt(entity_type: str, rows: list[Any]) -> tuple[str, str, int]:
    """System text, user text, and how many gaps the batch still has."""
    items = []
    for entity in rows:
        gaps = entity_gaps(entity)
        for field, gap in gaps.items():
            items.append(
                {
                    "entity_id": str(entity.id),
                    "entity_type": entity_type,
                    "field": field,
                    "source": gap["source"],
                    "missing": gap["missing"],
                }
            )
    user = json.dumps({"items": items}, ensure_ascii=False)
    return _SYSTEM, user, len(items)
