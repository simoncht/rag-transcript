"""add clerk_user_id to users

Revision ID: 005_add_clerk_user_id
Revises: 004_add_conversation_sources
Create Date: 2025-12-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_add_clerk_user_id"
down_revision: Union[str, None] = "004_add_conversation_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add clerk_user_id column and unique index on users."""
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove clerk_user_id column and index."""
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")
