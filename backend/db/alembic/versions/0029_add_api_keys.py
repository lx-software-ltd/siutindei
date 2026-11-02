"""Add api_keys table for partner API authentication."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_add_api_keys"
down_revision: Union[str, None] = "0028_hk_regions_wizard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the api_keys table used by the partner API authorizer."""
    op.create_table(
        "api_keys",
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
            comment="Human-readable label for the key (e.g. partner name)",
        ),
        sa.Column(
            "key_prefix",
            sa.Text(),
            nullable=False,
            comment="First characters of the plaintext key, for display",
        ),
        sa.Column(
            "key_hash",
            sa.Text(),
            nullable=False,
            comment="SHA-256 hex digest of the plaintext key",
        ),
        sa.Column(
            "scope",
            sa.Text(),
            nullable=False,
            comment="Access scope: read (query only) or crud (query + edit)",
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
            comment="Restrict the key to one organization; NULL = full access",
        ),
        sa.Column(
            "created_by",
            sa.Text(),
            nullable=True,
            comment="Cognito sub of the admin who created the key",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Optional expiry; NULL = does not expire",
        ),
        sa.Column(
            "revoked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Set when the key is revoked; NULL = active",
        ),
        sa.Column(
            "last_used_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "scope IN ('read', 'crud')",
            name="api_keys_scope_allowed",
        ),
    )
    op.create_index(
        "api_keys_key_hash_unique",
        "api_keys",
        ["key_hash"],
        unique=True,
    )
    op.create_index("api_keys_org_id_idx", "api_keys", ["org_id"])

    # The authorizer runs as the read-only app user; it validates keys via
    # SELECT and refreshes last_used_at via a column-scoped UPDATE grant.
    op.execute("GRANT SELECT ON api_keys TO siutindei_app;")
    op.execute("GRANT UPDATE (last_used_at) ON api_keys TO siutindei_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys TO siutindei_admin;")

    op.execute(
        """
        CREATE TRIGGER api_keys_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON api_keys
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
        """
    )


def downgrade() -> None:
    """Drop the api_keys table."""
    op.execute("DROP TRIGGER IF EXISTS api_keys_audit_trigger ON api_keys;")
    op.drop_index("api_keys_org_id_idx", table_name="api_keys")
    op.drop_index("api_keys_key_hash_unique", table_name="api_keys")
    op.drop_table("api_keys")
