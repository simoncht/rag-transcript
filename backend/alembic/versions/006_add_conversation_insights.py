"""add conversation insights cache table

Revision ID: 006_add_conversation_insights
Revises: 005_add_clerk_user_id
Create Date: 2025-12-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "006_add_conversation_insights"
down_revision: Union[str, None] = "005_add_clerk_user_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column(
            "extraction_prompt_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "graph_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "topic_chunks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("topics_count", sa.Integer(), nullable=False),
        sa.Column("total_chunks_analyzed", sa.Integer(), nullable=False),
        sa.Column("generation_time_seconds", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_insights_conversation_id",
        "conversation_insights",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_insights_user_id",
        "conversation_insights",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_insights_created_at",
        "conversation_insights",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_insights_created_at",
        table_name="conversation_insights",
    )
    op.drop_index(
        "ix_conversation_insights_user_id",
        table_name="conversation_insights",
    )
    op.drop_index(
        "ix_conversation_insights_conversation_id",
        table_name="conversation_insights",
    )
    op.drop_table("conversation_insights")

