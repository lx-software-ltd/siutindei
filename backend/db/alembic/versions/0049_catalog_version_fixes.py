"""Make catalog history immutable and backfill it in batches.

Revision ID: 0049_catalog_version_fixes
Revises: 0048_catalog_versions

Seed assessment: no seed column changes. ``catalog_versions`` stays
unseeded. The batch backfill may insert ``organization_merges`` rows
with ``kind = 'delete'`` when ``audit_log`` still has a removed
organization and no merge row. A fresh database has none. Existing
seed SQL is unchanged.

A failed run of this revision can commit the helper functions before
the version stamp. Those copies return ``integer``. ``CREATE OR
REPLACE`` cannot change a return type, so ``upgrade`` drops them
before loading the SQL again.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_catalog_version_fixes"
down_revision: Union[str, None] = "0048_catalog_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DB = Path(__file__).resolve().parents[2]
_TABLES = (
    "organizations",
    "locations",
    "activities",
    "activity_pricing",
    "activity_schedule",
)
_BATCH_CAP = 10000
_BACKFILL_FUNCTIONS = (
    "catalog_backfill_deleted_batch(text)",
    "catalog_backfill_deleted(text, text[])",
    "catalog_backfill_deleted_candidates(text, integer)",
    "catalog_backfill_live_batch(text)",
    "catalog_backfill_live(text, uuid[])",
    "catalog_backfill_live_candidates(text, integer)",
)


def upgrade() -> None:
    """Replace version triggers, then fill any history still missing."""
    op.execute((_DB / "catalog_version_triggers.sql").read_text(encoding="utf-8"))
    _grant_catalog_versions()
    # Drop first. A failed attempt left integer-returning copies, and
    # CREATE OR REPLACE cannot change a return type.
    _drop_backfill_functions()
    op.execute((_DB / "catalog_version_backfill.sql").read_text(encoding="utf-8"))
    _backfill_in_batches()
    _drop_backfill_functions()


def _drop_backfill_functions() -> None:
    """Remove the one-shot helpers. Batches go before the functions they call."""
    for name in _BACKFILL_FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {name}")


def _grant_catalog_versions() -> None:
    for role in ("siutindei_app", "siutindei_admin"):
        op.execute(f"REVOKE UPDATE ON catalog_versions FROM {role}")
        op.execute(f"GRANT SELECT, INSERT, DELETE ON catalog_versions TO {role}")
        op.execute(f"GRANT UPDATE (reason, related_id) ON catalog_versions TO {role}")
        op.execute(
            f"GRANT EXECUTE ON FUNCTION catalog_forget_entity(text, uuid) TO {role}"
        )


def downgrade() -> None:
    """History rows belong to 0048. Dropping that revision removes them."""


def _backfill_in_batches() -> None:
    """Commit every 200 rows so one migration does not lock the catalog."""
    with op.get_context().autocommit_block():
        for table in _TABLES:
            _drain("catalog_backfill_live_batch", table)
            _drain("catalog_backfill_deleted_batch", table)


def _drain_ids(
    function_name: str, table: str, fetch_ids, cap: int = _BATCH_CAP
) -> None:
    """Stop when a batch returns the same first id, or the cap is hit.

    ``fetch_ids`` is one batch: the ids it selected and then wrote. An
    empty result means the table is finished. The batch function does
    both steps in one statement, so the drain does not query twice.
    """
    previous: str | None = None
    last_ids: list[str] = []
    for _ in range(cap):
        ids = [str(item) for item in fetch_ids()]
        if not ids:
            return
        marker = ids[0]
        if previous is not None and marker == previous:
            shown = ", ".join(ids[:5])
            raise RuntimeError(
                f"{function_name} made no progress for {table}; sample ids: {shown}"
            )
        previous = marker
        last_ids = ids
    shown = ", ".join(last_ids[:5])
    raise RuntimeError(
        f"{function_name} did not finish for {table}; sample ids: {shown}"
    )


def _drain(function_name: str, table: str) -> None:
    """Fill one table. The batch returns the ids it just handled."""
    statement = sa.select(getattr(sa.func, function_name)(table))

    def fetch_ids() -> list[str]:
        found = op.get_bind().execute(statement).scalar()
        return [] if not found else list(found)

    _drain_ids(function_name, table, fetch_ids)
