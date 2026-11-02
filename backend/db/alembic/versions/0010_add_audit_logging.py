"""Add audit logging table and triggers.

This migration creates:
1. An audit_log table for storing change history
2. Trigger functions for automatic audit logging at the database level
3. Triggers on all main tables to capture changes

The hybrid approach provides:
- Application-level logging with full context (user, request ID)
- Database-level triggers as a safety net for direct changes
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_add_audit_logging"
down_revision: Union[str, None] = "0009_rename_owner_to_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables to add audit triggers to
AUDITED_TABLES = [
    "organizations",
    "locations",
    "activities",
    "activity_locations",
    "activity_pricing",
    "activity_schedule",
    "organization_access_requests",
]


def upgrade() -> None:
    """Create audit_log table and trigger infrastructure."""

    # Create the audit_log table
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column(
            "action",
            sa.Text(),
            nullable=False,
            comment="INSERT, UPDATE, or DELETE",
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            nullable=True,
            comment="Cognito user sub who made the change",
        ),
        sa.Column(
            "request_id",
            sa.Text(),
            nullable=True,
            comment="Lambda request ID for correlation",
        ),
        sa.Column(
            "old_values",
            postgresql.JSONB(),
            nullable=True,
            comment="Previous values (for UPDATE/DELETE)",
        ),
        sa.Column(
            "new_values",
            postgresql.JSONB(),
            nullable=True,
            comment="New values (for INSERT/UPDATE)",
        ),
        sa.Column(
            "changed_fields",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            comment="List of fields that changed (for UPDATE)",
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="trigger",
            comment="Source of the audit entry: trigger or application",
        ),
        sa.Column(
            "ip_address",
            sa.Text(),
            nullable=True,
            comment="Client IP address if available",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Client user agent if available",
        ),
    )

    # Create indexes for efficient querying
    op.create_index(
        "audit_log_table_record_idx",
        "audit_log",
        ["table_name", "record_id"],
    )
    op.create_index(
        "audit_log_timestamp_idx",
        "audit_log",
        ["timestamp"],
    )
    op.create_index(
        "audit_log_user_id_idx",
        "audit_log",
        ["user_id"],
    )
    op.create_index(
        "audit_log_action_idx",
        "audit_log",
        ["action"],
    )

    # Create the audit trigger function
    # This function reads context from session variables set by the application
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger_func()
        RETURNS TRIGGER AS $$
        DECLARE
            record_id_val TEXT;
            old_data JSONB;
            new_data JSONB;
            changed_cols TEXT[];
            col_name TEXT;
            current_user_id TEXT;
            current_request_id TEXT;
        BEGIN
            -- Get application context from session variables (set via SET LOCAL)
            current_user_id := current_setting('app.current_user_id', true);
            current_request_id := current_setting('app.current_request_id', true);

            -- Determine the record ID (handle composite keys for activity_locations)
            IF TG_TABLE_NAME = 'activity_locations' THEN
                IF TG_OP = 'DELETE' THEN
                    record_id_val := OLD.activity_id::text || ':' || OLD.location_id::text;
                ELSE
                    record_id_val := NEW.activity_id::text || ':' || NEW.location_id::text;
                END IF;
            ELSE
                IF TG_OP = 'DELETE' THEN
                    record_id_val := OLD.id::text;
                ELSE
                    record_id_val := NEW.id::text;
                END IF;
            END IF;

            -- Build JSON representations
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                old_data := to_jsonb(OLD);
            END IF;

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                new_data := to_jsonb(NEW);
            END IF;

            -- For updates, determine which columns changed
            IF TG_OP = 'UPDATE' THEN
                changed_cols := ARRAY[]::TEXT[];
                FOR col_name IN
                    SELECT key FROM jsonb_object_keys(new_data) AS key
                LOOP
                    IF (old_data->col_name) IS DISTINCT FROM (new_data->col_name) THEN
                        changed_cols := array_append(changed_cols, col_name);
                    END IF;
                END LOOP;

                -- Skip audit if nothing actually changed
                IF array_length(changed_cols, 1) IS NULL THEN
                    RETURN NEW;
                END IF;
            END IF;

            -- Insert the audit record
            INSERT INTO audit_log (
                table_name,
                record_id,
                action,
                user_id,
                request_id,
                old_values,
                new_values,
                changed_fields,
                source
            ) VALUES (
                TG_TABLE_NAME,
                record_id_val,
                TG_OP,
                NULLIF(current_user_id, ''),
                NULLIF(current_request_id, ''),
                old_data,
                new_data,
                changed_cols,
                'trigger'
            );

            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create triggers on all audited tables
    for table_name in AUDITED_TABLES:
        op.execute(f"""
            CREATE TRIGGER {table_name}_audit_trigger
            AFTER INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
        """)

    # Grant permissions to the app and admin users
    op.execute("GRANT SELECT, INSERT ON audit_log TO siutindei_app;")
    op.execute("GRANT SELECT, INSERT ON audit_log TO siutindei_admin;")


def downgrade() -> None:
    """Remove audit logging infrastructure."""

    # Drop triggers from all tables
    for table_name in AUDITED_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS {table_name}_audit_trigger ON {table_name};"
        )

    # Drop the trigger function
    op.execute("DROP FUNCTION IF EXISTS audit_trigger_func();")

    # Drop indexes
    op.drop_index("audit_log_action_idx", table_name="audit_log")
    op.drop_index("audit_log_user_id_idx", table_name="audit_log")
    op.drop_index("audit_log_timestamp_idx", table_name="audit_log")
    op.drop_index("audit_log_table_record_idx", table_name="audit_log")

    # Drop the audit_log table
    op.drop_table("audit_log")
