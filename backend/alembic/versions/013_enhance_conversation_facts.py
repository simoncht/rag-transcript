"""enhance conversation facts with importance scoring

Revision ID: 013_enhance_conversation_facts
Revises: 012_add_llm_usage_tracking
Create Date: 2026-01-27

Adds multi-factor scoring fields based on OpenAI/Anthropic memory best practices:
- importance: LLM-rated significance (0.0-1.0)
- category: Fact type for scope separation (identity, topic, preference, session)
- last_accessed: For retrieval strength calculation
- access_count: How often this fact has been recalled
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add importance column with default 0.5 (mid-range)
    op.add_column(
        "conversation_facts",
        sa.Column(
            "importance",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.5"),
        ),
    )

    # Add category column for scope separation
    op.add_column(
        "conversation_facts",
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'topic'"),
        ),
    )

    # Add last_accessed for retrieval strength
    op.add_column(
        "conversation_facts",
        sa.Column(
            "last_accessed",
            sa.DateTime(),
            nullable=True,  # NULL = never accessed
        ),
    )

    # Add access_count for frequency factor
    op.add_column(
        "conversation_facts",
        sa.Column(
            "access_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Create index for importance-based queries
    op.create_index(
        "ix_conversation_facts_importance",
        "conversation_facts",
        ["conversation_id", "importance"],
        unique=False,
    )

    # Create index for category-based queries
    op.create_index(
        "ix_conversation_facts_category",
        "conversation_facts",
        ["conversation_id", "category"],
        unique=False,
    )

    # Composite index for multi-factor scoring queries
    op.create_index(
        "ix_conversation_facts_scoring",
        "conversation_facts",
        ["conversation_id", "importance", "category", "source_turn"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_facts_scoring", table_name="conversation_facts")
    op.drop_index("ix_conversation_facts_category", table_name="conversation_facts")
    op.drop_index("ix_conversation_facts_importance", table_name="conversation_facts")
    op.drop_column("conversation_facts", "access_count")
    op.drop_column("conversation_facts", "last_accessed")
    op.drop_column("conversation_facts", "category")
    op.drop_column("conversation_facts", "importance")
