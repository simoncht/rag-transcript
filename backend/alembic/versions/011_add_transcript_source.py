"""Add transcript_source field to videos table

Tracks whether transcript came from YouTube captions or Whisper transcription.
This enables the caption-first optimization where we extract YouTube auto-captions
(1-4s) before falling back to Whisper download+transcription (15-90s).

Revision ID: 011_add_transcript_source
Revises: 010_remove_clerk_add_nextauth
Create Date: 2026-01-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # Add transcript_source column to track origin of transcript
    # Values: "captions" (from YouTube), "whisper" (from Whisper transcription)
    op.add_column(
        'videos',
        sa.Column('transcript_source', sa.String(length=50), nullable=True)
    )


def downgrade():
    op.drop_column('videos', 'transcript_source')
