"""
Transcript model for storing raw transcription output.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Transcript(Base):
    """Transcript model storing raw Whisper output with segments."""

    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Full transcript text
    full_text = Column(Text, nullable=False)

    # Raw segments from Whisper: [{"text": "...", "start": 0.0, "end": 5.2, "speaker": "SPEAKER_00"}, ...]
    segments = Column(JSONB, nullable=False)

    # Metadata
    language = Column(String(10), nullable=True)  # Detected language
    word_count = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Integer, nullable=False)

    # Speaker diarization (if available)
    has_speaker_labels = Column(Boolean, nullable=False, default=False)
    speaker_count = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="transcript")

    def __repr__(self):
        return f"<Transcript(id={self.id}, video_id={self.video_id}, language={self.language})>"
