"""
Usage tracking service for billing and quota enforcement.

Tracks:
- Video ingestion (count, minutes processed)
- Chat messages (count, tokens used)
- Storage usage (MB)
- Embedding generation (tokens, if using API)

Enforces quotas before operations and logs all billable events.
"""
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models import UsageEvent, UserQuota, User
from app.core.config import settings


class QuotaExceededError(Exception):
    """Raised when a user exceeds their quota."""
    def __init__(self, quota_type: str, used: float, limit: float):
        self.quota_type = quota_type
        self.used = used
        self.limit = limit
        super().__init__(f"{quota_type} quota exceeded: {used}/{limit}")


class UsageTracker:
    """
    Service for tracking usage and enforcing quotas.

    Provides methods to:
    - Check quotas before operations
    - Log usage events
    - Calculate costs
    - Get usage statistics
    """

    def __init__(self, db: Session):
        """
        Initialize usage tracker.

        Args:
            db: Database session
        """
        self.db = db

    def _get_or_create_quota(self, user_id: UUID) -> UserQuota:
        """
        Get or create user quota for current period.

        Args:
            user_id: User ID

        Returns:
            UserQuota object
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Try to get existing quota
        quota = self.db.query(UserQuota).filter(UserQuota.user_id == user_id).first()

        # Check if quota needs to be reset (new period)
        now = datetime.utcnow()
        if quota and quota.quota_period_end < now:
            # Reset quota for new period
            quota.quota_period_start = now
            quota.quota_period_end = now + timedelta(days=30)
            quota.videos_used = 0
            quota.minutes_used = Decimal(0)
            quota.messages_used = 0
            quota.storage_mb_used = Decimal(0)
            quota.embedding_tokens_used = 0
            self.db.commit()
        elif not quota:
            # Create new quota
            quota = self._create_initial_quota(user_id, user.subscription_tier)
            self.db.add(quota)
            self.db.commit()

        return quota

    def _create_initial_quota(self, user_id: UUID, tier: str) -> UserQuota:
        """
        Create initial quota based on subscription tier.

        Args:
            user_id: User ID
            tier: Subscription tier (free, pro, enterprise)

        Returns:
            UserQuota object
        """
        now = datetime.utcnow()

        # Define limits by tier
        tier_limits = {
            "free": {
                "videos": settings.free_tier_video_limit,
                "minutes": Decimal(settings.free_tier_minutes_limit),
                "messages": settings.free_tier_messages_limit,
                "storage_mb": Decimal(settings.free_tier_storage_mb_limit),
                "embedding_tokens": None,  # Unlimited for local embeddings
            },
            "pro": {
                "videos": 50,
                "minutes": Decimal(500),
                "messages": 999999,  # Unlimited
                "storage_mb": Decimal(10000),  # 10 GB
                "embedding_tokens": None,
            },
            "enterprise": {
                "videos": 999999,  # Unlimited
                "minutes": Decimal(999999),
                "messages": 999999,
                "storage_mb": Decimal(100000),  # 100 GB
                "embedding_tokens": None,
            }
        }

        limits = tier_limits.get(tier, tier_limits["free"])

        return UserQuota(
            user_id=user_id,
            quota_period_start=now,
            quota_period_end=now + timedelta(days=30),
            videos_used=0,
            videos_limit=limits["videos"],
            minutes_used=Decimal(0),
            minutes_limit=limits["minutes"],
            messages_used=0,
            messages_limit=limits["messages"],
            storage_mb_used=Decimal(0),
            storage_mb_limit=limits["storage_mb"],
            embedding_tokens_used=0,
            embedding_tokens_limit=limits["embedding_tokens"],
        )

    def check_quota(self, user_id: UUID, quota_type: str, amount: float = 1.0) -> bool:
        """
        Check if user has enough quota for an operation.

        Args:
            user_id: User ID
            quota_type: Type of quota (videos, minutes, messages, storage)
            amount: Amount needed

        Returns:
            True if quota available

        Raises:
            QuotaExceededError: If quota exceeded
        """
        quota = self._get_or_create_quota(user_id)

        if quota_type == "videos":
            if quota.videos_used + amount > quota.videos_limit:
                raise QuotaExceededError("videos", quota.videos_used, quota.videos_limit)
        elif quota_type == "minutes":
            if quota.minutes_used + Decimal(amount) > quota.minutes_limit:
                raise QuotaExceededError("minutes", float(quota.minutes_used), float(quota.minutes_limit))
        elif quota_type == "messages":
            if quota.messages_used + amount > quota.messages_limit:
                raise QuotaExceededError("messages", quota.messages_used, quota.messages_limit)
        elif quota_type == "storage":
            if quota.storage_mb_used + Decimal(amount) > quota.storage_mb_limit:
                raise QuotaExceededError("storage_mb", float(quota.storage_mb_used), float(quota.storage_mb_limit))

        return True

    def track_video_ingestion(
        self,
        user_id: UUID,
        video_id: UUID,
        duration_seconds: float,
        audio_size_mb: float
    ):
        """
        Track video ingestion event.

        Args:
            user_id: User ID
            video_id: Video ID
            duration_seconds: Video duration
            audio_size_mb: Audio file size in MB
        """
        minutes = duration_seconds / 60.0

        # Create usage event
        event = UsageEvent(
            user_id=user_id,
            event_type="video_ingested",
            metadata={
                "video_id": str(video_id),
                "duration_seconds": duration_seconds,
                "audio_size_mb": audio_size_mb,
            },
            quota_category="videos",
            quota_amount_used=Decimal(1),
        )
        self.db.add(event)

        # Update quota
        quota = self._get_or_create_quota(user_id)
        quota.videos_used += 1
        quota.minutes_used += Decimal(minutes)
        quota.storage_mb_used += Decimal(audio_size_mb)

        self.db.commit()

    def track_transcription(
        self,
        user_id: UUID,
        video_id: UUID,
        duration_seconds: float,
        chunk_count: int,
        model_used: str
    ):
        """
        Track transcription completion.

        Args:
            user_id: User ID
            video_id: Video ID
            duration_seconds: Transcription duration
            chunk_count: Number of chunks created
            model_used: Whisper model used
        """
        minutes = duration_seconds / 60.0

        event = UsageEvent(
            user_id=user_id,
            event_type="video_transcribed",
            metadata={
                "video_id": str(video_id),
                "duration_seconds": duration_seconds,
                "chunk_count": chunk_count,
                "model_used": model_used,
            },
            quota_category="minutes",
            quota_amount_used=Decimal(minutes),
        )
        self.db.add(event)
        self.db.commit()

    def track_chat_message(
        self,
        user_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        tokens_in: int,
        tokens_out: int,
        chunks_retrieved: int
    ):
        """
        Track chat message sent.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_id: Message ID
            tokens_in: Input tokens
            tokens_out: Output tokens
            chunks_retrieved: Number of chunks retrieved
        """
        event = UsageEvent(
            user_id=user_id,
            event_type="chat_message_sent",
            metadata={
                "conversation_id": str(conversation_id),
                "message_id": str(message_id),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "chunks_retrieved": chunks_retrieved,
            },
            quota_category="messages",
            quota_amount_used=Decimal(1),
        )
        self.db.add(event)

        # Update quota
        quota = self._get_or_create_quota(user_id)
        quota.messages_used += 1

        self.db.commit()

    def track_embedding_generation(
        self,
        user_id: UUID,
        chunk_count: int,
        model_used: str,
        embedding_dimensions: int
    ):
        """
        Track embedding generation (relevant for API-based embeddings).

        Args:
            user_id: User ID
            chunk_count: Number of chunks embedded
            model_used: Embedding model
            embedding_dimensions: Embedding dimensions
        """
        event = UsageEvent(
            user_id=user_id,
            event_type="embedding_generated",
            metadata={
                "chunk_count": chunk_count,
                "model_used": model_used,
                "embedding_dimensions": embedding_dimensions,
            },
        )
        self.db.add(event)
        self.db.commit()

    def get_usage_summary(self, user_id: UUID) -> Dict:
        """
        Get usage summary for a user.

        Args:
            user_id: User ID

        Returns:
            Dict with usage statistics
        """
        quota = self._get_or_create_quota(user_id)

        return {
            "period_start": quota.quota_period_start.isoformat(),
            "period_end": quota.quota_period_end.isoformat(),
            "videos": {
                "used": quota.videos_used,
                "limit": quota.videos_limit,
                "remaining": quota.remaining_quota("videos"),
                "percentage": (quota.videos_used / quota.videos_limit * 100) if quota.videos_limit > 0 else 0,
            },
            "minutes": {
                "used": float(quota.minutes_used),
                "limit": float(quota.minutes_limit),
                "remaining": quota.remaining_quota("minutes"),
                "percentage": (float(quota.minutes_used) / float(quota.minutes_limit) * 100) if quota.minutes_limit > 0 else 0,
            },
            "messages": {
                "used": quota.messages_used,
                "limit": quota.messages_limit,
                "remaining": quota.remaining_quota("messages"),
                "percentage": (quota.messages_used / quota.messages_limit * 100) if quota.messages_limit > 0 else 0,
            },
            "storage_mb": {
                "used": float(quota.storage_mb_used),
                "limit": float(quota.storage_mb_limit),
                "remaining": quota.remaining_quota("storage"),
                "percentage": (float(quota.storage_mb_used) / float(quota.storage_mb_limit) * 100) if quota.storage_mb_limit > 0 else 0,
            },
        }
