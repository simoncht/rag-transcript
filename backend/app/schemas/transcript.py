"""
Pydantic schemas for transcript retrieval.
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """Single transcript segment with timing."""
    text: str
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    speaker: Optional[str] = Field(None, description="Speaker label if available")


class TranscriptDetail(BaseModel):
    """Full transcript for a video."""
    video_id: UUID
    full_text: str
    language: Optional[str] = None
    duration_seconds: int
    word_count: int
    has_speaker_labels: bool
    speaker_count: Optional[int] = None
    created_at: datetime
    segments: List[TranscriptSegment]

    class Config:
        from_attributes = True
