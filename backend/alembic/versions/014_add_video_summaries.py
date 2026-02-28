"""add video-level summaries for two-level retrieval

Revision ID: 014_add_video_summaries
Revises: 013_enhance_conversation_facts
Create Date: 2026-01-30

Adds video-level summary fields for hierarchical retrieval:
- summary: LLM-generated summary of the entire video (200-500 words)
- key_topics: Main themes/topics extracted from the video

This enables two-level retrieval (NotebookLM-style):
- Level 1: Video summaries for "summarize all" queries
- Level 0: Chunks for specific detail queries
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add summary column for video-level summary
    op.add_column(
        "videos",
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,  # NULL until generated after processing
        ),
    )

    # Add key_topics array for main themes
    op.add_column(
        "videos",
        sa.Column(
            "key_topics",
            ARRAY(sa.Text()),
            nullable=True,
        ),
    )

    # Add summary_generated_at timestamp
    op.add_column(
        "videos",
        sa.Column(
            "summary_generated_at",
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("videos", "summary_generated_at")
    op.drop_column("videos", "key_topics")
    op.drop_column("videos", "summary")
