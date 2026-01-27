"""
ConversationFact model.

Stores extracted facts from conversation messages for long-distance recall.
Enables the system to remember key information (names, topics, frameworks, etc.)
from early turns that are outside the working memory window.

Enhanced with multi-factor scoring based on OpenAI/Anthropic memory best practices:
- importance: LLM-rated significance (0.0-1.0)
- category: Fact type for scope separation (identity, topic, preference, session)
- last_accessed: For retrieval strength calculation (frequency factor)
- access_count: How often this fact has been recalled
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class FactCategory(str, Enum):
    """Categories for scope separation (OpenAI WMR best practice)."""
    IDENTITY = "identity"      # Durable: names, roles, relationships (highest priority)
    TOPIC = "topic"            # Core concepts, subjects being discussed
    PREFERENCE = "preference"  # User preferences, opinions
    SESSION = "session"        # Session-specific context (lower priority)
    EPHEMERAL = "ephemeral"    # Single-use facts (lowest priority)


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

    # Metadata (original)
    source_turn = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False, default=1.0)

    # NEW: Multi-factor scoring fields (Phase 2 enhancement)
    # LLM-rated importance (0.0-1.0): identity facts get 0.9+, ephemeral get 0.3-
    importance = Column(Float, nullable=False, default=0.5)

    # Category for scope separation: identity > topic > preference > session > ephemeral
    category = Column(String(50), nullable=False, default=FactCategory.TOPIC.value)

    # For retrieval strength: track when fact was last used
    last_accessed = Column(DateTime, nullable=True)  # NULL = never accessed

    # For frequency factor: how often this fact has been recalled
    access_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="facts")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "fact_key", name="unique_conversation_fact_key"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationFact(key={self.fact_key}, value={self.fact_value[:30]}..., "
            f"turn={self.source_turn}, importance={self.importance:.2f}, "
            f"category={self.category})>"
        )
