"""Add a reason on rejected organizations.

Revision ID: 0054_org_review_reason
Revises: 0053_translation_fixes

Seed assessment: review_reason is nullable. Existing seed inserts omit
it and stay valid. Seed organizations are approved, so the check that
a reason exists only on rejected rows holds. No seed rows change.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054_org_review_reason"
down_revision: Union[str, None] = "0053_translation_fixes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVIEW_REASONS = ("not_relevant", "duplicate", "poor_data", "other")


def upgrade() -> None:
    """Store why an organization was rejected."""
    op.add_column(
        "organizations",
        sa.Column("review_reason", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "organizations_review_reason_check",
        "organizations",
        "review_reason IS NULL OR review_reason IN ("
        + ", ".join(f"'{value}'" for value in REVIEW_REASONS)
        + ")",
    )
    op.create_check_constraint(
        "organizations_review_reason_rejected_check",
        "organizations",
        "review_reason IS NULL OR review_status = 'rejected'",
    )


def downgrade() -> None:
    """Drop the reject reason."""
    op.drop_constraint(
        "organizations_review_reason_rejected_check",
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        "organizations_review_reason_check",
        "organizations",
        type_="check",
    )
    op.drop_column("organizations", "review_reason")
