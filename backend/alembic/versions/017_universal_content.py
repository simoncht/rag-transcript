"""Universal content support - add content_type and document fields to videos

Revision ID: 017
Revises: 016
Create Date: 2026-02-06

This migration adds:
- content_type column to videos (default 'youtube' for backward compat)
- source_metadata JSONB for type-specific fields
- original_filename, file_size_bytes, source_url, page_count for documents
- Makes youtube_id nullable for non-video content
- Adds content_type index for filtering
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # Add content_type discriminator (default 'youtube' for existing rows)
    # ========================================================================
    op.add_column(
        "videos",
        sa.Column(
            "content_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'youtube'"),
        ),
    )
    op.create_index("idx_videos_content_type", "videos", ["content_type"])

    # ========================================================================
    # Add document-specific columns
    # ========================================================================
    op.add_column(
        "videos",
        sa.Column("original_filename", sa.String(500), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("source_url", sa.String(2000), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column(
            "source_metadata",
            JSONB,
            nullable=True,
        ),
    )
    op.add_column(
        "videos",
        sa.Column("document_file_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("extracted_text_path", sa.String(500), nullable=True),
    )

    # ========================================================================
    # Make youtube_id nullable (documents don't have youtube_id)
    # ========================================================================
    op.alter_column(
        "videos",
        "youtube_id",
        existing_type=sa.String(50),
        nullable=True,
    )
    op.alter_column(
        "videos",
        "youtube_url",
        existing_type=sa.String(500),
        nullable=True,
    )

    # ========================================================================
    # Add content_type to chunks for filtering
    # ========================================================================
    op.add_column(
        "chunks",
        sa.Column(
            "content_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'youtube'"),
        ),
    )
    op.add_column(
        "chunks",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("section_heading", sa.String(500), nullable=True),
    )


def downgrade():
    # Remove chunk columns
    op.drop_column("chunks", "section_heading")
    op.drop_column("chunks", "page_number")
    op.drop_column("chunks", "content_type")

    # Restore youtube_id as NOT NULL
    op.alter_column(
        "videos",
        "youtube_id",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.alter_column(
        "videos",
        "youtube_url",
        existing_type=sa.String(500),
        nullable=False,
    )

    # Remove document columns
    op.drop_column("videos", "extracted_text_path")
    op.drop_column("videos", "document_file_path")
    op.drop_column("videos", "source_metadata")
    op.drop_column("videos", "page_count")
    op.drop_column("videos", "source_url")
    op.drop_column("videos", "file_size_bytes")
    op.drop_column("videos", "original_filename")

    # Remove content_type
    op.drop_index("idx_videos_content_type", table_name="videos")
    op.drop_column("videos", "content_type")
