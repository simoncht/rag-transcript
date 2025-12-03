"""
Video model for storing YouTube video metadata and processing status.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Video(Base):
    """Video model with rich metadata."""

    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # YouTube metadata
    youtube_id = Column(String(50), nullable=False, index=True)
    youtube_url = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    channel_name = Column(String(255), nullable=True)
    channel_id = Column(String(100), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Video duration in seconds
    upload_date = Column(DateTime, nullable=True)  # When video was uploaded to YouTube
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)
    language = Column(String(10), nullable=True)  # ISO language code (e.g., 'en', 'es')

    # YouTube chapters (if available)
    chapters = Column(JSONB, nullable=True)  # [{"title": "Intro", "start_time": 0, "end_time": 120}, ...]

    # Processing status
    status = Column(String(50), default="pending", nullable=False, index=True)
    # Status values: pending, downloading, transcribing, chunking, enriching, indexing, completed, failed
    progress_percent = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)

    # Storage paths
    audio_file_path = Column(String(500), nullable=True)  # Path to downloaded audio
    audio_file_size_mb = Column(Float, nullable=True)  # File size in MB
    transcript_file_path = Column(String(500), nullable=True)  # Path to transcript JSON

    # Processing metadata
    transcription_model = Column(String(50), nullable=True)  # e.g., "whisper-base"
    transcription_language = Column(String(10), nullable=True)  # Detected language from Whisper
    transcription_duration_seconds = Column(Integer, nullable=True)  # How long transcription took
    chunk_count = Column(Integer, default=0, nullable=False)  # Number of chunks created

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)  # When processing completed

    # Relationships
    user = relationship("User", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video(id={self.id}, title={self.title[:30]}, status={self.status})>"
