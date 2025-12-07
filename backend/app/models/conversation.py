"""
Conversation model for managing chat sessions.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.db.base import Base


class Conversation(Base):
    """
    Conversation model for chat sessions.

    Each conversation has a scope of selected videos and maintains message history.
    """

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL"), nullable=True, index=True)

    # Conversation metadata
    title = Column(String(255), nullable=True)  # Auto-generated or user-provided
    selected_video_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])  # Videos in scope

    # Statistics
    message_count = Column(Integer, default=0, nullable=False)
    total_tokens_used = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    sources = relationship(
        "ConversationSource",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationSource.added_at",
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, messages={self.message_count})>"
