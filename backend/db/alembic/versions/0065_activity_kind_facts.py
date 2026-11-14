"""Listing kind and checked facts on activities, checked date on organizations.

Revision ID: 0065_activity_kind_facts
Revises: 0064_org_parent_verified

``activities.kind`` is text with a check, not an enum, so a later kind
is one constraint change. The backfill reads the ``0040`` category ids:
venues become ``place``, nursery and crèche become ``preschool``, and
of the rest a name that reads like a camp or workshop becomes ``camp``.
It runs with ``app.catalog_backfill`` on, so it writes no catalog
version: a snapshot without ``kind`` already reads as the default.

``organizations.parent_verified_at`` stays null for organizations that
are already verified. The real date is not known.

Seed assessment: no seed change. ``kind`` and ``facts`` are NOT NULL
with server defaults ``class`` and ``{}``, which both checks accept.
``parent_verified_at`` is nullable, and the seed organizations are not
verified, so its check holds. Seed inserts omit all three columns. No
new table or foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0065_activity_kind_facts"
down_revision: Union[str, None] = "0064_org_parent_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = ("class", "camp", "place", "preschool", "eat")
_CATEGORY_ID = "c1111111-1111-1111-1111-11111111{suffix}"
_PLACE_SUFFIXES = (
    "1205",
    "1206",
    "1241",
    "1242",
    "1243",
    "1251",
    "1252",
    "1253",
    "1261",
    "1262",
    "1263",
)
_PRESCHOOL_SUFFIXES = ("1211", "1212")
_CAMP_NAME_PATTERN = r"\m(camps?|workshops?|holiday course)\M"
_CAMP_NAME_WORDS = ("夏令營", "冬令營", "日營", "工作坊", "暑期班")


def upgrade() -> None:
    """Add the three columns, then backfill kind."""
    op.add_column(
        "activities",
        sa.Column(
            "kind",
            sa.Text(),
            nullable=False,
            server_default="class",
            comment="Listing kind: decides what the card and page show",
        ),
    )
    op.create_check_constraint(
        "activities_kind_check",
        "activities",
        "kind IN (" + ", ".join(f"'{kind}'" for kind in _KINDS) + ")",
    )
    op.create_index("activities_kind_idx", "activities", ["kind"])
    op.add_column(
        "activities",
        sa.Column(
            "facts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Parent-checked facts: true seen, false seen missing",
        ),
    )
    op.create_check_constraint(
        "activities_facts_object_check",
        "activities",
        "jsonb_typeof(facts) = 'object'",
    )
    op.add_column(
        "organizations",
        sa.Column(
            "parent_verified_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Admin-only: when a parent last checked this organization",
        ),
    )
    op.create_check_constraint(
        "organizations_parent_verified_at_check",
        "organizations",
        "parent_verified_at IS NULL OR parent_verified",
    )
    backfill_kind(op.get_bind())


def downgrade() -> None:
    """Drop the three columns. Kinds, facts, and checked dates are lost."""
    op.drop_constraint(
        "organizations_parent_verified_at_check",
        "organizations",
        type_="check",
    )
    op.drop_column("organizations", "parent_verified_at")
    op.drop_constraint("activities_facts_object_check", "activities", type_="check")
    op.drop_column("activities", "facts")
    op.drop_index("activities_kind_idx", table_name="activities")
    op.drop_constraint("activities_kind_check", "activities", type_="check")
    op.drop_column("activities", "kind")


def backfill_kind(bind: Any) -> None:
    """Set kind from the 0040 leaves, then from the name. Others stay class."""
    bind.execute(sa.text("SELECT set_config('app.catalog_backfill', 'on', true)"))
    _set_kind_for_categories(bind, "place", _PLACE_SUFFIXES)
    _set_kind_for_categories(bind, "preschool", _PRESCHOOL_SUFFIXES)
    # One bound name per entry of _CAMP_NAME_WORDS. The SQL stays a literal
    # so a scanner does not read it as assembled from outside the file.
    if len(_CAMP_NAME_WORDS) != 5:
        raise RuntimeError("The camp backfill names five words")
    bind.execute(
        sa.text(
            "UPDATE activities SET kind = 'camp' "
            "WHERE kind = 'class' AND (name ~* :pattern "
            "OR strpos(name, :word0) > 0 OR strpos(name, :word1) > 0 "
            "OR strpos(name, :word2) > 0 OR strpos(name, :word3) > 0 "
            "OR strpos(name, :word4) > 0)"
        ),
        {
            "pattern": _CAMP_NAME_PATTERN,
            "word0": _CAMP_NAME_WORDS[0],
            "word1": _CAMP_NAME_WORDS[1],
            "word2": _CAMP_NAME_WORDS[2],
            "word3": _CAMP_NAME_WORDS[3],
            "word4": _CAMP_NAME_WORDS[4],
        },
    )
    bind.execute(sa.text("SELECT set_config('app.catalog_backfill', 'off', true)"))


def _set_kind_for_categories(bind: Any, kind: str, suffixes: Sequence[str]) -> None:
    bind.execute(
        sa.text(
            "UPDATE activities SET kind = :kind "
            "WHERE kind = 'class' AND category_id = ANY(CAST(:ids AS uuid[]))"
        ),
        {
            "kind": kind,
            "ids": [_CATEGORY_ID.format(suffix=suffix) for suffix in suffixes],
        },
    )
