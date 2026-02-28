"""
Pydantic schemas for quota-related API endpoints.

Uses the registry pattern where quota types are defined in the database,
not hardcoded in the schema.
"""
from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, Field


class QuotaTypeInfo(BaseModel):
    """Information about a quota type."""

    id: str
    display_name: str
    description: Optional[str] = None
    unit: str
    reset_period: str  # none, daily, monthly
    warning_thresholds: List[int]
    is_active: bool

    class Config:
        from_attributes = True


class QuotaUsageInfo(BaseModel):
    """Current usage for a specific quota type."""

    quota_type_id: str
    display_name: str
    unit: str
    used: float
    limit: float
    remaining: float
    is_unlimited: bool
    percentage_used: float
    warning_level: Optional[str] = None  # None, "50", "80", "95", "exceeded"
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    is_admin_override: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "quota_type_id": "youtube_searches",
                "display_name": "YouTube Searches",
                "unit": "count",
                "used": 5,
                "limit": 10,
                "remaining": 5,
                "is_unlimited": False,
                "percentage_used": 50.0,
                "warning_level": "50",
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-01-02T00:00:00Z",
            }
        }


class QuotaCheckResult(BaseModel):
    """Result from checking if a quota action is allowed."""

    allowed: bool
    quota_type_id: str
    warning_level: Optional[str] = None
    message: Optional[str] = None
    current_used: float
    limit: float
    would_use: float

    class Config:
        json_schema_extra = {
            "example": {
                "allowed": True,
                "quota_type_id": "youtube_searches",
                "warning_level": "80",
                "message": "You're at 80% of your daily search quota",
                "current_used": 8,
                "limit": 10,
                "would_use": 9,
            }
        }


class AllQuotasResponse(BaseModel):
    """Response with all quota usage for a user."""

    quotas: Dict[str, QuotaUsageInfo]
    tier: str
    has_warnings: bool
    exceeded_quotas: List[str]


class TierQuotaLimitsResponse(BaseModel):
    """Default quota limits for each tier."""

    tier: str
    limits: Dict[str, float]  # quota_type_id -> limit (-1 for unlimited)


class AdminQuotaOverride(BaseModel):
    """Admin request to override a user's quota limit."""

    user_id: UUID
    quota_type_id: str
    new_limit: float = Field(..., description="New limit value, -1 for unlimited")
    reason: Optional[str] = None


class QuotaIncrementRequest(BaseModel):
    """Request to increment quota usage (internal use)."""

    quota_type_id: str
    amount: float = Field(default=1.0, ge=0)


class QuotaResetRequest(BaseModel):
    """Admin request to reset a user's quota usage."""

    user_id: UUID
    quota_type_id: str
    reason: Optional[str] = None
