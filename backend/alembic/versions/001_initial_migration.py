"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("subscription_tier", sa.String(length=50), nullable=False),
        sa.Column("subscription_status", sa.String(length=50), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(
        "ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=True
    )

    # Create videos table
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("youtube_id", sa.String(length=50), nullable=False),
        sa.Column("youtube_url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("channel_id", sa.String(length=100), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("upload_date", sa.DateTime(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("chapters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("audio_file_path", sa.String(length=500), nullable=True),
        sa.Column("audio_file_size_mb", sa.Float(), nullable=True),
        sa.Column("transcript_file_path", sa.String(length=500), nullable=True),
        sa.Column("transcription_model", sa.String(length=50), nullable=True),
        sa.Column("transcription_language", sa.String(length=10), nullable=True),
        sa.Column("transcription_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_videos_created_at"), "videos", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_videos_is_deleted"), "videos", ["is_deleted"], unique=False
    )
    op.create_index(op.f("ix_videos_status"), "videos", ["status"], unique=False)
    op.create_index(op.f("ix_videos_user_id"), "videos", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_videos_youtube_id"), "videos", ["youtube_id"], unique=False
    )

    # Create transcripts table
    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("segments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("has_speaker_labels", sa.String(), nullable=False),
        sa.Column("speaker_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transcripts_video_id"), "transcripts", ["video_id"], unique=True
    )

    # Create chunks table
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("start_timestamp", sa.Float(), nullable=False),
        sa.Column("end_timestamp", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("speakers", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("chapter_title", sa.String(length=255), nullable=True),
        sa.Column("chapter_index", sa.Integer(), nullable=True),
        sa.Column("chunk_summary", sa.Text(), nullable=True),
        sa.Column("chunk_title", sa.String(length=255), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("embedding_text", sa.Text(), nullable=True),
        sa.Column("is_indexed", sa.String(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chunk_timestamps",
        "chunks",
        ["start_timestamp", "end_timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_chunk_user_video", "chunks", ["user_id", "video_id"], unique=False
    )
    op.create_index(
        "idx_chunk_video_index", "chunks", ["video_id", "chunk_index"], unique=False
    )
    op.create_index(op.f("ix_chunks_user_id"), "chunks", ["user_id"], unique=False)
    op.create_index(op.f("ix_chunks_video_id"), "chunks", ["video_id"], unique=False)

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "selected_video_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_created_at"),
        "conversations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False
    )

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("response_time_seconds", sa.Float(), nullable=True),
        sa.Column("chunks_retrieved_count", sa.Integer(), nullable=True),
        sa.Column("chunks_used_count", sa.Integer(), nullable=True),
        sa.Column(
            "message_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False
    )

    # Create message_chunk_references table
    op.create_table(
        "message_chunk_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("was_used_in_response", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_chunk_references_chunk_id"),
        "message_chunk_references",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_chunk_references_message_id"),
        "message_chunk_references",
        ["message_id"],
        unique=False,
    )

    # Create usage_events table
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("cost_estimate", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("quota_category", sa.String(length=50), nullable=True),
        sa.Column(
            "quota_amount_used", sa.Numeric(precision=10, scale=2), nullable=True
        ),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_usage_events_event_timestamp"),
        "usage_events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_usage_events_event_type"), "usage_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_usage_events_user_id"), "usage_events", ["user_id"], unique=False
    )

    # Create user_quotas table
    op.create_table(
        "user_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_period_start", sa.DateTime(), nullable=False),
        sa.Column("quota_period_end", sa.DateTime(), nullable=False),
        sa.Column("videos_used", sa.Integer(), nullable=False),
        sa.Column("videos_limit", sa.Integer(), nullable=False),
        sa.Column("minutes_used", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("minutes_limit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("messages_used", sa.Integer(), nullable=False),
        sa.Column("messages_limit", sa.Integer(), nullable=False),
        sa.Column("storage_mb_used", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "storage_mb_limit", sa.Numeric(precision=10, scale=2), nullable=False
        ),
        sa.Column("embedding_tokens_used", sa.Integer(), nullable=False),
        sa.Column("embedding_tokens_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_quotas_user_id"), "user_quotas", ["user_id"], unique=True
    )

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("completed_steps", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_jobs_celery_task_id"), "jobs", ["celery_task_id"], unique=True
    )
    op.create_index(op.f("ix_jobs_created_at"), "jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_jobs_job_type"), "jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_jobs_video_id"), "jobs", ["video_id"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("jobs")
    op.drop_table("user_quotas")
    op.drop_table("usage_events")
    op.drop_table("message_chunk_references")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("chunks")
    op.drop_table("transcripts")
    op.drop_table("videos")
    op.drop_table("users")
