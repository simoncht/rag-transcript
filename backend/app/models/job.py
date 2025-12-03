"""
Job model for tracking asynchronous processing tasks.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Job(Base):
    """
    Job model for tracking background processing tasks.

    Tracks the status and progress of async operations like video download,
    transcription, chunking, and indexing.
    """

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)

    # Job metadata
    job_type = Column(String(50), nullable=False, index=True)
    # Job types: download_audio, transcribe, chunk_transcript, enrich_chunks, index_chunks, full_pipeline

    # Celery task info
    celery_task_id = Column(String(255), nullable=True, unique=True, index=True)

    # Status tracking
    status = Column(String(50), default="pending", nullable=False, index=True)
    # Status values: pending, running, completed, failed, canceled
    progress_percent = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(100), nullable=True)  # Human-readable current step
    total_steps = Column(Integer, nullable=True)
    completed_steps = Column(Integer, default=0, nullable=False)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)  # Structured error info
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Results
    result = Column(JSONB, nullable=True)  # Job output data

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User")
    video = relationship("Video")

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status}, progress={self.progress_percent}%)>"

    @property
    def duration_seconds(self) -> float:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0.0

    @property
    def is_terminal_state(self) -> bool:
        """Check if job is in a terminal state (completed, failed, canceled)."""
        return self.status in ["completed", "failed", "canceled"]

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == "failed" and self.retry_count < self.max_retries
