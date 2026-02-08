"""Add collection_themes table for LLM-powered theme clustering

Revision ID: 019
Revises: 018
Create Date: 2026-02-08

Stores clustered themes per collection: LLM-generated labels,
descriptions, member video IDs, and relevance scores.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers, used by Alembic
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_themes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "collection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("theme_label", sa.String(255), nullable=False),
        sa.Column("theme_description", sa.Text, nullable=True),
        sa.Column("video_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column(
            "topic_keywords", ARRAY(sa.Text), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("collection_themes")
