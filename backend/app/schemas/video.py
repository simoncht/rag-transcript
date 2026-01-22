"""
Pydantic schemas for video-related API endpoints.
"""
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request schemas
class VideoIngestRequest(BaseModel):
    """Request to ingest a YouTube video."""

    youtube_url: str = Field(..., description="YouTube video URL")

    class Config:
        json_schema_extra = {
            "example": {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
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
    status: str = Field(
        ...,
        description="Processing status: pending, downloading, transcribing, chunking, enriching, indexing, completed, failed, canceled",
    )
    progress_percent: float = Field(
        ..., ge=0, le=100, description="Processing progress percentage"
    )
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
    transcript_source: Optional[str] = Field(
        default=None, description="Source of transcript: 'captions' (YouTube) or 'whisper'"
    )
    audio_file_size_mb: Optional[float] = None
    transcript_size_mb: Optional[float] = None
    storage_total_mb: Optional[float] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
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
                "message": "Video ingestion started",
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
                "delete_transcript": True,
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
                        "total_size_mb": 47.8,
                    }
                ],
                "total_savings_mb": 47.8,
                "message": "Videos deleted successfully",
            }
        }


# Cancel schemas
class VideoCancelRequest(BaseModel):
    """Request to cancel a video's processing."""

    cleanup_option: str = Field(
        default="keep_video",
        description="How to handle the video after cancellation: 'keep_video' (status=canceled) or 'full_delete' (remove record)",
    )

    class Config:
        json_schema_extra = {
            "example": {"cleanup_option": "keep_video"}
        }


class CleanupSummary(BaseModel):
    """Summary of cleanup actions taken."""

    transcript_deleted: bool = False
    chunks_deleted: int = 0
    audio_file_deleted: bool = False
    transcript_file_deleted: bool = False
    vectors_deleted: bool = False


class VideoCancelResponse(BaseModel):
    """Response from cancel operation."""

    video_id: UUID
    previous_status: str
    new_status: str
    celery_task_revoked: bool
    cleanup_summary: CleanupSummary

    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "previous_status": "downloading",
                "new_status": "canceled",
                "celery_task_revoked": True,
                "cleanup_summary": {
                    "transcript_deleted": False,
                    "chunks_deleted": 0,
                    "audio_file_deleted": True,
                    "vectors_deleted": False,
                },
            }
        }


class BulkCancelRequest(BaseModel):
    """Request to cancel multiple videos."""

    video_ids: List[UUID]
    cleanup_option: str = Field(
        default="keep_video",
        description="How to handle the videos after cancellation: 'keep_video' or 'full_delete'",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "video_ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "660e8400-e29b-41d4-a716-446655440001",
                ],
                "cleanup_option": "keep_video",
            }
        }


class BulkCancelResultItem(BaseModel):
    """Result for a single video in bulk cancel."""

    video_id: UUID
    success: bool
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    error: Optional[str] = None


class BulkCancelResponse(BaseModel):
    """Response from bulk cancel operation."""

    total: int
    canceled: int
    skipped: int
    results: List[BulkCancelResultItem]

    class Config:
        json_schema_extra = {
            "example": {
                "total": 4,
                "canceled": 3,
                "skipped": 1,
                "results": [
                    {
                        "video_id": "550e8400-e29b-41d4-a716-446655440000",
                        "success": True,
                        "previous_status": "downloading",
                        "new_status": "canceled",
                    },
                    {
                        "video_id": "660e8400-e29b-41d4-a716-446655440001",
                        "success": False,
                        "error": "Video is already in terminal status: completed",
                    },
                ],
            }
        }
