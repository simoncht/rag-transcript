"""
API endpoints for notifications.

Endpoints:
- GET /notifications - List notifications
- GET /notifications/unread-count - Get unread count
- POST /notifications/mark-read - Mark as read
- POST /notifications/dismiss - Dismiss notifications
- GET/PUT /notifications/preferences - Manage preferences
- GET/PUT /notifications/settings - Global settings
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.nextauth import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationList,
    NotificationMarkReadRequest,
    NotificationDismissRequest,
    UnreadCountResponse,
    UserPreferencesResponse,
    UpdatePreferencesRequest,
    NotificationSettingsResponse,
    UpdateNotificationSettingsRequest,
)
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationList)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_read: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user."""
    service = NotificationService(db)

    notifications = service.get_notifications(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        include_read=include_read,
    )

    unread_count = service.get_unread_count(current_user.id)

    return NotificationList(
        notifications=[
            NotificationResponse(
                id=n.id,
                event_type_id=n.event_type_id,
                title=n.title,
                body=n.body,
                action_url=n.action_url,
                metadata=n.extra_data,
                created_at=n.created_at,
                read_at=n.read_at,
                dismissed_at=n.dismissed_at,
                is_read=n.is_read,
                is_dismissed=n.is_dismissed,
            )
            for n in notifications
        ],
        total=len(notifications),
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of unread notifications."""
    service = NotificationService(db)
    count = service.get_unread_count(current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/mark-read")
async def mark_notifications_read(
    mark_request: NotificationMarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark notifications as read."""
    service = NotificationService(db)

    notification_ids = mark_request.notification_ids if mark_request.notification_ids else None
    count = service.mark_read(current_user.id, notification_ids)

    return {"marked_count": count}


@router.post("/dismiss")
async def dismiss_notifications(
    dismiss_request: NotificationDismissRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss notifications (hide from list)."""
    if not dismiss_request.notification_ids:
        raise HTTPException(status_code=400, detail="No notification IDs provided")

    service = NotificationService(db)
    count = service.dismiss(current_user.id, dismiss_request.notification_ids)

    return {"dismissed_count": count}


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's notification preferences."""
    service = NotificationService(db)
    preferences = service.get_user_preferences(current_user.id)

    return UserPreferencesResponse(
        preferences=[
            {
                "event_type_id": p["event_type_id"],
                "display_name": p["display_name"],
                "category": p["category"],
                "is_enabled": p["is_enabled"],
                "enabled_channels": p["enabled_channels"],
                "frequency": p["frequency"],
            }
            for p in preferences
        ],
        available_channels=["in_app", "email"],
    )


@router.put("/preferences")
async def update_preferences(
    update_request: UpdatePreferencesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notification preferences."""
    service = NotificationService(db)

    for pref in update_request.preferences:
        service.update_preference(
            user_id=current_user.id,
            event_type_id=pref.event_type_id,
            is_enabled=pref.is_enabled,
            enabled_channels=pref.enabled_channels,
            frequency=pref.frequency,
        )

    return {"updated": len(update_request.preferences)}


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get global notification settings."""
    return NotificationSettingsResponse(
        email_digest_enabled=getattr(current_user, "email_digest_enabled", True) or True,
        email_digest_frequency=getattr(current_user, "email_digest_frequency", "daily") or "daily",
        recommendations_enabled=getattr(current_user, "recommendations_enabled", True) or True,
        timezone=getattr(current_user, "timezone", "UTC") or "UTC",
    )


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_settings(
    update_request: UpdateNotificationSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update global notification settings."""
    if update_request.email_digest_enabled is not None:
        current_user.email_digest_enabled = update_request.email_digest_enabled
    if update_request.email_digest_frequency is not None:
        current_user.email_digest_frequency = update_request.email_digest_frequency
    if update_request.recommendations_enabled is not None:
        current_user.recommendations_enabled = update_request.recommendations_enabled
    if update_request.timezone is not None:
        current_user.timezone = update_request.timezone

    db.commit()

    return NotificationSettingsResponse(
        email_digest_enabled=current_user.email_digest_enabled or True,
        email_digest_frequency=current_user.email_digest_frequency or "daily",
        recommendations_enabled=current_user.recommendations_enabled or True,
        timezone=current_user.timezone or "UTC",
    )
