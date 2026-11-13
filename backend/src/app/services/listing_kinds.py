"""Listing kinds and the parent-checked facts each kind allows.

A fact is ``true`` when a parent saw it and ``false`` when a parent saw
that it is missing. An absent key means nobody checked.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory
from app.db.models.category_suggestion import FIXED_ROOT_KINDS, WIZARD_GROUP_IDS
from app.exceptions import ValidationError
from app.services.org_review_decision import reject_if_only_hidden

KINDS = ("class", "camp", "place", "preschool", "eat")
DEFAULT_KIND = "class"
TOPIC_KINDS = ("class", "camp")

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


def kind_for_category(
    session: Session,
    category_id: UUID | str | None,
    current_kind: str,
) -> str:
    """The kind a category decides, else ``current_kind``.

    Under Places to play, Nurseries and kindergartens, or Eat with kids
    the root decides. Under a topic only ``class`` and ``camp`` fit, so
    any other kind becomes ``class``. Elsewhere the kind is kept.
    """
    root = _root_id(session, category_id)
    if root in FIXED_ROOT_KINDS:
        return FIXED_ROOT_KINDS[root]
    if root in WIZARD_GROUP_IDS and current_kind not in TOPIC_KINDS:
        return DEFAULT_KIND
    return current_kind


def assign_category(
    session: Session,
    activity: Activity,
    category_id: UUID | str,
) -> None:
    """Move an activity to a category. Kind follows; facts it loses go."""
    activity.category_id = category_id  # type: ignore[assignment]
    kind = kind_for_category(session, category_id, activity.kind or DEFAULT_KIND)
    if kind != activity.kind:
        activity.kind = kind
        activity.facts = facts_for_kind(kind, activity.facts)


def move_to_category(
    session: Session,
    activity: Activity,
    category_id: UUID | str,
) -> None:
    """Assign a category, then reject the organization if all it has is hidden."""
    assign_category(session, activity, category_id)
    reject_if_only_hidden(session, activity.org_id)


def _root_id(session: Session, category_id: UUID | str | None) -> UUID | None:
    seen: set[UUID] = set()
    current = _as_uuid(category_id)
    while current is not None and current not in seen:
        seen.add(current)
        row = session.get(ActivityCategory, current)
        if row is None:
            return None
        if row.parent_id is None:
            return current
        current = _as_uuid(row.parent_id)
    return None


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def guess_kind(name: str | None) -> str:
    """``camp`` when the name reads like a camp or workshop, else ``class``."""
    text = name or ""
    if _CAMP_NAME_PATTERN.search(text):
        return "camp"
    if any(word in text for word in _CAMP_NAME_WORDS):
        return "camp"
    return DEFAULT_KIND
