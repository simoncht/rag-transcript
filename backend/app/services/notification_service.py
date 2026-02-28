"""
Event-driven notification service with pluggable delivery channels.

Supports:
- Multiple notification channels (in_app, email, push, etc.)
- Per-user preference overrides
- Delivery tracking
- Digest batching
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.models.notification import (
    NotificationEventType,
    UserNotificationPreference,
    Notification,
    NotificationDelivery,
)

logger = logging.getLogger(__name__)


class DeliveryHandler(ABC):
    """Base class for notification delivery handlers."""

    @property
    @abstractmethod
    def channel(self) -> str:
        """Return the channel identifier (in_app, email, push, etc.)."""
        pass

    @property
    def is_immediate(self) -> bool:
        """Whether this channel delivers immediately or is batched."""
        return True

    @abstractmethod
    async def deliver(
        self,
        notification: Notification,
        user: User,
    ) -> bool:
        """
        Deliver a notification via this channel.

        Args:
            notification: Notification to deliver
            user: Target user

        Returns:
            True if delivery succeeded
        """
        pass


class InAppDeliveryHandler(DeliveryHandler):
    """In-app notification delivery (stored in database)."""

    @property
    def channel(self) -> str:
        return "in_app"

    async def deliver(self, notification: Notification, user: User) -> bool:
        # In-app notifications are already stored, nothing to do
        return True


class EmailDeliveryHandler(DeliveryHandler):
    """Email notification delivery (placeholder for email service)."""

    @property
    def channel(self) -> str:
        return "email"

    @property
    def is_immediate(self) -> bool:
        return False  # Batched in digest

    async def deliver(self, notification: Notification, user: User) -> bool:
        # TODO: Implement email sending via SMTP or service
        logger.info(f"Would send email to {user.email}: {notification.title}")
        return True


class NotificationService:
    """
    Event-driven notification system with pluggable delivery channels.

    Usage:
        service = NotificationService(db)

        # Emit a notification
        await service.emit(
            event_type_id="content.processing_complete",
            user_id=user.id,
            title="Video processed",
            body="Your video has finished processing",
            action_url="/videos/123",
        )

        # Get notifications
        notifications = service.get_notifications(user_id)
    """

    def __init__(self, db: Session):
        self.db = db
        self.delivery_handlers: Dict[str, DeliveryHandler] = {}

        # Register default handlers
        self.register_handler(InAppDeliveryHandler())
        self.register_handler(EmailDeliveryHandler())

    def register_handler(self, handler: DeliveryHandler) -> None:
        """Register a delivery handler for a channel."""
        self.delivery_handlers[handler.channel] = handler
        logger.debug(f"Registered notification handler: {handler.channel}")

    async def emit(
        self,
        event_type_id: str,
        user_id: UUID,
        title: str,
        body: Optional[str] = None,
        action_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Notification]:
        """
        Emit a notification event, respecting user preferences.

        Args:
            event_type_id: Type of event (e.g., 'content.discovered')
            user_id: Target user UUID
            title: Notification title
            body: Optional body text
            action_url: Optional URL for action button
            metadata: Optional event-specific metadata

        Returns:
            Created Notification or None if disabled
        """
        # Get event type
        event_type = self.db.query(NotificationEventType).get(event_type_id)
        if not event_type or not event_type.is_active:
            logger.warning(f"Inactive or unknown event type: {event_type_id}")
            return None

        # Get user preferences
        preference = (
            self.db.query(UserNotificationPreference)
            .filter(
                UserNotificationPreference.user_id == user_id,
                UserNotificationPreference.event_type_id == event_type_id,
            )
            .first()
        )

        # Check if disabled
        if preference and not preference.is_enabled:
            logger.debug(f"Notification disabled for user {user_id}: {event_type_id}")
            return None

        # Determine channels
        channels = (
            preference.enabled_channels
            if preference and preference.enabled_channels
            else event_type.default_channels
        )

        # Create notification record
        notification = Notification(
            user_id=user_id,
            event_type_id=event_type_id,
            title=title,
            body=body,
            action_url=action_url,
            extra_data=metadata or {},
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        logger.debug(f"Created notification {notification.id} for user {user_id}: {title}")

        # Queue delivery for each channel
        for channel in channels:
            if channel in self.delivery_handlers:
                delivery = NotificationDelivery(
                    notification_id=notification.id,
                    channel=channel,
                    status="pending",
                )
                self.db.add(delivery)

        self.db.commit()

        # Trigger immediate delivery
        await self._deliver_immediate(notification, channels)

        return notification

    async def _deliver_immediate(
        self,
        notification: Notification,
        channels: List[str],
    ) -> None:
        """Deliver to immediate channels (in_app, push)."""
        user = self.db.query(User).get(notification.user_id)
        if not user:
            return

        for channel in channels:
            if channel not in self.delivery_handlers:
                continue

            handler = self.delivery_handlers[channel]
            if not handler.is_immediate:
                continue

            # Get delivery record
            delivery = (
                self.db.query(NotificationDelivery)
                .filter(
                    NotificationDelivery.notification_id == notification.id,
                    NotificationDelivery.channel == channel,
                )
                .first()
            )

            if not delivery:
                continue

            try:
                delivery.attempted_at = datetime.utcnow()
                success = await handler.deliver(notification, user)

                if success:
                    delivery.status = "delivered"
                    delivery.delivered_at = datetime.utcnow()
                else:
                    delivery.status = "failed"
                    delivery.error_message = "Delivery failed"
            except Exception as e:
                logger.error(f"Notification delivery failed: {e}")
                delivery.status = "failed"
                delivery.error_message = str(e)

            self.db.commit()

    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
                Notification.dismissed_at.is_(None),
            )
            .count()
        )

    def get_notifications(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        include_read: bool = True,
    ) -> List[Notification]:
        """Get notifications for a user."""
        query = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.dismissed_at.is_(None),
            )
        )

        if not include_read:
            query = query.filter(Notification.read_at.is_(None))

        return (
            query.order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def mark_read(
        self,
        user_id: UUID,
        notification_ids: Optional[List[UUID]] = None,
    ) -> int:
        """
        Mark notifications as read.

        Args:
            user_id: User UUID
            notification_ids: Specific IDs to mark, or None for all

        Returns:
            Number of notifications marked
        """
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )

        if notification_ids:
            query = query.filter(Notification.id.in_(notification_ids))

        count = 0
        now = datetime.utcnow()
        for notification in query.all():
            notification.read_at = now
            count += 1

        self.db.commit()
        return count

    def dismiss(
        self,
        user_id: UUID,
        notification_ids: List[UUID],
    ) -> int:
        """
        Dismiss notifications (hide from list).

        Args:
            user_id: User UUID
            notification_ids: IDs to dismiss

        Returns:
            Number of notifications dismissed
        """
        count = 0
        now = datetime.utcnow()

        notifications = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.id.in_(notification_ids),
                Notification.dismissed_at.is_(None),
            )
            .all()
        )

        for notification in notifications:
            notification.dismissed_at = now
            count += 1

        self.db.commit()
        return count

    def get_user_preferences(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all notification preferences for a user.

        Returns merged preferences with defaults.
        """
        event_types = (
            self.db.query(NotificationEventType)
            .filter(NotificationEventType.is_active == True)  # noqa: E712
            .all()
        )

        preferences = (
            self.db.query(UserNotificationPreference)
            .filter(UserNotificationPreference.user_id == user_id)
            .all()
        )

        pref_map = {p.event_type_id: p for p in preferences}

        result = []
        for et in event_types:
            pref = pref_map.get(et.id)
            result.append({
                "event_type_id": et.id,
                "display_name": et.display_name,
                "category": et.category,
                "is_enabled": pref.is_enabled if pref else True,
                "enabled_channels": (
                    pref.enabled_channels if pref and pref.enabled_channels
                    else et.default_channels
                ),
                "frequency": (
                    pref.frequency if pref and pref.frequency
                    else et.default_frequency
                ),
            })

        return result

    def update_preference(
        self,
        user_id: UUID,
        event_type_id: str,
        is_enabled: Optional[bool] = None,
        enabled_channels: Optional[List[str]] = None,
        frequency: Optional[str] = None,
    ) -> None:
        """Update a user's notification preference."""
        pref = (
            self.db.query(UserNotificationPreference)
            .filter(
                UserNotificationPreference.user_id == user_id,
                UserNotificationPreference.event_type_id == event_type_id,
            )
            .first()
        )

        if not pref:
            pref = UserNotificationPreference(
                user_id=user_id,
                event_type_id=event_type_id,
            )
            self.db.add(pref)

        if is_enabled is not None:
            pref.is_enabled = is_enabled
        if enabled_channels is not None:
            pref.enabled_channels = enabled_channels
        if frequency is not None:
            pref.frequency = frequency

        self.db.commit()
