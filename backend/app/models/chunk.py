"""
Chunk model for storing transcript chunks with contextual enrichment.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    Text,
    Float,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.db.base import Base


class Chunk(Base):
    """
    Chunk model storing semantically meaningful units of transcript.

    Each chunk represents a coherent "thought unit" from the transcript,
    with contextual enrichment (summary, title, keywords) for better retrieval.
    """

    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Chunk ordering and position
    chunk_index = Column(Integer, nullable=False)  # 0-indexed position in video

    # Original text
    text = Column(Text, nullable=False)  # The actual chunk text
    token_count = Column(Integer, nullable=False)  # Token count using tiktoken

    # Timing information
    start_timestamp = Column(Float, nullable=False)  # Start time in seconds
    end_timestamp = Column(Float, nullable=False)  # End time in seconds
    duration_seconds = Column(Float, nullable=False)  # end - start

    # Speaker information (if available)
    speakers = Column(ARRAY(String), nullable=True)  # List of speaker IDs in this chunk

    # YouTube chapter (if video has chapters)
    chapter_title = Column(String(255), nullable=True)
    chapter_index = Column(Integer, nullable=True)

    # Contextual enrichment (Anthropic-style contextual retrieval)
    chunk_summary = Column(Text, nullable=True)  # 1-3 sentences summarizing the chunk
    chunk_title = Column(String(255), nullable=True)  # Short phrase capturing main idea
    keywords = Column(ARRAY(String), nullable=True)  # Key topics/entities

    # Embedding information
    embedding_text = Column(
        Text, nullable=True
    )  # Combined text used for embedding: f"{title}. {summary}\n\n{text}"
    is_indexed = Column(
        Boolean, nullable=False, default=False
    )  # Whether chunk is in vector DB
    indexed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    enriched_at = Column(
        DateTime, nullable=True
    )  # When contextual enrichment was completed

    # Relationships
    video = relationship("Video", back_populates="chunks")
    user = relationship("User")
    message_references = relationship(
        "MessageChunkReference", back_populates="chunk", cascade="all, delete-orphan"
    )

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_chunk_video_index", "video_id", "chunk_index"),
        Index("idx_chunk_user_video", "user_id", "video_id"),
        Index("idx_chunk_timestamps", "start_timestamp", "end_timestamp"),
    )

    def __repr__(self):
        return f"<Chunk(id={self.id}, video_id={self.video_id}, index={self.chunk_index}, tokens={self.token_count})>"

    @property
    def timestamp_display(self) -> str:
        """Format timestamps as MM:SS or HH:MM:SS."""
        start_mins = int(self.start_timestamp // 60)
        start_secs = int(self.start_timestamp % 60)
        end_mins = int(self.end_timestamp // 60)
        end_secs = int(self.end_timestamp % 60)

        if start_mins >= 60:
            start_hours = start_mins // 60
            start_mins = start_mins % 60
            end_hours = end_mins // 60
            end_mins = end_mins % 60
            return f"{start_hours:02d}:{start_mins:02d}:{start_secs:02d} - {end_hours:02d}:{end_mins:02d}:{end_secs:02d}"

        return f"{start_mins:02d}:{start_secs:02d} - {end_mins:02d}:{end_secs:02d}"
