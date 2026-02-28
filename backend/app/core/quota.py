"""
Quota enforcement middleware and utilities.

Provides functions to check and enforce user quotas before allowing actions.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from app.services.subscription import subscription_service
import logging

logger = logging.getLogger(__name__)


class QuotaExceededException(HTTPException):
    """Exception raised when user quota is exceeded."""

    def __init__(self, quota_type: str, quota_usage: dict):
        """
        Initialize quota exceeded exception.

        Args:
            quota_type: Type of quota exceeded (video, message, storage, minutes)
            quota_usage: Current quota usage dictionary
        """
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "quota_exceeded",
                "quota_type": quota_type,
                "message": f"Your {quota_type} quota has been exceeded. Please upgrade your plan to continue.",
                "quota": quota_usage,
                "upgrade_url": "/account/subscription",
            },
        )


async def check_video_quota(user: User, db: Session) -> None:
    """
    Check if user can ingest another video.

    Args:
        user: User object
        db: Database session

    Raises:
        QuotaExceededException: If video quota exceeded
    """
    # Admin users bypass all quotas
    if user.is_superuser:
        logger.info(f"Admin user {user.id} bypassing video quota check")
        return

    if not subscription_service.check_video_quota(user.id, db):
        quota = subscription_service.get_user_quota(user.id, db)
        logger.warning(f"Video quota exceeded for user {user.id}: {quota.videos_used}/{quota.videos_limit}")

        raise QuotaExceededException(
            quota_type="video",
            quota_usage=quota.dict(),
        )


async def check_document_quota(user: User, db: Session) -> None:
    """
    Check if user can upload another document.

    Args:
        user: User object
        db: Database session

    Raises:
        QuotaExceededException: If document quota exceeded
    """
    # Admin users bypass all quotas
    if user.is_superuser:
        logger.info(f"Admin user {user.id} bypassing document quota check")
        return

    if not subscription_service.check_document_quota(user.id, db):
        quota = subscription_service.get_user_quota(user.id, db)
        logger.warning(f"Document quota exceeded for user {user.id}: {quota.documents_used}/{quota.documents_limit}")

        raise QuotaExceededException(
            quota_type="document",
            quota_usage=quota.dict(),
        )


async def check_message_quota(user: User, db: Session) -> None:
    """
    Check if user can send another message.

    Args:
        user: User object
        db: Database session

    Raises:
        QuotaExceededException: If message quota exceeded
    """
    # Admin users bypass all quotas
    if user.is_superuser:
        logger.info(f"Admin user {user.id} bypassing message quota check")
        return

    if not subscription_service.check_message_quota(user.id, db):
        quota = subscription_service.get_user_quota(user.id, db)
        logger.warning(f"Message quota exceeded for user {user.id}: {quota.messages_used}/{quota.messages_limit}")

        raise QuotaExceededException(
            quota_type="message",
            quota_usage=quota.dict(),
        )


async def check_storage_quota(user: User, file_size_mb: float, db: Session) -> None:
    """
    Check if user has enough storage quota for a file.

    Args:
        user: User object
        file_size_mb: Size of file in MB
        db: Database session

    Raises:
        QuotaExceededException: If storage quota exceeded
    """
    # Admin users bypass all quotas
    if user.is_superuser:
        logger.info(f"Admin user {user.id} bypassing storage quota check")
        return

    if not subscription_service.check_storage_quota(user.id, file_size_mb, db):
        quota = subscription_service.get_user_quota(user.id, db)
        logger.warning(
            f"Storage quota exceeded for user {user.id}: "
            f"{quota.storage_used_mb:.2f}MB/{quota.storage_limit_mb}MB (requesting {file_size_mb:.2f}MB)"
        )

        raise QuotaExceededException(
            quota_type="storage",
            quota_usage=quota.dict(),
        )


async def check_minutes_quota(user: User, duration_minutes: int, db: Session) -> None:
    """
    Check if user has enough minutes quota for a video.

    Args:
        user: User object
        duration_minutes: Video duration in minutes
        db: Database session

    Raises:
        QuotaExceededException: If minutes quota exceeded
    """
    # Admin users bypass all quotas
    if user.is_superuser:
        logger.info(f"Admin user {user.id} bypassing minutes quota check")
        return

    if not subscription_service.check_minutes_quota(user.id, duration_minutes, db):
        quota = subscription_service.get_user_quota(user.id, db)
        logger.warning(
            f"Minutes quota exceeded for user {user.id}: "
            f"{quota.minutes_used}/{quota.minutes_limit} (requesting {duration_minutes} minutes)"
        )

        raise QuotaExceededException(
            quota_type="minutes",
            quota_usage=quota.dict(),
        )


