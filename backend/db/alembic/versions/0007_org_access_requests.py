"""Add organization_access_requests table for owner onboarding.

This table tracks requests from owners who want to be added to an organization.
Requests are reviewed by admins and trigger email notifications.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007_org_access_requests"
down_revision: Union[str, None] = "0006_rename_to_media_urls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create organization_access_requests table.

    This table stores requests from users in the 'owner' group who want to
    be assigned to an organization. Each user can have at most one pending
    request at a time.

    Columns:
        - id: Primary key UUID
        - requester_id: Cognito user sub (subject) of the requesting user
        - requester_email: Email address of the requester for notifications
        - organization_name: Free text name of the organization they want to join
        - request_message: Optional message explaining the request
        - status: Request status (pending, approved, rejected)
        - created_at: When the request was submitted
        - updated_at: When the request was last modified
        - reviewed_at: When the request was reviewed (approved/rejected)
        - reviewed_by: Cognito user sub of the admin who reviewed
    """
    # Create the status enum type if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_request_status') THEN
                CREATE TYPE access_request_status AS ENUM ('pending', 'approved', 'rejected');
            END IF;
        END
        $$;
    """)

    op.create_table(
        "organization_access_requests",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "requester_id",
            sa.Text(),
            nullable=False,
            comment="Cognito user sub (subject) identifier of the requesting user",
        ),
        sa.Column(
            "requester_email",
            sa.Text(),
            nullable=False,
            comment="Email address of the requester",
        ),
        sa.Column(
            "organization_name",
            sa.Text(),
            nullable=False,
            comment="Name of the organization the user wants to join/create",
        ),
        sa.Column(
            "request_message",
            sa.Text(),
            nullable=True,
            comment="Optional message from the requester",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                name="access_request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "reviewed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When the request was reviewed",
        ),
        sa.Column(
            "reviewed_by",
            sa.Text(),
            nullable=True,
            comment="Cognito user sub of the admin who reviewed the request",
        ),
    )

    # Create index for efficient lookups by requester
    op.create_index(
        "organization_access_requests_requester_id_idx",
        "organization_access_requests",
        ["requester_id"],
    )

    # Create index for finding pending requests
    op.create_index(
        "organization_access_requests_status_idx",
        "organization_access_requests",
        ["status"],
    )

    # Create unique constraint to allow only one pending request per user
    op.create_index(
        "organization_access_requests_pending_unique",
        "organization_access_requests",
        ["requester_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    """Remove organization_access_requests table."""
    op.drop_index(
        "organization_access_requests_pending_unique",
        table_name="organization_access_requests",
    )
    op.drop_index(
        "organization_access_requests_status_idx",
        table_name="organization_access_requests",
    )
    op.drop_index(
        "organization_access_requests_requester_id_idx",
        table_name="organization_access_requests",
    )
    op.drop_table("organization_access_requests")
    op.execute("DROP TYPE IF EXISTS access_request_status")
