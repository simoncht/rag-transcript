"""Soft delete for conversations and collections, FK fixes

Revision ID: 016
Revises: 015
Create Date: 2025-02-05

This migration adds:
- is_deleted and deleted_at columns to conversations (soft delete)
- is_deleted and deleted_at columns to collections (soft delete)
- Fixes subscriptions.user_id FK to include ondelete="CASCADE"
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # Add soft delete columns to conversations
    # ========================================================================
    op.add_column(
        "conversations",
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_conversations_is_deleted",
        "conversations",
        ["is_deleted"],
    )

    # ========================================================================
    # Add soft delete columns to collections
    # ========================================================================
    op.add_column(
        "collections",
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "collections",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_collections_is_deleted",
        "collections",
        ["is_deleted"],
    )

    # ========================================================================
    # Fix subscriptions.user_id FK to include ondelete="CASCADE"
    # ========================================================================
    # Drop the existing foreign key constraint
    op.drop_constraint(
        "subscriptions_user_id_fkey", "subscriptions", type_="foreignkey"
    )

    # Recreate with CASCADE
    op.create_foreign_key(
        "subscriptions_user_id_fkey",
        "subscriptions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # ========================================================================
    # Revert subscriptions.user_id FK
    # ========================================================================
    op.drop_constraint(
        "subscriptions_user_id_fkey", "subscriptions", type_="foreignkey"
    )
    op.create_foreign_key(
        "subscriptions_user_id_fkey",
        "subscriptions",
        "users",
        ["user_id"],
        ["id"],
    )

    # ========================================================================
    # Remove soft delete from collections
    # ========================================================================
    op.drop_index("idx_collections_is_deleted", table_name="collections")
    op.drop_column("collections", "deleted_at")
    op.drop_column("collections", "is_deleted")

    # ========================================================================
    # Remove soft delete from conversations
    # ========================================================================
    op.drop_index("idx_conversations_is_deleted", table_name="conversations")
    op.drop_column("conversations", "deleted_at")
    op.drop_column("conversations", "is_deleted")
