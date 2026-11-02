"""Create tickets table and migrate data from legacy tables.

This migration creates the `tickets` table and migrates existing data
from `organization_access_requests` and `organization_suggestions`,
then drops those tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_unify_tickets"
down_revision: Union[str, None] = "0011_add_org_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create unified tickets table and migrate data."""

    # Create the ticket_type enum
    ticket_type_enum = postgresql.ENUM(
        "access_request",
        "organization_suggestion",
        name="ticket_type",
        create_type=False,
    )
    ticket_type_enum.create(op.get_bind(), checkfirst=True)

    # Create the ticket_status enum (reuse values from both existing enums)
    ticket_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="ticket_status",
        create_type=False,
    )
    ticket_status_enum.create(op.get_bind(), checkfirst=True)

    # Create the unified tickets table
    op.create_table(
        "tickets",
        # --- Common fields ---
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
            comment="Unique progressive ticket ID (R00001 for requests, S00001 for suggestions)",
        ),
        sa.Column(
            "ticket_type",
            ticket_type_enum,
            nullable=False,
            comment="Type of ticket: access_request or organization_suggestion",
        ),
        sa.Column(
            "submitter_id",
            sa.Text(),
            nullable=False,
            comment="Cognito user sub of the person who submitted",
        ),
        sa.Column(
            "submitter_email",
            sa.Text(),
            nullable=False,
            comment="Email of the submitter for notifications",
        ),
        sa.Column(
            "organization_name",
            sa.Text(),
            nullable=False,
            comment="Organization name (requested or suggested)",
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=True,
            comment="Free-text message from submitter (request_message or additional_notes)",
        ),
        sa.Column(
            "status",
            ticket_status_enum,
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
            comment="When the ticket was reviewed",
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
        # --- Suggestion-specific fields (nullable) ---
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description of the suggested place",
        ),
        sa.Column(
            "suggested_district",
            sa.Text(),
            nullable=True,
            comment="District where the suggested place is located",
        ),
        sa.Column(
            "suggested_address",
            sa.Text(),
            nullable=True,
            comment="Full address of the suggested place",
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
            comment="URLs of uploaded media files",
        ),
        sa.Column(
            "created_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            comment="ID of organization created/assigned on approval",
        ),
    )

    # Create indexes for efficient querying
    op.create_index("tickets_type_idx", "tickets", ["ticket_type"])
    op.create_index("tickets_status_idx", "tickets", ["status"])
    op.create_index("tickets_submitter_idx", "tickets", ["submitter_id"])
    op.create_index("tickets_created_at_idx", "tickets", ["created_at"])
    op.create_index("tickets_type_status_idx", "tickets", ["ticket_type", "status"])

    # Grant permissions
    op.execute("GRANT SELECT, INSERT ON tickets TO siutindei_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON tickets TO siutindei_admin;")

    # Add audit trigger
    op.execute("""
        CREATE TRIGGER tickets_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON tickets
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)

    # --- Migrate data from organization_access_requests ---
    op.execute("""
        INSERT INTO tickets (
            id, ticket_id, ticket_type, submitter_id, submitter_email,
            organization_name, message, status, created_at, updated_at,
            reviewed_at, reviewed_by, admin_notes
        )
        SELECT
            id, ticket_id, 'access_request'::ticket_type,
            requester_id, requester_email,
            organization_name, request_message,
            status::text::ticket_status,
            created_at, updated_at,
            reviewed_at, reviewed_by, NULL
        FROM organization_access_requests;
    """)

    # --- Migrate data from organization_suggestions ---
    op.execute("""
        INSERT INTO tickets (
            id, ticket_id, ticket_type, submitter_id, submitter_email,
            organization_name, message, status, created_at, updated_at,
            reviewed_at, reviewed_by, admin_notes,
            description, suggested_district, suggested_address,
            suggested_lat, suggested_lng, media_urls,
            created_organization_id
        )
        SELECT
            id, ticket_id, 'organization_suggestion'::ticket_type,
            suggester_id, suggester_email,
            organization_name, additional_notes,
            status::text::ticket_status,
            created_at, updated_at,
            reviewed_at, reviewed_by, admin_notes,
            description, suggested_district, suggested_address,
            suggested_lat, suggested_lng, media_urls,
            created_organization_id
        FROM organization_suggestions;
    """)

    # Drop old audit triggers
    op.execute(
        "DROP TRIGGER IF EXISTS organization_access_requests_audit_trigger "
        "ON organization_access_requests;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS organization_suggestions_audit_trigger "
        "ON organization_suggestions;"
    )

    # Drop old tables
    op.drop_table("organization_suggestions")
    op.drop_table("organization_access_requests")

    # Drop old enum types
    op.execute("DROP TYPE IF EXISTS suggestion_status;")
    op.execute("DROP TYPE IF EXISTS access_request_status;")


def downgrade() -> None:
    """Recreate separate tables and migrate data back."""

    # Recreate the old enum types
    access_request_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="access_request_status",
        create_type=False,
    )
    access_request_status.create(op.get_bind(), checkfirst=True)

    suggestion_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="suggestion_status",
        create_type=False,
    )
    suggestion_status.create(op.get_bind(), checkfirst=True)

    # Recreate organization_access_requests
    op.create_table(
        "organization_access_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ticket_id", sa.Text(), nullable=False, unique=True),
        sa.Column("requester_id", sa.Text(), nullable=False),
        sa.Column("requester_email", sa.Text(), nullable=False),
        sa.Column("organization_name", sa.Text(), nullable=False),
        sa.Column("request_message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            access_request_status,
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
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
    )

    # Recreate organization_suggestions
    op.create_table(
        "organization_suggestions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ticket_id", sa.Text(), nullable=False, unique=True),
        sa.Column("suggester_id", sa.Text(), nullable=False),
        sa.Column("suggester_email", sa.Text(), nullable=False),
        sa.Column("organization_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("suggested_district", sa.Text(), nullable=True),
        sa.Column("suggested_address", sa.Text(), nullable=True),
        sa.Column("suggested_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("suggested_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column(
            "media_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("additional_notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            suggestion_status,
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
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Migrate data back
    op.execute("""
        INSERT INTO organization_access_requests (
            id, ticket_id, requester_id, requester_email,
            organization_name, request_message, status,
            created_at, updated_at, reviewed_at, reviewed_by
        )
        SELECT
            id, ticket_id, submitter_id, submitter_email,
            organization_name, message,
            status::text::access_request_status,
            created_at, updated_at, reviewed_at, reviewed_by
        FROM tickets
        WHERE ticket_type = 'access_request';
    """)

    op.execute("""
        INSERT INTO organization_suggestions (
            id, ticket_id, suggester_id, suggester_email,
            organization_name, additional_notes, status,
            created_at, updated_at, reviewed_at, reviewed_by, admin_notes,
            description, suggested_district, suggested_address,
            suggested_lat, suggested_lng, media_urls,
            created_organization_id
        )
        SELECT
            id, ticket_id, submitter_id, submitter_email,
            organization_name, message,
            status::text::suggestion_status,
            created_at, updated_at, reviewed_at, reviewed_by, admin_notes,
            description, suggested_district, suggested_address,
            suggested_lat, suggested_lng, media_urls,
            created_organization_id
        FROM tickets
        WHERE ticket_type = 'organization_suggestion';
    """)

    # Re-add indexes and triggers for old tables
    op.create_index(
        "org_access_req_status_idx", "organization_access_requests", ["status"]
    )
    op.create_index(
        "org_access_req_requester_idx", "organization_access_requests", ["requester_id"]
    )
    op.execute("""
        CREATE TRIGGER organization_access_requests_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON organization_access_requests
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)

    op.create_index(
        "organization_suggestions_status_idx", "organization_suggestions", ["status"]
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
    op.execute("""
        CREATE TRIGGER organization_suggestions_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON organization_suggestions
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)

    # Grant permissions on old tables
    op.execute("GRANT SELECT, INSERT ON organization_access_requests TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON organization_access_requests TO siutindei_admin;"
    )
    op.execute("GRANT SELECT, INSERT ON organization_suggestions TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON organization_suggestions TO siutindei_admin;"
    )

    # Drop the unified tickets table
    op.execute("DROP TRIGGER IF EXISTS tickets_audit_trigger ON tickets;")
    op.drop_table("tickets")
    op.execute("DROP TYPE IF EXISTS ticket_type;")
    op.execute("DROP TYPE IF EXISTS ticket_status;")
