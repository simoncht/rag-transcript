"""
Usage tracking models for billing and quotas.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class UsageEvent(Base):
    """
    Usage event model for tracking billable actions.

    Records every significant action (video processing, chat messages, embeddings)
    for usage analytics and quota enforcement.
    """

    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event classification
    event_type = Column(String(50), nullable=False, index=True)
    # Event types: video_ingested, video_transcribed, chat_message_sent, embedding_generated, storage_used

    # Event metadata (flexible JSON for different event types)
    event_metadata = Column(JSONB, nullable=False, default={})
    # Examples:
    # - video_transcribed: {video_id, duration_seconds, audio_size_mb, chunk_count, model_used}
    # - chat_message_sent: {conversation_id, message_id, tokens_in, tokens_out, chunks_retrieved}
    # - embedding_generated: {chunk_count, model_used, embedding_dimensions}

    # Cost estimation (for tracking COGS)
    cost_estimate = Column(Numeric(10, 6), nullable=True)  # Estimated cost in USD

    # Quota tracking
    quota_category = Column(
        String(50), nullable=True
    )  # videos, minutes, messages, storage
    quota_amount_used = Column(
        Numeric(10, 2), nullable=True
    )  # How much quota this consumed

    # Timestamps
    event_timestamp = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    user = relationship("User", back_populates="usage_events")

    def __repr__(self):
        return f"<UsageEvent(id={self.id}, type={self.event_type}, user_id={self.user_id})>"


class UserQuota(Base):
    """
    User quota tracking for subscription limits.

    Tracks usage against limits for each quota period (typically monthly).
    """

    __tablename__ = "user_quotas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Quota period
    quota_period_start = Column(DateTime, nullable=False)
    quota_period_end = Column(DateTime, nullable=False)

    # Video quotas
    videos_used = Column(Integer, default=0, nullable=False)
    videos_limit = Column(Integer, nullable=False)  # Based on subscription tier

    # Minutes quotas (transcription)
    minutes_used = Column(Numeric(10, 2), default=0, nullable=False)
    minutes_limit = Column(Numeric(10, 2), nullable=False)

    # Message quotas (chat)
    messages_used = Column(Integer, default=0, nullable=False)
    messages_limit = Column(Integer, nullable=False)

    # Storage quotas
    storage_mb_used = Column(Numeric(10, 2), default=0, nullable=False)
    storage_mb_limit = Column(Numeric(10, 2), nullable=False)

    # Embedding token quotas (for API-based embeddings)
    embedding_tokens_used = Column(Integer, default=0, nullable=False)
    embedding_tokens_limit = Column(Integer, nullable=True)  # Null = unlimited

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<UserQuota(user_id={self.user_id}, videos={self.videos_used}/{self.videos_limit})>"

    def is_quota_exceeded(self, quota_type: str) -> bool:
        """Check if a specific quota is exceeded."""
        if quota_type == "videos":
            return self.videos_used >= self.videos_limit
        elif quota_type == "minutes":
            return self.minutes_used >= self.minutes_limit
        elif quota_type == "messages":
            return self.messages_used >= self.messages_limit
        elif quota_type == "storage":
            return self.storage_mb_used >= self.storage_mb_limit
        elif quota_type == "embedding_tokens":
            if self.embedding_tokens_limit is None:
                return False
            return self.embedding_tokens_used >= self.embedding_tokens_limit
        return False

    def remaining_quota(self, quota_type: str) -> float:
        """Get remaining quota for a specific type."""
        if quota_type == "videos":
            return max(0, self.videos_limit - self.videos_used)
        elif quota_type == "minutes":
            return max(0, float(self.minutes_limit - self.minutes_used))
        elif quota_type == "messages":
            return max(0, self.messages_limit - self.messages_used)
        elif quota_type == "storage":
            return max(0, float(self.storage_mb_limit - self.storage_mb_used))
        elif quota_type == "embedding_tokens":
            if self.embedding_tokens_limit is None:
                return float("inf")
            return max(0, self.embedding_tokens_limit - self.embedding_tokens_used)
        return 0
