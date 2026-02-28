"""
Quota service using registry pattern for extensibility.

Provides unified quota management for all quota types (videos, minutes,
messages, storage, youtube_searches, etc.) with period-based tracking.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.models.quota import QuotaType, TierQuotaLimit, UserQuotaUsage

logger = logging.getLogger(__name__)


class QuotaInfo:
    """Information about a user's quota for a specific type."""

    def __init__(
        self,
        quota_type_id: str,
        display_name: str,
        unit: str,
        used: float,
        limit: float,
        is_unlimited: bool,
        is_admin_override: bool,
        period_start: Optional[datetime],
        period_end: Optional[datetime],
        warning_thresholds: List[int],
    ):
        self.quota_type_id = quota_type_id
        self.display_name = display_name
        self.unit = unit
        self.used = used
        self.limit = limit
        self.is_unlimited = is_unlimited
        self.is_admin_override = is_admin_override
        self.period_start = period_start
        self.period_end = period_end
        self.warning_thresholds = warning_thresholds

    @property
    def remaining(self) -> float:
        if self.is_unlimited:
            return float("inf")
        return max(0.0, self.limit - self.used)

    @property
    def percentage_used(self) -> float:
        if self.is_unlimited or self.limit <= 0:
            return 0.0
        return min(100.0, (self.used / self.limit) * 100)

    @property
    def warning_level(self) -> Optional[str]:
        """Get the current warning level based on percentage used."""
        if self.is_unlimited:
            return None
        pct = self.percentage_used
        if pct >= 100:
            return "exceeded"
        for threshold in reversed(self.warning_thresholds):
            if pct >= threshold:
                return str(threshold)
        return None

    def to_dict(self) -> Dict:
        return {
            "quota_type_id": self.quota_type_id,
            "display_name": self.display_name,
            "unit": self.unit,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining if not self.is_unlimited else -1,
            "is_unlimited": self.is_unlimited,
            "is_admin_override": self.is_admin_override,
            "percentage_used": self.percentage_used,
            "warning_level": self.warning_level,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


class QuotaCheckResult:
    """Result from checking if a quota action is allowed."""

    def __init__(
        self,
        allowed: bool,
        quota_type_id: str,
        warning_level: Optional[str] = None,
        message: Optional[str] = None,
        current_used: float = 0,
        limit: float = 0,
        would_use: float = 0,
    ):
        self.allowed = allowed
        self.quota_type_id = quota_type_id
        self.warning_level = warning_level
        self.message = message
        self.current_used = current_used
        self.limit = limit
        self.would_use = would_use


class QuotaService:
    """
    Unified quota management using registry pattern.

    Supports:
    - Multiple quota types (extensible via database)
    - Period-based quotas (daily, monthly)
    - Admin overrides
    - Warning thresholds
    """

    def __init__(self, db: Session):
        self.db = db

    def get_quota(self, user_id: UUID, quota_type_id: str) -> QuotaInfo:
        """
        Get current quota usage and limits for a user.

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier

        Returns:
            QuotaInfo with current usage and limits
        """
        quota_type = self.db.query(QuotaType).get(quota_type_id)
        if not quota_type:
            raise ValueError(f"Unknown quota type: {quota_type_id}")

        usage = self._get_or_create_usage(user_id, quota_type)

        return QuotaInfo(
            quota_type_id=quota_type_id,
            display_name=quota_type.display_name,
            unit=quota_type.unit,
            used=float(usage.used_value),
            limit=float(usage.limit_value),
            is_unlimited=usage.is_unlimited,
            is_admin_override=usage.is_admin_override,
            period_start=usage.period_start,
            period_end=usage.period_end,
            warning_thresholds=quota_type.warning_thresholds or [50, 80, 95],
        )

    def get_all_quotas(self, user_id: UUID) -> Dict[str, QuotaInfo]:
        """Get all active quotas for a user."""
        quota_types = (
            self.db.query(QuotaType)
            .filter(QuotaType.is_active == True)  # noqa: E712
            .all()
        )

        return {
            qt.id: self.get_quota(user_id, qt.id) for qt in quota_types
        }

    def check_quota(
        self,
        user_id: UUID,
        quota_type_id: str,
        amount: float = 1.0,
    ) -> QuotaCheckResult:
        """
        Check if user has quota available for an action.

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier
            amount: Amount to check (default 1)

        Returns:
            QuotaCheckResult with allowed flag and warning level
        """
        info = self.get_quota(user_id, quota_type_id)

        if info.is_unlimited:
            return QuotaCheckResult(
                allowed=True,
                quota_type_id=quota_type_id,
                warning_level=None,
                current_used=info.used,
                limit=info.limit,
                would_use=info.used + amount,
            )

        new_used = info.used + amount
        new_percentage = (new_used / info.limit * 100) if info.limit > 0 else 100

        if new_percentage > 100:
            return QuotaCheckResult(
                allowed=False,
                quota_type_id=quota_type_id,
                warning_level="exceeded",
                message=f"{info.display_name} quota exceeded",
                current_used=info.used,
                limit=info.limit,
                would_use=new_used,
            )

        # Check warning thresholds
        warning_level = None
        for threshold in reversed(info.warning_thresholds):
            if new_percentage >= threshold:
                warning_level = str(threshold)
                break

        message = None
        if warning_level:
            message = f"You're at {int(new_percentage)}% of your {info.display_name.lower()} quota"

        return QuotaCheckResult(
            allowed=True,
            quota_type_id=quota_type_id,
            warning_level=warning_level,
            message=message,
            current_used=info.used,
            limit=info.limit,
            would_use=new_used,
        )

    def increment(
        self,
        user_id: UUID,
        quota_type_id: str,
        amount: float = 1.0,
    ) -> QuotaInfo:
        """
        Increment quota usage.

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier
            amount: Amount to increment (default 1)

        Returns:
            Updated QuotaInfo
        """
        quota_type = self.db.query(QuotaType).get(quota_type_id)
        if not quota_type:
            raise ValueError(f"Unknown quota type: {quota_type_id}")

        usage = self._get_or_create_usage(user_id, quota_type)
        usage.used_value = Decimal(str(float(usage.used_value) + amount))
        usage.updated_at = datetime.utcnow()
        self.db.commit()

        logger.debug(
            f"Incremented quota {quota_type_id} for user {user_id}: "
            f"{float(usage.used_value) - amount} -> {float(usage.used_value)}"
        )

        return self.get_quota(user_id, quota_type_id)

    def decrement(
        self,
        user_id: UUID,
        quota_type_id: str,
        amount: float = 1.0,
    ) -> QuotaInfo:
        """
        Decrement quota usage (for refunds/deletions).

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier
            amount: Amount to decrement (default 1)

        Returns:
            Updated QuotaInfo
        """
        quota_type = self.db.query(QuotaType).get(quota_type_id)
        if not quota_type:
            raise ValueError(f"Unknown quota type: {quota_type_id}")

        usage = self._get_or_create_usage(user_id, quota_type)
        new_value = max(0, float(usage.used_value) - amount)
        usage.used_value = Decimal(str(new_value))
        usage.updated_at = datetime.utcnow()
        self.db.commit()

        return self.get_quota(user_id, quota_type_id)

    def set_admin_override(
        self,
        user_id: UUID,
        quota_type_id: str,
        new_limit: float,
    ) -> QuotaInfo:
        """
        Set an admin override for a user's quota limit.

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier
            new_limit: New limit value (-1 for unlimited)

        Returns:
            Updated QuotaInfo
        """
        quota_type = self.db.query(QuotaType).get(quota_type_id)
        if not quota_type:
            raise ValueError(f"Unknown quota type: {quota_type_id}")

        usage = self._get_or_create_usage(user_id, quota_type)
        usage.limit_value = Decimal(str(new_limit))
        usage.is_unlimited = new_limit < 0
        usage.is_admin_override = True
        usage.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"Admin override set for user {user_id}, quota {quota_type_id}: "
            f"limit={new_limit}, unlimited={new_limit < 0}"
        )

        return self.get_quota(user_id, quota_type_id)

    def reset_usage(self, user_id: UUID, quota_type_id: str) -> QuotaInfo:
        """
        Reset usage for a quota type (admin action).

        Args:
            user_id: User UUID
            quota_type_id: Quota type identifier

        Returns:
            Updated QuotaInfo
        """
        quota_type = self.db.query(QuotaType).get(quota_type_id)
        if not quota_type:
            raise ValueError(f"Unknown quota type: {quota_type_id}")

        usage = self._get_or_create_usage(user_id, quota_type)
        usage.used_value = Decimal("0")
        usage.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Reset quota {quota_type_id} for user {user_id}")

        return self.get_quota(user_id, quota_type_id)

    def refresh_limits_from_tier(self, user_id: UUID) -> None:
        """
        Refresh all quota limits from the user's current tier.

        Called when user tier changes (upgrade/downgrade).
        Does not affect admin overrides.
        """
        user = self.db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        quota_types = (
            self.db.query(QuotaType)
            .filter(QuotaType.is_active == True)  # noqa: E712
            .all()
        )

        for qt in quota_types:
            usage = self._get_or_create_usage(user_id, qt)

            # Skip admin overrides
            if usage.is_admin_override:
                continue

            # Get new limit from tier
            tier_limit = (
                self.db.query(TierQuotaLimit)
                .filter(
                    TierQuotaLimit.tier == user.subscription_tier,
                    TierQuotaLimit.quota_type_id == qt.id,
                )
                .first()
            )

            if tier_limit:
                usage.limit_value = tier_limit.limit_value
                usage.is_unlimited = tier_limit.is_unlimited
                usage.updated_at = datetime.utcnow()

        self.db.commit()
        logger.info(f"Refreshed quota limits for user {user_id} from tier {user.subscription_tier}")

    def _get_or_create_usage(
        self,
        user_id: UUID,
        quota_type: QuotaType,
    ) -> UserQuotaUsage:
        """Get or create usage record for current period."""
        period_start = self._get_period_start(quota_type.reset_period)

        usage = (
            self.db.query(UserQuotaUsage)
            .filter(
                UserQuotaUsage.user_id == user_id,
                UserQuotaUsage.quota_type_id == quota_type.id,
                UserQuotaUsage.period_start == period_start,
            )
            .first()
        )

        if usage:
            return usage

        # Get limit from tier
        user = self.db.query(User).get(user_id)
        tier = user.subscription_tier if user else "free"

        tier_limit = (
            self.db.query(TierQuotaLimit)
            .filter(
                TierQuotaLimit.tier == tier,
                TierQuotaLimit.quota_type_id == quota_type.id,
            )
            .first()
        )

        limit_value = Decimal(str(tier_limit.limit_value)) if tier_limit else Decimal("0")
        is_unlimited = tier_limit.is_unlimited if tier_limit else False

        usage = UserQuotaUsage(
            user_id=user_id,
            quota_type_id=quota_type.id,
            limit_value=limit_value,
            is_unlimited=is_unlimited,
            period_start=period_start,
            period_end=self._get_period_end(period_start, quota_type.reset_period),
        )
        self.db.add(usage)
        self.db.commit()
        self.db.refresh(usage)

        return usage

    def _get_period_start(self, reset_period: str) -> datetime:
        """Get the start of the current period."""
        now = datetime.utcnow()
        if reset_period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif reset_period == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif reset_period == "yearly":
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # "none" - use epoch as period start
            return datetime(1970, 1, 1)

    def _get_period_end(
        self,
        period_start: datetime,
        reset_period: str,
    ) -> Optional[datetime]:
        """Get the end of the current period."""
        if reset_period == "daily":
            return period_start + timedelta(days=1)
        elif reset_period == "monthly":
            # Next month, same day
            if period_start.month == 12:
                return period_start.replace(year=period_start.year + 1, month=1)
            return period_start.replace(month=period_start.month + 1)
        elif reset_period == "yearly":
            return period_start.replace(year=period_start.year + 1)
        else:  # "none"
            return None


# Convenience function for getting a quota service instance
def get_quota_service(db: Session) -> QuotaService:
    """Get a QuotaService instance."""
    return QuotaService(db)
