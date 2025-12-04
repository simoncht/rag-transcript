"""
Collection models for organizing videos into playlists/groups.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Collection(Base):
    """Collection/Playlist model for organizing videos."""

    __tablename__ = "collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Metadata (instructor, subject, semester, tags, etc.)
    # Example: {"instructor": "Dr. Ng", "subject": "ML", "semester": "Fall 2024", "tags": ["course", "ai"]}
    # Note: Using 'meta' instead of 'metadata' to avoid SQLAlchemy reserved name
    meta = Column('metadata', JSONB, default={}, nullable=False)

    # Default collection flag (e.g., "Uncategorized")
    is_default = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="collections")
    collection_videos = relationship("CollectionVideo", back_populates="collection", cascade="all, delete-orphan")
    members = relationship("CollectionMember", back_populates="collection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Collection(id={self.id}, name={self.name}, user_id={self.user_id})>"


class CollectionVideo(Base):
    """Join table for many-to-many relationship between collections and videos."""

    __tablename__ = "collection_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)

    # Metadata
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=True)  # For custom ordering within collection

    # Relationships
    collection = relationship("Collection", back_populates="collection_videos")
    video = relationship("Video", back_populates="collection_videos")
    added_by = relationship("User", foreign_keys=[added_by_user_id])

    # Unique constraint: one video can only be in a collection once
    __table_args__ = (
        UniqueConstraint('collection_id', 'video_id', name='unique_collection_video'),
    )

    def __repr__(self):
        return f"<CollectionVideo(collection_id={self.collection_id}, video_id={self.video_id})>"


class CollectionMember(Base):
    """Collection sharing permissions (for Phase 4)."""

    __tablename__ = "collection_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Permission level: owner, editor, viewer
    role = Column(String(20), nullable=False)

    # Metadata
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    collection = relationship("Collection", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    added_by = relationship("User", foreign_keys=[added_by_user_id])

    # Constraints
    __table_args__ = (
        UniqueConstraint('collection_id', 'user_id', name='unique_collection_member'),
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name='valid_role'),
    )

    def __repr__(self):
        return f"<CollectionMember(collection_id={self.collection_id}, user_id={self.user_id}, role={self.role})>"
