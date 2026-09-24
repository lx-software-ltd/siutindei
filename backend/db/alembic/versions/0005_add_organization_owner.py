"""Add owner_id column to organizations for Cognito user ownership."""

from __future__ import annotations

import os
from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_organization_owner"
down_revision: Union[str, None] = "0004_add_organization_pictures"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_fallback_owner_sub() -> str:
    """Get the Cognito user sub for the fallback owner.

    Queries Cognito to find the user by email and returns their sub.
    The fallback owner email is read from the FALLBACK_OWNER_EMAIL environment variable.

    Returns:
        The Cognito user sub (UUID string).

    Raises:
        RuntimeError: If the user cannot be found or required env vars are not set.
    """
    from app.services.aws_proxy import invoke as aws_proxy

    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    if not user_pool_id:
        raise RuntimeError(
            "COGNITO_USER_POOL_ID environment variable is required for migration"
        )

    fallback_owner_email = os.environ.get("FALLBACK_OWNER_EMAIL")
    if not fallback_owner_email:
        raise RuntimeError(
            "FALLBACK_OWNER_EMAIL environment variable is required for migration. "
            "Set it in the FallbackOwnerEmail parameter in production.json."
        )

    response = aws_proxy(
        "cognito-idp",
        "list_users",
        {
            "UserPoolId": user_pool_id,
            "Filter": f'email = "{fallback_owner_email}"',
            "Limit": 1,
        },
    )

    users = response.get("Users", [])
    if not users:
        raise RuntimeError(
            f"Fallback owner user with email '{fallback_owner_email}' not found in Cognito. "
            "Please create this user before running the migration."
        )

    # Extract the sub attribute
    user = users[0]
    attributes = {attr["Name"]: attr["Value"] for attr in user.get("Attributes", [])}
    sub = attributes.get("sub")

    if not sub:
        raise RuntimeError(
            f"Fallback owner user '{fallback_owner_email}' does not have a sub attribute"
        )

    return sub


def upgrade() -> None:
    """Add owner_id column to organizations table.

    The owner_id references a Cognito user's sub (subject) identifier.
    This is stored as TEXT since Cognito subs are UUID strings.
    The column is NOT NULL - every organization must have an owner.

    Existing organizations without an owner will be assigned to the fallback
    owner identified by the FALLBACK_OWNER_EMAIL environment variable.
    """
    # First add the column as nullable
    op.add_column(
        "organizations",
        sa.Column(
            "owner_id",
            sa.Text(),
            nullable=True,
            comment="Cognito user sub (subject) identifier of the organization owner",
        ),
    )

    # Create an index for efficient lookups by owner
    op.create_index(
        "organizations_owner_id_idx",
        "organizations",
        ["owner_id"],
    )

    # Check if there are any existing organizations without owner_id
    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM organizations WHERE owner_id IS NULL")
    )
    null_count = result.scalar()

    if null_count and null_count > 0:
        # Get the fallback owner's Cognito sub
        fallback_owner_sub = _get_fallback_owner_sub()

        # Update existing organizations to use the fallback owner
        connection.execute(
            sa.text(
                "UPDATE organizations SET owner_id = :owner_id WHERE owner_id IS NULL"
            ),
            {"owner_id": fallback_owner_sub},
        )

    # Make the column NOT NULL
    op.alter_column(
        "organizations",
        "owner_id",
        nullable=False,
    )


def downgrade() -> None:
    """Remove owner_id column from organizations."""
    op.drop_index("organizations_owner_id_idx", table_name="organizations")
    op.drop_column("organizations", "owner_id")
