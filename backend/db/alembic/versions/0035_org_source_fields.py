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
    """Split import attribution out of a description.

    Returns cleaned description, source URL, source note, and catalog
    pairs from the last ``Source:`` line. A line is removed only when
    it is exactly ``Source: ...``. The first `` — `` segment is the URL
    when it starts with http(s); otherwise the whole remainder is the
    note, so a note that itself contains `` — `` stays intact.
    """
    if description is None:
        return None, None, None, {}
    kept: list[str] = []
    source_lines: list[str] = []
    for line in description.split("\n"):
        match = _SOURCE_LINE.match(line.strip())
        if match:
            source_lines.append(match.group(1).strip())
        else:
            kept.append(line)
    if not source_lines:
        return description, None, None, {}
    url, raw_note = _split_source_line(source_lines[-1])
    pairs = {
        match.group(1): match.group(2).strip() for match in _PAIR.finditer(raw_note)
    }
    note = _residual_note(raw_note)
    cleaned = "\n".join(kept).strip()
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
            "SELECT a.id AS id, a.org_id AS org_id, a.description AS description, "
            "o.source AS source, o.source_id AS source_id, "
            "o.description_source AS description_source "
            "FROM activities a "
            "JOIN organizations o ON o.id = a.org_id "
            "WHERE a.description LIKE '%Source:%'"
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
    description, url, note, pairs = peel_appended_source(row["description"])
    if description == row["description"] and not url and not note and not pairs:
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
    source = row["source"] or _allowed(pairs.get("source"), _ORG_SOURCES)
    source_id = row["source_id"] or _clip(pairs.get("sourceId"))
    description_source = row["description_source"] or _allowed(
        pairs.get("descriptionSource"),
        _DESCRIPTION_SOURCES,
    )
    if (
        source == row["source"]
        and source_id == row["source_id"]
        and description_source == row["description_source"]
    ):
        return
    bind.execute(
        sa.text(
            "UPDATE organizations SET source = :source, source_id = :source_id, "
            "description_source = :description_source WHERE id = :id"
        ),
        {
            "id": row["org_id"],
            "source": source,
            "source_id": source_id,
            "description_source": description_source,
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
    kept: list[str] = []
    for segment in note.split(";"):
        piece = segment.strip()
        if not piece:
            continue
        match = _PAIR.fullmatch(piece)
        if match and match.group(1) in _CATALOG_KEYS:
            continue
        kept.append(piece)
    return "; ".join(kept)


def _allowed(value: str | None, choices: frozenset[str]) -> str | None:
    if value in choices:
        return value
    return None


def _clip(value: str | None) -> str | None:
    if not value:
        return None
    return value[:_MAX_SOURCE_ID]
