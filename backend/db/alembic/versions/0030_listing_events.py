"""Add listing_events and adopt listing_events_daily.

Revision ID: 0030_listing_events
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0030_listing_events"
down_revision: Union[str, None] = "0029_add_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create raw listing_events and adopt listing_events_daily."""
    op.create_table(
        "listing_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'"),
        ),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("client_event_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ('search', 'listing_view', 'cta_tap', " "'lead_relayed')",
            name="listing_events_type_allowed",
        ),
        sa.CheckConstraint(
            "source IN ('public_www', 'flutter', 'partner')",
            name="listing_events_source_allowed",
        ),
    )
    op.create_index(
        "listing_events_day_type_idx",
        "listing_events",
        ["occurred_on", "event_type", "location_id"],
    )
    op.create_index(
        "listing_events_client_id_uniq",
        "listing_events",
        ["source", "client_event_id"],
        unique=True,
    )

    # Adopt the table created by the lx-software receivables.sql script
    # (CREATE TABLE IF NOT EXISTS). Product owns writes; the board view
    # v_funnel_daily stays in the admin SQL.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_events_daily (
            day                 date NOT NULL,
            location_id         uuid NOT NULL
                DEFAULT '00000000-0000-0000-0000-000000000000',
            searches            integer NOT NULL DEFAULT 0,
            listing_views       integer NOT NULL DEFAULT 0,
            cta_taps            integer NOT NULL DEFAULT 0,
            leads_relayed       integer NOT NULL DEFAULT 0,
            bookings_confirmed  integer NOT NULL DEFAULT 0,
            PRIMARY KEY (day, location_id)
        );
        """
    )

    op.execute("GRANT SELECT, INSERT ON listing_events TO siutindei_admin;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON listing_events_daily TO siutindei_admin;"
    )


def downgrade() -> None:
    """Drop listing_events. Leave listing_events_daily for board views."""
    op.drop_index(
        "listing_events_client_id_uniq",
        table_name="listing_events",
    )
    op.drop_index(
        "listing_events_day_type_idx",
        table_name="listing_events",
    )
    op.drop_table("listing_events")
