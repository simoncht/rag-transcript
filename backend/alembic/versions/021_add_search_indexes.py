"""Add search indexes for video library filtering

Revision ID: 021
Revises: 020
"""
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B-tree index on channel_name for fast channel filtering
    op.create_index(
        "ix_videos_channel_name",
        "videos",
        ["channel_name"],
        unique=False,
    )
    # GIN index on tags array for overlap queries
    op.create_index(
        "ix_videos_tags",
        "videos",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_videos_tags", table_name="videos")
    op.drop_index("ix_videos_channel_name", table_name="videos")
