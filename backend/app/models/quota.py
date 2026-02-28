"""
Quota models using registry pattern for extensibility.

Includes:
- QuotaType: Registry of quota types (add new quotas without schema changes)
- TierQuotaLimit: Default limits per tier
- UserQuotaUsage: Per-user quota tracking with period support
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Numeric,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.db.base import Base


class QuotaType(Base):
    """
    Registry of quota types.

    Add new quota types by inserting rows, no schema changes needed.
    """

    __tablename__ = "quota_types"

    id = Column(String(50), primary_key=True)  # videos, minutes, messages, storage, youtube_searches
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=False)  # count, minutes, mb, api_calls
    reset_period = Column(String(50), nullable=False)  # none, daily, monthly, yearly
    warning_thresholds = Column(ARRAY(Integer), default=[50, 80, 95], nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tier_limits = relationship("TierQuotaLimit", back_populates="quota_type")
    user_usage = relationship("UserQuotaUsage", back_populates="quota_type")

    def __repr__(self):
        return f"<QuotaType(id={self.id}, unit={self.unit}, reset={self.reset_period})>"


class TierQuotaLimit(Base):
    """
    Default quota limits per subscription tier.

    Primary key is (tier, quota_type_id) composite.
    """

    __tablename__ = "tier_quota_limits"

    tier = Column(String(50), primary_key=True)  # free, pro, enterprise
    quota_type_id = Column(
        String(50),
        ForeignKey("quota_types.id"),
        primary_key=True,
    )
    limit_value = Column(Numeric, nullable=False)  # -1 for unlimited
    is_unlimited = Column(Boolean, default=False, nullable=False)

    # Relationships
    quota_type = relationship("QuotaType", back_populates="tier_limits")

    def __repr__(self):
        limit_str = "unlimited" if self.is_unlimited else str(self.limit_value)
        return f"<TierQuotaLimit(tier={self.tier}, type={self.quota_type_id}, limit={limit_str})>"


class UserQuotaUsage(Base):
    """
    Per-user quota usage tracking.

    Supports period-based quotas (daily, monthly) with automatic reset.
    """

    __tablename__ = "user_quota_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quota_type_id = Column(
        String(50),
        ForeignKey("quota_types.id"),
        nullable=False,
    )

    # Current limits (from tier or admin override)
    limit_value = Column(Numeric, nullable=False)
    is_unlimited = Column(Boolean, default=False, nullable=False)
    is_admin_override = Column(Boolean, default=False, nullable=False)

    # Current usage
    used_value = Column(Numeric, default=Decimal("0"), nullable=False)

    # Period tracking
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="quota_usage")
    quota_type = relationship("QuotaType", back_populates="user_usage")

    @property
    def remaining(self) -> Decimal:
        """Calculate remaining quota."""
        if self.is_unlimited:
            return Decimal("-1")
        return max(Decimal("0"), Decimal(str(self.limit_value)) - Decimal(str(self.used_value)))

    @property
    def percentage_used(self) -> float:
        """Calculate percentage of quota used."""
        if self.is_unlimited or self.limit_value == 0:
            return 0.0
        return min(100.0, float(self.used_value) / float(self.limit_value) * 100)

    def __repr__(self):
        return f"<UserQuotaUsage(user_id={self.user_id}, type={self.quota_type_id}, used={self.used_value}/{self.limit_value})>"
