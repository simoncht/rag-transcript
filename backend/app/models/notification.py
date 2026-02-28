"""
Notification models for event-driven notifications.

Includes:
- NotificationEventType: Registry of notification types
- UserNotificationPreference: Per-user preference overrides
- Notification: Notification instances
- NotificationDelivery: Per-channel delivery tracking
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.db.base import Base


class NotificationEventType(Base):
    """
    Registry of notification event types.

    Add new event types by inserting rows, no schema changes needed.
    """

    __tablename__ = "notification_event_types"

    id = Column(String(100), primary_key=True)  # content.discovered, quota.warning, etc.
    category = Column(String(50), nullable=False)  # content, account, system
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    default_channels = Column(ARRAY(Text), default=["in_app"], nullable=False)
    default_frequency = Column(String(50), default="immediate", nullable=False)  # immediate, daily_digest
    is_active = Column(Boolean, default=True, nullable=False)
    template_data = Column(JSONB, default=dict, nullable=False)

    # Relationships
    preferences = relationship("UserNotificationPreference", back_populates="event_type")
    notifications = relationship("Notification", back_populates="event_type")

    def __repr__(self):
        return f"<NotificationEventType(id={self.id}, channels={self.default_channels})>"


class UserNotificationPreference(Base):
    """
    User preference overrides for notification event types.

    If no preference exists, defaults from NotificationEventType are used.
    """

    __tablename__ = "user_notification_preferences"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    event_type_id = Column(
        String(100),
        ForeignKey("notification_event_types.id"),
        primary_key=True,
    )

    is_enabled = Column(Boolean, default=True, nullable=False)
    enabled_channels = Column(ARRAY(Text), nullable=True)  # Override default_channels
    frequency = Column(String(50), nullable=True)  # Override default_frequency

    # Relationships
    user = relationship("User", backref="notification_preferences")
    event_type = relationship("NotificationEventType", back_populates="preferences")

    def __repr__(self):
        return f"<UserNotificationPreference(user_id={self.user_id}, event={self.event_type_id}, enabled={self.is_enabled})>"


class Notification(Base):
    """
    Notification instance for a user.

    Created when an event is emitted. Tracks read/dismissed status.
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type_id = Column(
        String(100),
        ForeignKey("notification_event_types.id"),
        nullable=False,
    )

    # Content
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    action_url = Column(String(500), nullable=True)
    extra_data = Column("metadata", JSONB, default=dict, nullable=False)
    # Example extra_data: {count: 3, source_id: "uuid", video_title: "..."}

    # Status
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="notifications")
    event_type = relationship("NotificationEventType", back_populates="notifications")
    deliveries = relationship(
        "NotificationDelivery",
        back_populates="notification",
        cascade="all, delete-orphan",
    )

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @property
    def is_dismissed(self) -> bool:
        return self.dismissed_at is not None

    def __repr__(self):
        return f"<Notification(id={self.id}, title={self.title[:30]}, read={self.is_read})>"


class NotificationDelivery(Base):
    """
    Delivery tracking for each notification channel.

    Tracks send attempts, success/failure, and external IDs for each channel.
    """

    __tablename__ = "notification_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel = Column(String(50), nullable=False)  # in_app, email, push, slack

    # Delivery status
    status = Column(String(50), default="pending", nullable=False)  # pending, sent, delivered, failed
    attempted_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    external_id = Column(String(255), nullable=True)  # Email message ID, push receipt, etc.

    # Relationships
    notification = relationship("Notification", back_populates="deliveries")

    def __repr__(self):
        return f"<NotificationDelivery(id={self.id}, channel={self.channel}, status={self.status})>"
