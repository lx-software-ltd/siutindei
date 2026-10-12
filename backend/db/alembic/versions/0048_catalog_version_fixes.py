"""Make catalog history immutable and backfill it in batches.

Revision ID: 0048_catalog_version_fixes
Revises: 0047_catalog_versions

Seed assessment: no seed column changes. ``catalog_versions`` stays
unseeded. The batch backfill may insert ``organization_merges`` rows
with ``kind = 'delete'`` when ``audit_log`` still has a removed
organization and no merge row. A fresh database has none. Existing
seed SQL is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048_catalog_version_fixes"
down_revision: Union[str, None] = "0047_catalog_versions"
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


def upgrade() -> None:
    """Replace version triggers, then fill any history still missing."""
    op.execute((_DB / "catalog_version_triggers.sql").read_text(encoding="utf-8"))
    _grant_catalog_versions()
    op.execute((_DB / "catalog_version_backfill.sql").read_text(encoding="utf-8"))
    _backfill_in_batches()
    for name in (
        "catalog_backfill_deleted_batch(text)",
        "catalog_backfill_deleted(text, text[])",
        "catalog_backfill_live_batch(text)",
        "catalog_backfill_live(text, uuid[])",
    ):
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
    """History rows belong to 0047. Dropping that revision removes them."""


def _backfill_in_batches() -> None:
    """Commit every 200 rows so one migration does not lock the catalog."""
    with op.get_context().autocommit_block():
        for table in _TABLES:
            _drain("catalog_backfill_live_batch", table)
            _drain("catalog_backfill_deleted_batch", table)


def _drain(function: str, table: str) -> None:
    for _ in range(_BATCH_CAP):
        count = (
            op.get_bind()
            .execute(sa.text(f"SELECT {function}(:table)"), {"table": table})
            .scalar()
        )
        if not count:
            return
    raise RuntimeError(f"{function} did not finish for {table}")
