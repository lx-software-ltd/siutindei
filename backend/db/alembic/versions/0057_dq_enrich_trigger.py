"""Allow enrichment as a data-quality run trigger.

Revision ID: 0057_dq_enrich_trigger
Revises: 0056_org_enrichment_pages

Seed assessment: check constraint only. ``seed_data.sql`` does not
insert ``data_quality_runs``. Existing rows use ``import`` or
``manual`` and stay valid. No new column, seed value, or foreign key.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0057_dq_enrich_trigger"
down_revision: Union[str, None] = "0056_org_enrichment_pages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECK = "data_quality_runs_trigger_check"
_TABLE = "data_quality_runs"
_NEW = "trigger IN ('import', 'manual', 'enrichment')"
_OLD = "trigger IN ('import', 'manual')"


def upgrade() -> None:
    """Accept a run staged by website-enrichment apply."""
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, _NEW)


def downgrade() -> None:
    """Drop enrichment runs so the previous trigger check can return."""
    op.execute("DELETE FROM data_quality_runs WHERE trigger = 'enrichment'")
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, _OLD)
