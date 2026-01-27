"""Add LLM usage tracking table for cost monitoring

Revision ID: 012_add_llm_usage
Revises: 011_add_transcript_source
Create Date: 2025-01-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create llm_usage_events table
    op.create_table(
        "llm_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="deepseek"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_miss_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("response_time_seconds", sa.Numeric(10, 3), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
    )

    # Create indexes for analytics queries
    op.create_index("ix_llm_usage_events_user_id", "llm_usage_events", ["user_id"])
    op.create_index("ix_llm_usage_events_model", "llm_usage_events", ["model"])
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])
    op.create_index("ix_llm_usage_events_conversation_id", "llm_usage_events", ["conversation_id"])
    op.create_index("ix_llm_usage_user_created", "llm_usage_events", ["user_id", "created_at"])
    op.create_index("ix_llm_usage_model_created", "llm_usage_events", ["model", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_model_created", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_conversation_id", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_created_at", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_model", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_user_id", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
