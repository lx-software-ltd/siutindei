"""Add catalog listing status, place_id, and import jobs.

Revision ID: 0032_org_listing_status
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0032_org_listing_status"
down_revision: Union[str, None] = "0031_link_orphan_activities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORG_STATUS_VALUES = (
    "operational",
    "closed_temporarily",
    "closed_permanently",
    "hidden",
)
STATUS_SOURCE_VALUES = ("owner", "provider", "places", "importer")
DESCRIPTION_SOURCE_VALUES = ("template", "official", "places", "enrich")


def upgrade() -> None:
    """Add listing columns, indexes, import jobs, and catalog view."""
    op.add_column(
        "organizations",
        sa.Column("place_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="operational",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "status_changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("status_source", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("source", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("source_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("description_source", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "organizations_status_check",
        "organizations",
        "status IN (" + ", ".join(f"'{v}'" for v in ORG_STATUS_VALUES) + ")",
    )
    op.create_check_constraint(
        "organizations_status_source_check",
        "organizations",
        "status_source IS NULL OR status_source IN ("
        + ", ".join(f"'{v}'" for v in STATUS_SOURCE_VALUES)
        + ")",
    )
    op.create_check_constraint(
        "organizations_desc_source_check",
        "organizations",
        "description_source IS NULL OR description_source IN ("
        + ", ".join(f"'{v}'" for v in DESCRIPTION_SOURCE_VALUES)
        + ")",
    )
    op.create_index(
        "organizations_place_id_uniq",
        "organizations",
        ["place_id"],
        unique=True,
        postgresql_where=sa.text("place_id IS NOT NULL"),
    )
    op.create_index(
        "organizations_source_id_idx",
        "organizations",
        ["source_id"],
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )

    op.add_column(
        "locations",
        sa.Column("place_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "locations_place_id_uniq",
        "locations",
        ["place_id"],
        unique=True,
        postgresql_where=sa.text("place_id IS NOT NULL"),
    )

    op.create_table(
        "import_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column(
            "dry_run",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "results",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "file_warnings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        "import_jobs_object_key_uniq",
        "import_jobs",
        ["object_key"],
        unique=True,
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON import_jobs TO siutindei_admin;")

    # Production already has this view with integer count columns.
    # CREATE OR REPLACE cannot change integer → bigint (COUNT), so drop first
    # and cast counts back to integer.
    op.execute("DROP VIEW IF EXISTS v_catalog_health")
    op.execute(
        """
        CREATE VIEW v_catalog_health AS
        SELECT
          COALESCE(ga.name, 'Unknown') AS district,
          COALESCE(ac.name, 'Unknown') AS category,
          COUNT(DISTINCT a.id)::integer AS activities,
          COUNT(DISTINCT o.id)::integer AS providers,
          COUNT(DISTINCT l.id)::integer AS stores,
          CASE
            WHEN COUNT(DISTINCT o.id) = 0 THEN 0
            ELSE ROUND(
              (
                COUNT(DISTINCT o.id) FILTER (
                  WHERE COALESCE(cardinality(o.media_urls), 0) > 0
                )::numeric
                + COUNT(DISTINCT a.id) FILTER (
                  WHERE EXISTS (
                    SELECT 1 FROM activity_pricing ap
                    WHERE ap.activity_id = a.id
                  )
                )::numeric
                + COUNT(DISTINCT a.id) FILTER (
                  WHERE EXISTS (
                    SELECT 1 FROM activity_schedule s
                    WHERE s.activity_id = a.id
                  )
                )::numeric
                + COUNT(DISTINCT l.id) FILTER (
                  WHERE l.lat IS NOT NULL AND l.lng IS NOT NULL
                )::numeric
              )
              / NULLIF(COUNT(DISTINCT o.id) * 4.0, 0),
              4
            )
          END AS completeness,
          COUNT(DISTINCT o.id) FILTER (
            WHERE COALESCE(cardinality(o.media_urls), 0) > 0
          )::integer AS has_photo,
          COUNT(DISTINCT a.id) FILTER (
            WHERE EXISTS (
              SELECT 1 FROM activity_pricing ap
              WHERE ap.activity_id = a.id
            )
          )::integer AS has_price,
          COUNT(DISTINCT a.id) FILTER (
            WHERE EXISTS (
              SELECT 1 FROM activity_schedule s
              WHERE s.activity_id = a.id
            )
          )::integer AS has_schedule,
          COUNT(DISTINCT l.id) FILTER (
            WHERE l.lat IS NOT NULL AND l.lng IS NOT NULL
          )::integer AS has_geo
        FROM organizations o
        LEFT JOIN locations l ON l.org_id = o.id
        LEFT JOIN geographic_areas ga ON ga.id = l.area_id
        LEFT JOIN activities a ON a.org_id = o.id
        LEFT JOIN activity_categories ac ON ac.id = a.category_id
        WHERE o.status IN ('operational', 'closed_temporarily')
        GROUP BY ga.name, ac.name
        """
    )
    op.execute("GRANT SELECT ON v_catalog_health TO siutindei_admin;")


def downgrade() -> None:
    """Remove listing columns, import jobs, and catalog view."""
    op.execute("DROP VIEW IF EXISTS v_catalog_health")
    op.drop_index("import_jobs_object_key_uniq", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("locations_place_id_uniq", table_name="locations")
    op.drop_column("locations", "place_id")
    op.drop_index("organizations_source_id_idx", table_name="organizations")
    op.drop_index("organizations_place_id_uniq", table_name="organizations")
    op.drop_constraint(
        "organizations_desc_source_check",
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        "organizations_status_source_check",
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        "organizations_status_check",
        "organizations",
        type_="check",
    )
    op.drop_column("organizations", "description_source")
    op.drop_column("organizations", "source_id")
    op.drop_column("organizations", "source")
    op.drop_column("organizations", "status_source")
    op.drop_column("organizations", "status_changed_at")
    op.drop_column("organizations", "status")
    op.drop_column("organizations", "place_id")
