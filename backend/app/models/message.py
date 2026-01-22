"""
Message model for storing conversation messages.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Message(Base):
    """
    Message model for user and assistant messages.

    Stores the message content, role, tokens used, and references to source chunks.
    """

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Token usage
    token_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(
        Integer, nullable=True
    )  # For assistant messages: prompt tokens
    output_tokens = Column(
        Integer, nullable=True
    )  # For assistant messages: completion tokens

    # LLM metadata (for assistant messages)
    llm_provider = Column(String(50), nullable=True)  # e.g., "ollama", "openai"
    llm_model = Column(String(100), nullable=True)  # e.g., "llama2", "gpt-4"
    response_time_seconds = Column(
        Float, nullable=True
    )  # How long the LLM took to respond

    # RAG metadata (for assistant messages)
    chunks_retrieved_count = Column(
        Integer, nullable=True
    )  # How many chunks were retrieved
    chunks_used_count = Column(
        Integer, nullable=True
    )  # How many chunks were actually used in response

    # Additional metadata
    message_metadata = Column(
        JSONB, nullable=True
    )  # For storing extra info (e.g., streaming status, errors)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    chunk_references = relationship(
        "MessageChunkReference", back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, tokens={self.token_count})>"


class MessageChunkReference(Base):
    """
    Many-to-many relationship between messages and chunks.

    Tracks which chunks were used to generate each assistant message,
    including confidence scores for citations.
    """

    __tablename__ = "message_chunk_references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Citation metadata
    relevance_score = Column(
        Float, nullable=False
    )  # Similarity score from vector search
    rank = Column(Integer, nullable=False)  # Position in retrieved results (1-indexed)
    was_used_in_response = Column(
        Boolean, nullable=False, default=True
    )  # Whether LLM actually used this chunk

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="chunk_references")
    chunk = relationship("Chunk", back_populates="message_references")

    def __repr__(self):
        return f"<MessageChunkReference(message_id={self.message_id}, chunk_id={self.chunk_id}, score={self.relevance_score})>"
