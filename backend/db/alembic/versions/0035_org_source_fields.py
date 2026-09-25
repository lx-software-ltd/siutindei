"""Move appended Source lines onto source_url and source_note.

Revision ID: 0035_org_source_fields
Revises: 0034_category_suggestions

Seed assessment: new nullable text columns with no default and no
CHECK. Existing seed rows stay valid. seed_data.sql also sets sample
source fields on Harbor Arts Studio and Creative Painting so the admin
editor has a populated example. Downgrade drops the columns and does
not put Source lines back into descriptions.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0035_org_source_fields"
down_revision: Union[str, None] = "0034_category_suggestions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOURCE_LINE = re.compile(r"^Source: (.*)$")
_URL = re.compile(r"^https?://", re.IGNORECASE)
_PAIR = re.compile(r"([A-Za-z]+)\s*=\s*([^;]+)")
_DASH = " — "
_CATALOG_KEYS = frozenset({"source", "sourceId", "descriptionSource"})
_ORG_SOURCES = frozenset({"lcsd", "edb", "swd", "places", "competitor"})
_DESCRIPTION_SOURCES = frozenset({"template", "official", "places", "enrich"})
_MAX_SOURCE_ID = 80


def upgrade() -> None:
    """Add source columns and lift Source lines out of descriptions."""
    op.add_column(
        "organizations",
        sa.Column("source_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("source_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("source_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("source_note", sa.Text(), nullable=True),
    )
    backfill_appended_sources(op.get_bind())


def downgrade() -> None:
    """Drop source_url and source_note. Descriptions stay cleaned."""
    op.drop_column("activities", "source_note")
    op.drop_column("activities", "source_url")
    op.drop_column("organizations", "source_note")
    op.drop_column("organizations", "source_url")


def peel_appended_source(
    description: str | None,
) -> tuple[str | None, str | None, str | None, dict[str, str]]:
    """Split trailing import attribution out of a description.

    Returns cleaned description, source URL, source note, and catalog
    pairs from the last trailing ``Source:`` line. Only a suffix of
    exact ``Source: ...`` lines is removed (blank lines after that
    suffix are ignored). A ``Source:`` line with more description
    after it stays in place. The first `` — `` segment is the URL
    when it starts with http(s); otherwise the whole remainder is the
    note, so a note that itself contains `` — `` stays intact.
    """
    if description is None:
        return None, None, None, {}
    lines = description.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    source_lines: list[str] = []
    while lines:
        match = _SOURCE_LINE.match(lines[-1].strip())
        if match is None:
            break
        source_lines.append(match.group(1).strip())
        lines.pop()
    if not source_lines:
        return description, None, None, {}
    source_lines.reverse()
    url, raw_note = _split_source_line(source_lines[-1])
    pairs = {
        match.group(1): match.group(2).strip() for match in _PAIR.finditer(raw_note)
    }
    note = _residual_note(raw_note)
    cleaned = "\n".join(lines).strip()
    return cleaned or None, url, note or None, pairs


def backfill_appended_sources(bind: sa.Connection) -> None:
    """Copy Source lines into columns and clear them from descriptions."""
    org_rows = bind.execute(
        sa.text(
            "SELECT id, description, source, source_id, description_source "
            "FROM organizations WHERE description LIKE '%Source:%'"
        )
    ).mappings()
    for row in org_rows:
        _update_organization_source(bind, row)

    activity_rows = bind.execute(
        sa.text(
            "SELECT id, description FROM activities "
            "WHERE description LIKE '%Source:%'"
        )
    ).mappings()
    for row in activity_rows:
        _update_activity_source(bind, row)


def _update_organization_source(
    bind: sa.Connection,
    row: Mapping[str, Any],
) -> None:
    description, url, note, pairs = peel_appended_source(row["description"])
    if description == row["description"] and not url and not note and not pairs:
        return
    bind.execute(
        sa.text(
            "UPDATE organizations SET description = :description, "
            "source_url = :source_url, source_note = :source_note, "
            "source = :source, source_id = :source_id, "
            "description_source = :description_source WHERE id = :id"
        ),
        {
            "id": row["id"],
            "description": description,
            "source_url": url,
            "source_note": note,
            "source": row["source"] or _allowed(pairs.get("source"), _ORG_SOURCES),
            "source_id": row["source_id"] or _clip(pairs.get("sourceId")),
            "description_source": row["description_source"]
            or _allowed(pairs.get("descriptionSource"), _DESCRIPTION_SOURCES),
        },
    )


def _update_activity_source(
    bind: sa.Connection,
    row: Mapping[str, Any],
) -> None:
    description, url, note, _pairs = peel_appended_source(row["description"])
    if description == row["description"] and not url and not note:
        return
    bind.execute(
        sa.text(
            "UPDATE activities SET description = :description, "
            "source_url = :source_url, source_note = :source_note "
            "WHERE id = :id"
        ),
        {
            "id": row["id"],
            "description": description,
            "source_url": url,
            "source_note": note,
        },
    )


def _split_source_line(payload: str) -> tuple[str | None, str]:
    if _DASH in payload:
        head, tail = payload.split(_DASH, 1)
        head = head.strip()
        if _URL.match(head):
            return head, tail.strip()
    if _URL.match(payload.strip()):
        return payload.strip(), ""
    return None, payload.strip()


def _residual_note(note: str) -> str:
    text = note.strip()
    kept: list[str] = []
    removed_catalog = False
    for segment in text.split(";"):
        piece = segment.strip()
        if not piece:
            continue
        match = _PAIR.fullmatch(piece)
        if match and match.group(1) in _CATALOG_KEYS:
            removed_catalog = True
            continue
        kept.append(piece)
    if not removed_catalog:
        return text
    return "; ".join(kept)


def _allowed(value: str | None, choices: frozenset[str]) -> str | None:
    if value in choices:
        return value
    return None


def _clip(value: str | None) -> str | None:
    if not value:
        return None
    return value[:_MAX_SOURCE_ID]
