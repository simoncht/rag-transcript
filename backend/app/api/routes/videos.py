"""
API endpoints for video management.

Endpoints:
- POST /videos/ingest - Ingest YouTube video
- GET /videos - List user's videos
- GET /videos/{video_id} - Get video details
- DELETE /videos/{video_id} - Delete video
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import Video, Job, User
from app.schemas import VideoIngestRequest, VideoIngestResponse, VideoDetail, VideoList, VideoUpdateTagsRequest
from app.services.youtube import youtube_service, YouTubeDownloadError
from app.services.usage_tracker import UsageTracker, QuotaExceededError
from app.services.vector_store import vector_store_service
from app.tasks.video_tasks import process_video_pipeline

router = APIRouter()


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Get current user (placeholder for auth).

    For MVP, returns the first user or creates one.
    In production, this would use JWT token validation.
    """
    user = db.query(User).first()
    if not user:
        # Create default user for MVP
        user = User(
            email="demo@example.com",
            full_name="Demo User",
            subscription_tier="free"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/ingest", response_model=VideoIngestResponse)
async def ingest_video(
    request: VideoIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Ingest a YouTube video for processing.

    Steps:
    1. Validate YouTube URL and extract metadata
    2. Check user quotas
    3. Create video and job records
    4. Queue background processing task
    5. Return video_id and job_id for tracking

    Returns:
        VideoIngestResponse with video_id and job_id
    """
    usage_tracker = UsageTracker(db)

    try:
        # Extract and validate video info
        video_info = youtube_service.get_video_info(request.youtube_url)

        # Validate video
        is_valid, error_message = youtube_service.validate_video(video_info)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Check quotas
        duration_minutes = video_info["duration_seconds"] / 60.0 if video_info["duration_seconds"] else 0
        try:
            usage_tracker.check_quota(current_user.id, "videos", 1)
            usage_tracker.check_quota(current_user.id, "minutes", duration_minutes)
        except QuotaExceededError as e:
            raise HTTPException(
                status_code=429,
                detail=f"Quota exceeded: {str(e)}"
            )

        # Create video record
        video = Video(
            user_id=current_user.id,
            youtube_id=video_info["youtube_id"],
            youtube_url=request.youtube_url,
            title=video_info["title"],
            description=video_info["description"],
            channel_name=video_info["channel_name"],
            channel_id=video_info["channel_id"],
            thumbnail_url=video_info["thumbnail_url"],
            duration_seconds=video_info["duration_seconds"],
            upload_date=video_info["upload_date"],
            view_count=video_info["view_count"],
            like_count=video_info["like_count"],
            language=video_info["language"],
            chapters=video_info["chapters"],
            status="pending",
            progress_percent=0.0
        )
        db.add(video)
        db.flush()

        # Create job record
        job = Job(
            user_id=current_user.id,
            video_id=video.id,
            job_type="full_pipeline",
            status="pending",
            progress_percent=0.0
        )
        db.add(job)
        db.commit()
        db.refresh(video)
        db.refresh(job)

        # Queue background task
        task = process_video_pipeline.delay(
            video_id=str(video.id),
            youtube_url=request.youtube_url,
            user_id=str(current_user.id),
            job_id=str(job.id)
        )

        # Update job with Celery task ID
        job.celery_task_id = task.id
        db.commit()

        return VideoIngestResponse(
            video_id=video.id,
            job_id=job.id,
            status="pending",
            message="Video ingestion started. Use the job_id to track progress."
        )

    except YouTubeDownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest video: {str(e)}")


@router.get("", response_model=VideoList)
async def list_videos(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List user's videos with pagination and filtering.

    Args:
        skip: Number of records to skip
        limit: Number of records to return
        status: Optional status filter

    Returns:
        VideoList with videos and total count
    """
    query = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.is_deleted == False
    )

    # Apply status filter
    if status:
        query = query.filter(Video.status == status)

    # Get total count
    total = query.count()

    # Get videos with pagination
    videos = query.order_by(Video.created_at.desc()).offset(skip).limit(limit).all()

    return VideoList(
        total=total,
        videos=[VideoDetail.model_validate(v) for v in videos]
    )


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific video.

    Args:
        video_id: Video UUID

    Returns:
        VideoDetail with full video information
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
        Video.is_deleted == False
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoDetail.model_validate(video)


@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a video (soft delete).

    This will:
    - Mark video as deleted in database
    - Remove chunks from vector store
    - Optionally clean up storage files

    Args:
        video_id: Video UUID

    Returns:
        Success message
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
        Video.is_deleted == False
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Soft delete video
    video.is_deleted = True
    video.deleted_at = None  # Will be set by model
    db.commit()

    # Delete from vector store (async, best effort)
    try:
        vector_store_service.delete_video(video_id)
    except Exception as e:
        print(f"Warning: Failed to delete video from vector store: {str(e)}")

    return {"message": "Video deleted successfully", "video_id": str(video_id)}


@router.patch("/{video_id}/tags", response_model=VideoDetail)
async def update_video_tags(
    video_id: uuid.UUID,
    request: VideoUpdateTagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update tags for a video.

    Args:
        video_id: Video UUID
        request: Request with tags array

    Returns:
        VideoDetail with updated video
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
        Video.is_deleted == False
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video.tags = request.tags
    db.commit()
    db.refresh(video)

    return VideoDetail.model_validate(video)
