"""Listing kinds and the parent-checked facts each kind allows.

A fact is ``true`` when a parent saw it and ``false`` when a parent saw
that it is missing. An absent key means nobody checked.
"""

from __future__ import annotations

import re
from typing import Any

from app.exceptions import ValidationError

KINDS = ("class", "camp", "place", "preschool", "eat")
DEFAULT_KIND = "class"

_CLASS_FACTS = ("drop_in", "parent_stays", "sen_friendly")
FACT_KEYS: dict[str, tuple[str, ...]] = {
    "class": _CLASS_FACTS,
    "camp": (*_CLASS_FACTS, "lunch_included"),
    "place": (
        "toilets",
        "changing_table",
        "shade",
        "fenced",
        "stroller_access",
        "water_play",
        "lifeguard",
        "parking",
        "food_nearby",
    ),
    "preschool": (),
    "eat": (
        "high_chairs",
        "kids_menu",
        "changing_table",
        "stroller_access",
        "room_to_run",
        "outdoor_seating",
    ),
}

# Keep in step with the backfill in 0065_activity_kind_facts.py.
_CAMP_NAME_PATTERN = re.compile(
    r"\b(camps?|workshops?|holiday course)\b",
    re.IGNORECASE,
)
_CAMP_NAME_WORDS = ("夏令營", "冬令營", "日營", "工作坊", "暑期班")


def parse_kind(value: Any) -> str:
    """Return a known kind or raise."""
    if isinstance(value, str) and value in KINDS:
        return value
    raise ValidationError(
        "kind must be one of: " + ", ".join(KINDS),
        field="kind",
    )


def validate_facts(kind: str, facts: Any) -> dict[str, bool]:
    """Return facts sorted by key. Unknown keys and non-booleans raise."""
    if facts is None:
        return {}
    if not isinstance(facts, dict):
        raise ValidationError("facts must be an object", field="facts")
    allowed = FACT_KEYS[kind]
    for key, value in facts.items():
        if key not in allowed:
            raise ValidationError(
                f"facts.{key} is not a fact for kind {kind}",
                field="facts",
            )
        if not isinstance(value, bool):
            raise ValidationError(
                f"facts.{key} must be true or false",
                field="facts",
            )
    return dict(sorted(facts.items()))


def facts_for_kind(kind: str, facts: dict[str, bool] | None) -> dict[str, bool]:
    """Drop the fact keys a kind does not allow."""
    allowed = FACT_KEYS[kind]
    return {
        key: value for key, value in sorted((facts or {}).items()) if key in allowed
    }


def guess_kind(name: str | None) -> str:
    """``camp`` when the name reads like a camp or workshop, else ``class``."""
    text = name or ""
    if _CAMP_NAME_PATTERN.search(text):
        return "camp"
    if any(word in text for word in _CAMP_NAME_WORDS):
        return "camp"
    return DEFAULT_KIND
