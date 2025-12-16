"""
Admin-specific Pydantic schemas for API request/response validation.

These schemas are used exclusively for admin endpoints and include
system-wide metrics, user management, and cost tracking data.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# User Management Schemas

class UserSummary(BaseModel):
    """Summary information for a user in admin list view."""

    id: UUID
    email: str
    full_name: Optional[str] = None
    clerk_user_id: Optional[str] = None
    subscription_tier: str
    subscription_status: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    # Aggregated metrics
    video_count: int = 0
    collection_count: int = 0
    conversation_count: int = 0
    total_messages: int = 0
    total_tokens_used: int = 0
    storage_mb_used: float = 0.0

    # Engagement metrics
    last_active_at: Optional[datetime] = None
    days_since_signup: int = 0
    days_since_last_active: Optional[int] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated response for user list."""

    total: int
    page: int
    page_size: int
    users: List[UserSummary]


class UserDetailMetrics(BaseModel):
    """Detailed metrics for a single user."""

    # Video metrics
    videos_total: int = 0
    videos_completed: int = 0
    videos_processing: int = 0
    videos_failed: int = 0
    total_transcription_minutes: float = 0.0

    # Collection metrics
    collections_total: int = 0
    collections_with_videos: int = 0

    # Conversation metrics
    conversations_total: int = 0
    conversations_active: int = 0
    messages_sent: int = 0
    messages_received: int = 0

    # Token metrics
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # Storage metrics
    storage_mb: float = 0.0
    audio_mb: float = 0.0
    transcript_mb: float = 0.0

    # Quota usage
    quota_videos_used: int = 0
    quota_videos_limit: int = 0
    quota_minutes_used: float = 0.0
    quota_minutes_limit: float = 0.0
    quota_messages_used: int = 0
    quota_messages_limit: int = 0
    quota_storage_used: float = 0.0
    quota_storage_limit: float = 0.0


class UserCostBreakdown(BaseModel):
    """Cost breakdown for a user."""

    # API costs
    transcription_cost: float = 0.0
    embedding_cost: float = 0.0
    llm_cost: float = 0.0
    storage_cost: float = 0.0

    # Total
    total_cost: float = 0.0

    # Revenue
    subscription_revenue: float = 0.0

    # Net
    net_profit: float = 0.0
    profit_margin: float = 0.0

    # Usage counts for cost calculation
    transcription_minutes: float = 0.0
    embedding_tokens: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    storage_gb: float = 0.0


class UserDetail(BaseModel):
    """Full user detail for admin view."""

    # Basic info
    id: UUID
    email: str
    full_name: Optional[str] = None
    clerk_user_id: Optional[str] = None

    # Account status
    subscription_tier: str
    subscription_status: str
    is_active: bool
    is_superuser: bool
    stripe_customer_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None

    # Metrics
    metrics: UserDetailMetrics

    # Cost breakdown
    costs: UserCostBreakdown

    # Admin notes (if implemented)
    admin_notes_count: int = 0

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Request to update user account settings (admin only)."""

    subscription_tier: Optional[str] = Field(None, description="Update subscription tier")
    subscription_status: Optional[str] = Field(None, description="Update subscription status")
    is_active: Optional[bool] = Field(None, description="Activate or deactivate account")
    is_superuser: Optional[bool] = Field(None, description="Grant or revoke admin privileges")


class QuotaOverrideRequest(BaseModel):
    """Request to manually override user quotas."""

    videos_limit: Optional[int] = None
    minutes_limit: Optional[float] = None
    messages_limit: Optional[int] = None
    storage_mb_limit: Optional[float] = None


class AdminNoteCreateRequest(BaseModel):
    """Request to add an admin note to a user."""

    note: str = Field(..., min_length=1, max_length=1000)


class AdminNote(BaseModel):
    """Admin note attached to a user."""

    id: UUID
    user_id: UUID
    admin_id: UUID
    admin_email: str
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


# Dashboard Schemas

class SystemStats(BaseModel):
    """System-wide statistics for admin dashboard."""

    # User stats
    total_users: int = 0
    active_users: int = 0
    new_users_this_month: int = 0
    churned_users_this_month: int = 0

    # Subscription breakdown
    users_free: int = 0
    users_starter: int = 0
    users_pro: int = 0
    users_business: int = 0
    users_enterprise: int = 0

    # Content stats
    total_videos: int = 0
    total_videos_completed: int = 0
    total_videos_processing: int = 0
    total_videos_failed: int = 0

    total_conversations: int = 0
    total_messages: int = 0
    total_collections: int = 0

    # Usage stats
    total_transcription_minutes: float = 0.0
    total_tokens_used: int = 0
    total_storage_gb: float = 0.0

    # Cost stats
    total_cost_this_month: float = 0.0
    total_revenue_this_month: float = 0.0
    net_profit_this_month: float = 0.0


class UserEngagementStats(BaseModel):
    """User engagement health breakdown."""

    active_users: int = 0  # Active in last 7 days
    at_risk_users: int = 0  # Inactive 14-30 days
    churning_users: int = 0  # Inactive 30+ days
    dormant_users: int = 0  # Inactive 90+ days


class DashboardResponse(BaseModel):
    """Admin dashboard response with system overview."""

    system_stats: SystemStats
    engagement_stats: UserEngagementStats
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# Activity Log Schemas

class UserActivityLog(BaseModel):
    """User activity log entry."""

    id: UUID
    user_id: UUID
    event_type: str
    event_metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True


class UserActivityResponse(BaseModel):
    """Response with user activity logs."""

    total: int
    logs: List[UserActivityLog]


# Error Log Schemas

class UserErrorLog(BaseModel):
    """Error log for a user."""

    timestamp: datetime
    error_type: str
    error_message: str
    video_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None


class UserErrorResponse(BaseModel):
    """Response with user error logs."""

    total: int
    errors: List[UserErrorLog]


# Abuse Detection Schemas

class AbuseAlert(BaseModel):
    """Abuse detection alert."""

    user_id: UUID
    user_email: str
    alert_type: str
    severity: str  # low, medium, high, critical
    description: str
    detected_at: datetime
    is_resolved: bool = False


class AbuseAlertResponse(BaseModel):
    """Response with abuse alerts."""

    total: int
    alerts: List[AbuseAlert]
