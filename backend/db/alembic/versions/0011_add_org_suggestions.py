"""Add organization suggestions table for public user submissions.

This migration creates a table for users to suggest new organizations
(places) for admins to review. Unlike access requests, users don't
become managers - they simply inform about new places.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_add_org_suggestions"
down_revision: Union[str, None] = "0010_add_audit_logging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create organization_suggestions table and related infrastructure."""

    # Create the suggestion status enum
    suggestion_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="suggestion_status",
        create_type=False,
    )
    suggestion_status_enum.create(op.get_bind(), checkfirst=True)

    # Create the organization_suggestions table
    op.create_table(
        "organization_suggestions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ticket_id",
            sa.Text(),
            nullable=False,
            unique=True,
            comment="Unique progressive ticket ID (format: S + 5 digits)",
        ),
        sa.Column(
            "suggester_id",
            sa.Text(),
            nullable=False,
            comment="Cognito user sub of the person suggesting",
        ),
        sa.Column(
            "suggester_email",
            sa.Text(),
            nullable=False,
            comment="Email of the suggester for notifications",
        ),
        sa.Column(
            "organization_name",
            sa.Text(),
            nullable=False,
            comment="Suggested name for the organization",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description of the organization/place",
        ),
        sa.Column(
            "suggested_district",
            sa.Text(),
            nullable=True,
            comment="District where the place is located",
        ),
        sa.Column(
            "suggested_address",
            sa.Text(),
            nullable=True,
            comment="Full address of the place",
        ),
        sa.Column(
            "suggested_lat",
            sa.Numeric(9, 6),
            nullable=True,
            comment="Latitude coordinate",
        ),
        sa.Column(
            "suggested_lng",
            sa.Numeric(9, 6),
            nullable=True,
            comment="Longitude coordinate",
        ),
        sa.Column(
            "media_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
            comment="URLs of uploaded pictures",
        ),
        sa.Column(
            "additional_notes",
            sa.Text(),
            nullable=True,
            comment="Any additional information from the suggester",
        ),
        sa.Column(
            "status",
            suggestion_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
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
            comment="When the suggestion was reviewed",
        ),
        sa.Column(
            "reviewed_by",
            sa.Text(),
            nullable=True,
            comment="Cognito user sub of the admin who reviewed",
        ),
        sa.Column(
            "admin_notes",
            sa.Text(),
            nullable=True,
            comment="Notes from the reviewing admin",
        ),
        sa.Column(
            "created_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            comment="ID of organization created from this suggestion (if approved)",
        ),
    )

    # Create indexes for efficient querying
    op.create_index(
        "organization_suggestions_status_idx",
        "organization_suggestions",
        ["status"],
    )
    op.create_index(
        "organization_suggestions_suggester_idx",
        "organization_suggestions",
        ["suggester_id"],
    )
    op.create_index(
        "organization_suggestions_created_at_idx",
        "organization_suggestions",
        ["created_at"],
    )

    # Grant permissions to the app and admin users
    op.execute("GRANT SELECT, INSERT ON organization_suggestions TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON organization_suggestions TO siutindei_admin;"
    )

    # Add audit trigger for this table
    op.execute("""
        CREATE TRIGGER organization_suggestions_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON organization_suggestions
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)


def downgrade() -> None:
    """Remove organization_suggestions table and related infrastructure."""

    # Drop the audit trigger
    op.execute(
        "DROP TRIGGER IF EXISTS organization_suggestions_audit_trigger "
        "ON organization_suggestions;"
    )

    # Drop indexes
    op.drop_index(
        "organization_suggestions_created_at_idx",
        table_name="organization_suggestions",
    )
    op.drop_index(
        "organization_suggestions_suggester_idx",
        table_name="organization_suggestions",
    )
    op.drop_index(
        "organization_suggestions_status_idx",
        table_name="organization_suggestions",
    )

    # Drop the table
    op.drop_table("organization_suggestions")

    # Drop the enum type
    suggestion_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="suggestion_status",
        create_type=False,
    )
    suggestion_status_enum.drop(op.get_bind(), checkfirst=True)
