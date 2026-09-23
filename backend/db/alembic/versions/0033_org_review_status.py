"""Add organization review gate columns and import job status.

Revision ID: 0033_org_review_status
Revises: 0032_org_listing_status

Every existing organization is backfilled to pending_review (the column
default). Seed rows set review_status explicitly to approved. Public
search keeps showing unapproved rows until ORG_REVIEW_GATE_ENABLED is
true. v_catalog_health counts approved rows only.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0033_org_review_status"
down_revision: Union[str, None] = "0032_org_listing_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVIEW_STATUS_VALUES = ("pending_review", "approved", "rejected")
IMPORT_JOB_STATUS_VALUES = ("running", "completed", "failed")

_CATALOG_HEALTH_WHERE = """
        WHERE o.status IN ('operational', 'closed_temporarily')
          AND o.review_status = 'approved'
"""

_CATALOG_HEALTH_WHERE_LEGACY = """
        WHERE o.status IN ('operational', 'closed_temporarily')
"""

_CATALOG_HEALTH_SELECT = """
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
"""


def _catalog_health_sql(where_clause: str) -> str:
    return (
        "CREATE VIEW v_catalog_health AS\n"
        + _CATALOG_HEALTH_SELECT
        + where_clause
        + "        GROUP BY ga.name, ac.name\n"
    )


def upgrade() -> None:
    """Add review columns, job status, and tighten the catalog view."""
    op.add_column(
        "organizations",
        sa.Column(
            "review_status",
            sa.Text(),
            nullable=False,
            server_default="pending_review",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "reviewed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("reviewed_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "last_imported_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "organizations_review_status_check",
        "organizations",
        "review_status IN ("
        + ", ".join(f"'{value}'" for value in REVIEW_STATUS_VALUES)
        + ")",
    )
    op.create_foreign_key(
        "organizations_import_job_fk",
        "organizations",
        "import_jobs",
        ["import_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "organizations_review_status_idx",
        "organizations",
        ["review_status"],
    )
    op.create_index(
        "organizations_import_job_id_idx",
        "organizations",
        ["import_job_id"],
        postgresql_where=sa.text("import_job_id IS NOT NULL"),
    )

    op.add_column(
        "import_jobs",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="completed",
        ),
    )
    op.create_check_constraint(
        "import_jobs_status_check",
        "import_jobs",
        "status IN ("
        + ", ".join(f"'{value}'" for value in IMPORT_JOB_STATUS_VALUES)
        + ")",
    )

    op.execute("DROP VIEW IF EXISTS v_catalog_health")
    op.execute(_catalog_health_sql(_CATALOG_HEALTH_WHERE))
    op.execute("GRANT SELECT ON v_catalog_health TO siutindei_admin;")


def downgrade() -> None:
    """Remove review columns and restore the previous catalog view."""
    op.execute("DROP VIEW IF EXISTS v_catalog_health")
    op.execute(_catalog_health_sql(_CATALOG_HEALTH_WHERE_LEGACY))
    op.execute("GRANT SELECT ON v_catalog_health TO siutindei_admin;")
    op.drop_constraint(
        "import_jobs_status_check",
        "import_jobs",
        type_="check",
    )
    op.drop_column("import_jobs", "status")
    op.drop_index(
        "organizations_import_job_id_idx",
        table_name="organizations",
    )
    op.drop_index(
        "organizations_review_status_idx",
        table_name="organizations",
    )
    op.drop_constraint(
        "organizations_import_job_fk",
        "organizations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "organizations_review_status_check",
        "organizations",
        type_="check",
    )
    op.drop_column("organizations", "last_imported_at")
    op.drop_column("organizations", "import_job_id")
    op.drop_column("organizations", "review_notes")
    op.drop_column("organizations", "reviewed_by")
    op.drop_column("organizations", "reviewed_at")
    op.drop_column("organizations", "review_status")
