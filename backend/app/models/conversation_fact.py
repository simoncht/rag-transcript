"""
ConversationFact model.

Stores extracted facts from conversation messages for long-distance recall.
Enables the system to remember key information (names, topics, frameworks, etc.)
from early turns that are outside the working memory window.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ConversationFact(Base):
    __tablename__ = "conversation_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fact data (simple key-value)
    fact_key = Column(String(200), nullable=False)
    fact_value = Column(Text, nullable=False)

    # Metadata
    source_turn = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="facts")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("conversation_id", "fact_key", name="unique_conversation_fact_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationFact(key={self.fact_key}, value={self.fact_value[:30]}..., "
            f"turn={self.source_turn}, confidence={self.confidence_score:.2f})>"
        )
