"""Add call_type and content_id to llm_usage_events

Revision ID: 022
Revises: 021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_usage_events",
        sa.Column("call_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "llm_usage_events",
        sa.Column("content_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_llm_usage_call_type", "llm_usage_events", ["call_type"])
    op.create_index("ix_llm_usage_content_id", "llm_usage_events", ["content_id"])

    # Backfill existing rows as 'chat'
    op.execute("UPDATE llm_usage_events SET call_type = 'chat' WHERE call_type IS NULL")


def downgrade() -> None:
    op.drop_index("ix_llm_usage_content_id", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_call_type", table_name="llm_usage_events")
    op.drop_column("llm_usage_events", "content_id")
    op.drop_column("llm_usage_events", "call_type")
