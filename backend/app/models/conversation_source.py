"""
Conversation sources model.

Tracks which videos/transcripts are attached to a conversation and whether they are
currently selected for retrieval.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ConversationSource(Base):
    """
    Mapping between conversations and their available videos/transcripts.

    is_selected controls whether a given source is used during retrieval.
    """

    __tablename__ = "conversation_sources"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "video_id",
            name="uq_conversation_sources_conversation_video",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id = Column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_selected = Column(Boolean, nullable=False, default=True)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    added_via = Column(String(50), nullable=True)  # e.g., "collection" or "manual"

    # Relationships
    conversation = relationship("Conversation", back_populates="sources")
    video = relationship("Video")

    def __repr__(self):
        return f"<ConversationSource(conversation_id={self.conversation_id}, video_id={self.video_id}, selected={self.is_selected})>"
