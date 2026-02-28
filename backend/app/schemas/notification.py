"""
Pydantic schemas for notification-related API endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Single notification response."""

    id: UUID
    event_type_id: str
    title: str
    body: Optional[str] = None
    action_url: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    is_read: bool
    is_dismissed: bool

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    """List of notifications."""

    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    """Request to mark notifications as read."""

    notification_ids: List[UUID] = Field(
        default_factory=list,
        description="Specific notification IDs to mark read. Empty = mark all read.",
    )


class NotificationDismissRequest(BaseModel):
    """Request to dismiss notifications."""

    notification_ids: List[UUID]


class UnreadCountResponse(BaseModel):
    """Response with unread notification count."""

    unread_count: int


# =============================================================================
# Notification Preferences
# =============================================================================


class NotificationEventTypeInfo(BaseModel):
    """Info about a notification event type."""

    id: str
    category: str
    display_name: str
    description: Optional[str] = None
    default_channels: List[str]
    default_frequency: str
    is_active: bool

    class Config:
        from_attributes = True


class UserPreferenceResponse(BaseModel):
    """User's preference for a notification type."""

    event_type_id: str
    display_name: str
    category: str
    is_enabled: bool
    enabled_channels: List[str]  # Effective channels (pref or default)
    frequency: str  # Effective frequency (pref or default)


class UserPreferencesResponse(BaseModel):
    """All user notification preferences."""

    preferences: List[UserPreferenceResponse]
    available_channels: List[str]


class UpdatePreferenceRequest(BaseModel):
    """Request to update a notification preference."""

    event_type_id: str
    is_enabled: Optional[bool] = None
    enabled_channels: Optional[List[str]] = None
    frequency: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    """Request to update multiple preferences."""

    preferences: List[UpdatePreferenceRequest]


# =============================================================================
# Notification Settings
# =============================================================================


class NotificationSettingsResponse(BaseModel):
    """User's global notification settings."""

    email_digest_enabled: bool
    email_digest_frequency: str  # daily, weekly
    recommendations_enabled: bool
    timezone: str


class UpdateNotificationSettingsRequest(BaseModel):
    """Request to update notification settings."""

    email_digest_enabled: Optional[bool] = None
    email_digest_frequency: Optional[str] = Field(
        default=None, pattern="^(daily|weekly)$"
    )
    recommendations_enabled: Optional[bool] = None
    timezone: Optional[str] = None
