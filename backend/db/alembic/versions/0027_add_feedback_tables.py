"""Add feedback labels and organization feedback tables."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_add_feedback_tables"
down_revision: Union[str, None] = "0026_org_name_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create feedback labels, feedback records, and ticket fields."""
    op.execute(
        "ALTER TYPE ticket_type " "ADD VALUE IF NOT EXISTS 'organization_feedback'"
    )

    op.add_column(
        "tickets",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "feedback_stars",
            sa.SmallInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "feedback_label_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "feedback_text",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "tickets_organization_id_fkey",
        "tickets",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "tickets_org_id_idx",
        "tickets",
        ["organization_id"],
    )
    op.create_index(
        "tickets_feedback_stars_idx",
        "tickets",
        ["feedback_stars"],
    )
    op.create_index(
        "tickets_feedback_label_ids_gin",
        "tickets",
        ["feedback_label_ids"],
        postgresql_using="gin",
    )
    op.create_check_constraint(
        "tickets_feedback_stars_range",
        "tickets",
        "feedback_stars BETWEEN 0 AND 5",
    )

    op.create_table(
        "feedback_labels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
    )
    op.create_index(
        "feedback_labels_name_unique_ci",
        "feedback_labels",
        [sa.text("lower(trim(name))")],
        unique=True,
    )
    op.create_index(
        "feedback_labels_display_order_idx",
        "feedback_labels",
        ["display_order"],
    )

    op.create_table(
        "organization_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitter_id",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "submitter_email",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "stars",
            sa.SmallInteger(),
            nullable=False,
        ),
        sa.Column(
            "label_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "source_ticket_id",
            sa.Text(),
            nullable=True,
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
        sa.CheckConstraint(
            "stars BETWEEN 0 AND 5",
            name="organization_feedback_stars_range",
        ),
    )
    op.create_index(
        "organization_feedback_org_idx",
        "organization_feedback",
        ["organization_id"],
    )
    op.create_index(
        "organization_feedback_submitter_idx",
        "organization_feedback",
        ["submitter_id"],
    )
    op.create_index(
        "organization_feedback_created_at_idx",
        "organization_feedback",
        ["created_at"],
    )
    op.create_index(
        "organization_feedback_label_ids_gin",
        "organization_feedback",
        ["label_ids"],
        postgresql_using="gin",
    )

    op.execute("GRANT SELECT ON feedback_labels TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE " "ON feedback_labels TO siutindei_admin;"
    )
    op.execute("GRANT SELECT ON organization_feedback TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON organization_feedback TO siutindei_admin;"
    )

    op.execute(
        """
        CREATE TRIGGER feedback_labels_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON feedback_labels
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
        """
    )
    op.execute(
        """
        CREATE TRIGGER organization_feedback_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON organization_feedback
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
        """
    )


def downgrade() -> None:
    """Drop feedback labels, feedback records, and ticket fields."""
    op.execute(
        "DROP TRIGGER IF EXISTS feedback_labels_audit_trigger ON feedback_labels;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS organization_feedback_audit_trigger "
        "ON organization_feedback;"
    )
    op.drop_index(
        "organization_feedback_label_ids_gin",
        table_name="organization_feedback",
    )
    op.drop_index(
        "organization_feedback_created_at_idx",
        table_name="organization_feedback",
    )
    op.drop_index(
        "organization_feedback_submitter_idx",
        table_name="organization_feedback",
    )
    op.drop_index(
        "organization_feedback_org_idx",
        table_name="organization_feedback",
    )
    op.drop_table("organization_feedback")

    op.drop_index(
        "feedback_labels_display_order_idx",
        table_name="feedback_labels",
    )
    op.drop_index(
        "feedback_labels_name_unique_ci",
        table_name="feedback_labels",
    )
    op.drop_table("feedback_labels")

    op.drop_constraint(
        "tickets_feedback_stars_range",
        "tickets",
        type_="check",
    )
    op.drop_index("tickets_feedback_label_ids_gin", table_name="tickets")
    op.drop_index("tickets_feedback_stars_idx", table_name="tickets")
    op.drop_index("tickets_org_id_idx", table_name="tickets")
    op.drop_constraint(
        "tickets_organization_id_fkey",
        "tickets",
        type_="foreignkey",
    )
    op.drop_column("tickets", "feedback_text")
    op.drop_column("tickets", "feedback_label_ids")
    op.drop_column("tickets", "feedback_stars")
    op.drop_column("tickets", "organization_id")
