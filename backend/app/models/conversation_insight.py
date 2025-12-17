"""
ConversationInsight model.

Stores cached topic graphs and topic->chunk mappings for a conversation to avoid
re-running LLM extraction on every modal open.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.db.base import Base


class ConversationInsight(Base):
    __tablename__ = "conversation_insights"

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

    video_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)

    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    extraction_prompt_version = Column(Integer, nullable=False, default=1)

    graph_data = Column(JSONB, nullable=False)
    topic_chunks = Column(JSONB, nullable=False)

    topics_count = Column(Integer, nullable=False)
    total_chunks_analyzed = Column(Integer, nullable=False)
    generation_time_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<ConversationInsight(conversation_id={self.conversation_id}, "
            f"topics={self.topics_count}, created_at={self.created_at})>"
        )
