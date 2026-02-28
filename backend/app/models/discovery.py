"""
Discovery models for content discovery and subscriptions.

Includes:
- DiscoverySource: User subscriptions to channels, topics, feeds
- DiscoveredContent: Content pending user action (import/dismiss)
- UserInterestProfile: Aggregated user interests for recommendations
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class DiscoverySource(Base):
    """
    User subscription to a content source (channel, topic, feed).

    Supports explicit subscriptions (user-initiated) and implicit follows
    (auto-detected from import patterns).
    """

    __tablename__ = "discovery_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source identification
    source_type = Column(String(50), nullable=False)  # youtube_channel, youtube_topic, rss_feed
    source_identifier = Column(String(500), nullable=False)  # channel_id, topic name, feed URL
    display_name = Column(String(255), nullable=True)
    display_image_url = Column(String(500), nullable=True)

    # Configuration
    config = Column(JSONB, default=dict, nullable=False)
    # Example config: {"auto_import": false, "notify": true, "priority": "normal"}

    # Classification
    is_explicit = Column(Boolean, default=True, nullable=False)  # User explicitly subscribed
    is_active = Column(Boolean, default=True, nullable=False)

    # Tracking
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    check_frequency_hours = Column(Integer, default=24, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="discovery_sources")
    discovered_content = relationship(
        "DiscoveredContent",
        back_populates="discovery_source",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<DiscoverySource(id={self.id}, type={self.source_type}, name={self.display_name})>"


class DiscoveredContent(Base):
    """
    Content discovered from a source, pending user action.

    Status lifecycle: pending -> imported | dismissed | expired
    """

    __tablename__ = "discovered_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    discovery_source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("discovery_sources.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Content preview (not yet fully imported)
    content_type = Column(String(50), nullable=False)  # video, audio, document
    source_type = Column(String(50), nullable=False)  # youtube, rss, recommendation
    source_identifier = Column(String(500), nullable=False)  # youtube_id, guid, URL

    # Display data
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    preview_metadata = Column(JSONB, default=dict, nullable=False)
    # Example: {duration: 3600, channel_name: "TED", published_at: "2024-01-15", view_count: 100000}

    # Discovery context
    discovery_reason = Column(String(100), nullable=True)  # subscription, topic_match, channel_follow
    discovery_context = Column(JSONB, default=dict, nullable=False)
    # Example: {matched_topic: "public speaking", score: 0.85}

    # Status
    status = Column(String(50), default="pending", nullable=False)  # pending, imported, dismissed, expired
    discovered_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    actioned_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="discovered_content")
    discovery_source = relationship("DiscoverySource", back_populates="discovered_content")

    def __repr__(self):
        return f"<DiscoveredContent(id={self.id}, title={self.title[:30]}, status={self.status})>"


class UserInterestProfile(Base):
    """
    Aggregated user interests for powering recommendations.

    Updated incrementally as user imports content.
    """

    __tablename__ = "user_interest_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Aggregated interests (JSONB arrays with scores)
    topics = Column(JSONB, default=list, nullable=False)
    # Example: [{topic: "machine learning", score: 5.0, last_seen: "2024-01-15"}, ...]

    channels = Column(JSONB, default=list, nullable=False)
    # Example: [{channel_id: "UCxyz", name: "3Blue1Brown", import_count: 5}, ...]

    # Profile metadata
    total_imports = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="interest_profile", uselist=False)

    def __repr__(self):
        return f"<UserInterestProfile(user_id={self.user_id}, imports={self.total_imports})>"
