"""
Pydantic schemas for video-related API endpoints.
"""
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field


# Request schemas
class VideoIngestRequest(BaseModel):
    """Request to ingest a YouTube video."""
    youtube_url: str = Field(..., description="YouTube video URL")

    class Config:
        json_schema_extra = {
            "example": {
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        }


# Response schemas
class VideoMetadata(BaseModel):
    """Video metadata."""
    id: UUID
    youtube_id: str
    youtube_url: str
    title: str
    description: Optional[str] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    upload_date: Optional[datetime] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    language: Optional[str] = None
    chapters: Optional[List[Dict]] = None

    class Config:
        from_attributes = True


class VideoStatus(BaseModel):
    """Video processing status."""
    id: UUID
    status: str = Field(..., description="Processing status: pending, downloading, transcribing, chunking, enriching, indexing, completed, failed")
    progress_percent: float = Field(..., ge=0, le=100, description="Processing progress percentage")
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VideoDetail(BaseModel):
    """Detailed video information."""
    id: UUID
    user_id: UUID

    # Metadata
    youtube_id: str
    youtube_url: str
    title: str
    description: Optional[str] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    upload_date: Optional[datetime] = None
    language: Optional[str] = None
    chapters: Optional[List[Dict]] = None
    tags: List[str] = Field(default_factory=list, description="Video tags")

    # Processing
    status: str
    progress_percent: float
    error_message: Optional[str] = None

    # Stats
    chunk_count: int
    transcription_language: Optional[str] = None
    audio_file_size_mb: Optional[float] = None
    transcript_size_mb: Optional[float] = None
    storage_total_mb: Optional[float] = None

    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VideoList(BaseModel):
    """List of videos."""
    total: int
    videos: List[VideoDetail]


class VideoIngestResponse(BaseModel):
    """Response from video ingestion."""
    video_id: UUID
    job_id: UUID
    status: str
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "660e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Video ingestion started"
            }
        }


class VideoDeleteBreakdown(BaseModel):
    """Storage breakdown for a single video."""
    video_id: UUID
    title: str
    audio_size_mb: float
    transcript_size_mb: float
    index_size_mb: float
    total_size_mb: float


class VideoDeleteRequest(BaseModel):
    """Request to delete videos with granular options."""
    video_ids: List[UUID]
    remove_from_library: bool = True  # Soft delete in DB
    delete_search_index: bool = True  # Remove from vector store
    delete_audio: bool = True  # Delete audio files
    delete_transcript: bool = True  # Delete transcript files

    class Config:
        json_schema_extra = {
            "example": {
                "video_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "remove_from_library": True,
                "delete_search_index": True,
                "delete_audio": True,
                "delete_transcript": True
            }
        }


class VideoDeleteResponse(BaseModel):
    """Response from video deletion with storage savings."""
    deleted_count: int
    videos: List[VideoDeleteBreakdown]
    total_savings_mb: float
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "deleted_count": 1,
                "videos": [
                    {
                        "video_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Example Video",
                        "audio_size_mb": 45.2,
                        "transcript_size_mb": 0.5,
                        "index_size_mb": 2.1,
                        "total_size_mb": 47.8
                    }
                ],
                "total_savings_mb": 47.8,
                "message": "Videos deleted successfully"
            }
        }
