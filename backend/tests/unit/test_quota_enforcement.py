"""
Unit tests for quota enforcement.

Tests the quota check functions that protect against exceeding limits.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.core.quota import (
    check_video_quota,
    check_message_quota,
    check_storage_quota,
    check_minutes_quota,
    QuotaExceededException,
)
from app.schemas import QuotaUsage


class TestVideoQuotaCheck:
    """Test video quota enforcement."""

    @pytest.mark.asyncio
    async def test_free_user_within_limit_passes(self, db, free_user):
        """Free user with <10 videos passes check."""
        from app.models import Video

        # Create 5 videos (under the 10 limit)
        for i in range(5):
            video = Video(
                user_id=free_user.id,
                youtube_id=f"vid_{i}",
                youtube_url=f"https://youtube.com/watch?v=vid_{i}",
                title=f"Test Video {i}",
                status="completed",
            )
            db.add(video)
        db.commit()

        # Should not raise
        await check_video_quota(free_user, db)

    @pytest.mark.asyncio
    async def test_free_user_at_limit_blocked(self, db, free_user):
        """Free user at 10 videos is blocked."""
        from app.models import Video

        # Create 10 videos (at the limit)
        for i in range(10):
            video = Video(
                user_id=free_user.id,
                youtube_id=f"vid_{i}",
                youtube_url=f"https://youtube.com/watch?v=vid_{i}",
                title=f"Test Video {i}",
                status="completed",
            )
            db.add(video)
        db.commit()

        with pytest.raises(QuotaExceededException) as exc:
            await check_video_quota(free_user, db)
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "quota_exceeded"
        assert exc.value.detail["quota_type"] == "video"

    @pytest.mark.asyncio
    async def test_pro_user_unlimited_videos(self, db, pro_user):
        """Pro user can have unlimited videos."""
        from app.models import Video

        # Create 100 videos
        for i in range(100):
            video = Video(
                user_id=pro_user.id,
                youtube_id=f"vid_{i}",
                youtube_url=f"https://youtube.com/watch?v=vid_{i}",
                title=f"Test Video {i}",
                status="completed",
            )
            db.add(video)
        db.commit()

        # Should not raise
        await check_video_quota(pro_user, db)

    @pytest.mark.asyncio
    async def test_admin_bypasses_quota(self, db, admin_user):
        """Admin users bypass all quota checks."""
        from app.models import Video

        # Create 100 videos
        for i in range(100):
            video = Video(
                user_id=admin_user.id,
                youtube_id=f"vid_{i}",
                youtube_url=f"https://youtube.com/watch?v=vid_{i}",
                title=f"Test Video {i}",
                status="completed",
            )
            db.add(video)
        db.commit()

        # Should not raise even though admin is on free tier
        await check_video_quota(admin_user, db)

    @pytest.mark.asyncio
    async def test_deleted_videos_not_counted(self, db, free_user):
        """Deleted videos should not count toward quota."""
        from app.models import Video

        # Create 10 videos, delete 5
        for i in range(10):
            video = Video(
                user_id=free_user.id,
                youtube_id=f"vid_{i}",
                youtube_url=f"https://youtube.com/watch?v=vid_{i}",
                title=f"Test Video {i}",
                status="completed",
                is_deleted=i < 5,  # First 5 are deleted
            )
            db.add(video)
        db.commit()

        # Should pass because only 5 active videos
        await check_video_quota(free_user, db)


class TestStorageQuotaCheck:
    """Test storage quota enforcement."""

    @pytest.mark.asyncio
    async def test_free_user_within_storage_limit(self, db, free_user):
        """Free user with <1GB storage passes."""
        # Mock storage usage at 500MB
        with patch("app.core.quota.subscription_service.get_user_quota") as mock_quota:
            mock_quota.return_value = QuotaUsage(
                tier="free",
                videos_used=5,
                videos_limit=10,
                videos_remaining=5,
                messages_used=50,
                messages_limit=200,
                messages_remaining=150,
                storage_used_mb=500,
                storage_limit_mb=1000,
                storage_remaining_mb=500,
                minutes_used=100,
                minutes_limit=1000,
                minutes_remaining=900,
            )

            with patch("app.core.quota.subscription_service.check_storage_quota", return_value=True):
                # Should not raise
                await check_storage_quota(free_user, 100, db)

    @pytest.mark.asyncio
    async def test_free_user_over_storage_blocked(self, db, free_user):
        """Free user exceeding 1GB storage is blocked."""
        with patch("app.core.quota.subscription_service.check_storage_quota", return_value=False):
            with patch("app.core.quota.subscription_service.get_user_quota") as mock_quota:
                mock_quota.return_value = QuotaUsage(
                    tier="free",
                    videos_used=5,
                    videos_limit=10,
                    videos_remaining=5,
                    messages_used=50,
                    messages_limit=200,
                    messages_remaining=150,
                    storage_used_mb=950,
                    storage_limit_mb=1000,
                    storage_remaining_mb=50,
                    minutes_used=100,
                    minutes_limit=1000,
                    minutes_remaining=900,
                )

                with pytest.raises(QuotaExceededException) as exc:
                    await check_storage_quota(free_user, 100, db)
                assert exc.value.detail["quota_type"] == "storage"

    @pytest.mark.asyncio
    async def test_admin_bypasses_storage_quota(self, db, admin_user):
        """Admin users bypass storage quota checks."""
        # Should not raise regardless of storage
        await check_storage_quota(admin_user, 10000, db)


class TestMessageQuotaCheck:
    """Test message quota enforcement."""

    @pytest.mark.asyncio
    async def test_free_user_within_message_limit(self, db, free_user):
        """Free user with <200 messages passes."""
        with patch("app.core.quota.subscription_service.check_message_quota", return_value=True):
            # Should not raise
            await check_message_quota(free_user, db)

    @pytest.mark.asyncio
    async def test_free_user_over_message_limit_blocked(self, db, free_user):
        """Free user at 200 messages is blocked."""
        with patch("app.core.quota.subscription_service.check_message_quota", return_value=False):
            with patch("app.core.quota.subscription_service.get_user_quota") as mock_quota:
                mock_quota.return_value = QuotaUsage(
                    tier="free",
                    videos_used=5,
                    videos_limit=10,
                    videos_remaining=5,
                    messages_used=200,
                    messages_limit=200,
                    messages_remaining=0,
                    storage_used_mb=500,
                    storage_limit_mb=1000,
                    storage_remaining_mb=500,
                    minutes_used=100,
                    minutes_limit=1000,
                    minutes_remaining=900,
                )

                with pytest.raises(QuotaExceededException) as exc:
                    await check_message_quota(free_user, db)
                assert exc.value.detail["quota_type"] == "message"

    @pytest.mark.asyncio
    async def test_pro_user_unlimited_messages(self, db, pro_user):
        """Pro user has unlimited messages."""
        with patch("app.core.quota.subscription_service.check_message_quota", return_value=True):
            # Should not raise
            await check_message_quota(pro_user, db)


class TestMinutesQuotaCheck:
    """Test video minutes quota enforcement."""

    @pytest.mark.asyncio
    async def test_free_user_within_minutes_limit(self, db, free_user):
        """Free user with <1000 minutes passes."""
        with patch("app.core.quota.subscription_service.check_minutes_quota", return_value=True):
            # Should not raise
            await check_minutes_quota(free_user, 30, db)

    @pytest.mark.asyncio
    async def test_free_user_over_minutes_limit_blocked(self, db, free_user):
        """Free user exceeding 1000 minutes is blocked."""
        with patch("app.core.quota.subscription_service.check_minutes_quota", return_value=False):
            with patch("app.core.quota.subscription_service.get_user_quota") as mock_quota:
                mock_quota.return_value = QuotaUsage(
                    tier="free",
                    videos_used=5,
                    videos_limit=10,
                    videos_remaining=5,
                    messages_used=50,
                    messages_limit=200,
                    messages_remaining=150,
                    storage_used_mb=500,
                    storage_limit_mb=1000,
                    storage_remaining_mb=500,
                    minutes_used=990,
                    minutes_limit=1000,
                    minutes_remaining=10,
                )

                with pytest.raises(QuotaExceededException) as exc:
                    await check_minutes_quota(free_user, 30, db)
                assert exc.value.detail["quota_type"] == "minutes"

    @pytest.mark.asyncio
    async def test_admin_bypasses_minutes_quota(self, db, admin_user):
        """Admin users bypass minutes quota checks."""
        # Should not raise regardless of minutes
        await check_minutes_quota(admin_user, 10000, db)


class TestQuotaExceededException:
    """Test QuotaExceededException structure."""

    def test_exception_has_correct_structure(self):
        """Exception contains expected fields."""
        exc = QuotaExceededException(
            quota_type="video",
            quota_usage={"tier": "free", "videos_used": 10, "videos_limit": 10},
        )

        assert exc.status_code == 403
        assert exc.detail["error"] == "quota_exceeded"
        assert exc.detail["quota_type"] == "video"
        assert "upgrade_url" in exc.detail
        assert "quota" in exc.detail
