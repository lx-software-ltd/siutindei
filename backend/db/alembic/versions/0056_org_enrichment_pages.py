"""Allow website enrichment to crawl up to 20 pages.

Revision ID: 0056_org_enrichment_pages
Revises: 0055_org_enrichment

Seed assessment: seed_data.sql has no org_enrichment_settings rows.
0055 inserts the singleton. This revision only widens its max_pages
check, raises the default from 6 to 12, and moves a row still on the old
default to 12. Existing seed SQL still runs.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056_org_enrichment_pages"
down_revision: Union[str, None] = "0055_org_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "org_enrichment_settings"
_CHECK = "org_enrichment_settings_pages_check"


def upgrade() -> None:
    """Widen max_pages to 1-20 and default to 12."""
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, "max_pages >= 1 AND max_pages <= 20")
    op.alter_column(_TABLE, "max_pages", server_default=sa.text("12"))
    op.execute(sa.text(f"UPDATE {_TABLE} SET max_pages = 12 WHERE max_pages = 6"))


def downgrade() -> None:
    """Restore max_pages 1-8 with default 6."""
    op.execute(sa.text(f"UPDATE {_TABLE} SET max_pages = 6 WHERE max_pages = 12"))
    op.execute(sa.text(f"UPDATE {_TABLE} SET max_pages = 8 WHERE max_pages > 8"))
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, "max_pages >= 1 AND max_pages <= 8")
    op.alter_column(_TABLE, "max_pages", server_default=sa.text("6"))
