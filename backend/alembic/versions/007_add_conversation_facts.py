"""add conversation facts for long-distance recall

Revision ID: 007_add_conversation_facts
Revises: 006_add_conversation_insights
Create Date: 2026-01-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "007_add_conversation_facts"
down_revision: Union[str, None] = "006_add_conversation_insights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_facts",
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
        sa.Column("fact_key", sa.String(length=200), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("source_turn", sa.Integer(), nullable=False),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "fact_key",
            name="unique_conversation_fact_key",
        ),
    )
    op.create_index(
        "ix_conversation_facts_conversation_id",
        "conversation_facts",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_facts_user_id",
        "conversation_facts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_facts_created_at",
        "conversation_facts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_facts_key",
        "conversation_facts",
        ["conversation_id", "fact_key"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_facts_confidence",
        "conversation_facts",
        ["conversation_id", "confidence_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_facts_confidence",
        table_name="conversation_facts",
    )
    op.drop_index(
        "ix_conversation_facts_key",
        table_name="conversation_facts",
    )
    op.drop_index(
        "ix_conversation_facts_created_at",
        table_name="conversation_facts",
    )
    op.drop_index(
        "ix_conversation_facts_user_id",
        table_name="conversation_facts",
    )
    op.drop_index(
        "ix_conversation_facts_conversation_id",
        table_name="conversation_facts",
    )
    op.drop_table("conversation_facts")
