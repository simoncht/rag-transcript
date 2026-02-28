"""Add collection_insights table

Revision ID: 020
Revises: 019
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "video_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("extraction_prompt_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("graph_data", postgresql.JSONB(), nullable=False),
        sa.Column("topic_chunks", postgresql.JSONB(), nullable=False),
        sa.Column("topics_count", sa.Integer(), nullable=False),
        sa.Column("total_chunks_analyzed", sa.Integer(), nullable=False),
        sa.Column("generation_time_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_collection_insights_collection_id",
        "collection_insights",
        ["collection_id"],
    )
    op.create_index(
        "ix_collection_insights_user_id", "collection_insights", ["user_id"]
    )
    op.create_index(
        "ix_collection_insights_created_at", "collection_insights", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_collection_insights_created_at", table_name="collection_insights")
    op.drop_index("ix_collection_insights_user_id", table_name="collection_insights")
    op.drop_index(
        "ix_collection_insights_collection_id", table_name="collection_insights"
    )
    op.drop_table("collection_insights")
