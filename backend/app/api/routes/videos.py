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
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import Video, Job, Transcript, User
from app.schemas import VideoIngestRequest, VideoIngestResponse, VideoDetail, VideoList, VideoUpdateTagsRequest, TranscriptDetail, VideoDeleteRequest, VideoDeleteResponse, VideoDeleteBreakdown
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

    video_ids = [v.id for v in videos]
    transcripts = (
        db.query(Transcript)
        .filter(Transcript.video_id.in_(video_ids))
        .all()
        if video_ids
        else []
    )
    transcript_map = {t.video_id: t for t in transcripts}

    def get_transcript_size_mb(video: Video) -> float:
        # Calculate from transcript in database (no file I/O)
        transcript = transcript_map.get(video.id)
        if transcript and transcript.full_text:
            return len(transcript.full_text.encode("utf-8")) / (1024 * 1024)
        return 0.0

    video_details: List[VideoDetail] = []
    for video in videos:
        transcript_size_mb = round(get_transcript_size_mb(video), 3)
        audio_size_mb = round(video.audio_file_size_mb or 0.0, 3)
        storage_total_mb = round(audio_size_mb + transcript_size_mb, 3)
        base = VideoDetail.model_validate(video)
        video_details.append(
            base.model_copy(
                update={
                    "transcript_size_mb": transcript_size_mb,
                    "storage_total_mb": storage_total_mb,
                }
            )
        )

    return VideoList(
        total=total,
        videos=video_details
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

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    transcript_size_mb = 0.0
    if transcript and transcript.full_text:
        transcript_size_mb = len(transcript.full_text.encode("utf-8")) / (1024 * 1024)
    transcript_size_mb = round(transcript_size_mb, 3)
    audio_size_mb = round(video.audio_file_size_mb or 0.0, 3)
    storage_total_mb = round(audio_size_mb + transcript_size_mb, 3)

    base = VideoDetail.model_validate(video)
    return base.model_copy(
        update={
            "transcript_size_mb": transcript_size_mb,
            "storage_total_mb": storage_total_mb,
        }
    )


@router.get("/{video_id}/transcript", response_model=TranscriptDetail)
async def get_video_transcript(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the full transcript for a processed video.

    Returns the complete text plus time-coded segments for review.
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
        Video.is_deleted == False
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available yet")

    return TranscriptDetail.model_validate(transcript)


def _get_transcript_size_mb(video: Video) -> float:
    """Calculate transcript size in MB (from database, no file I/O)."""
    transcript = video.transcript
    if transcript and transcript.full_text:
        return len(transcript.full_text.encode("utf-8")) / (1024 * 1024)
    return 0.0


def _estimate_index_size_mb(video: Video) -> float:
    """Estimate vector index size (~3.3 KB per chunk)."""
    if video.chunk_count == 0:
        return 0.0
    return (video.chunk_count * 3.3) / 1024.0


@router.post("/delete", response_model=VideoDeleteResponse)
async def delete_videos(
    request: VideoDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete one or more videos with granular options.

    Options:
    - remove_from_library: Soft delete in database
    - delete_search_index: Remove chunks from vector store
    - delete_audio: Delete audio files from disk
    - delete_transcript: Delete transcript files from disk

    Args:
        request: VideoDeleteRequest with video_ids and deletion options

    Returns:
        VideoDeleteResponse with breakdown and total savings
    """
    if not request.video_ids:
        raise HTTPException(status_code=400, detail="No videos specified")

    videos = db.query(Video).filter(
        Video.id.in_(request.video_ids),
        Video.user_id == current_user.id,
        Video.is_deleted == False
    ).all()

    if not videos:
        raise HTTPException(status_code=404, detail="No deletable videos found")

    if len(videos) != len(request.video_ids):
        raise HTTPException(status_code=404, detail="Some videos not found or already deleted")

    breakdowns = []
    total_savings = 0.0

    for video in videos:
        # Calculate sizes
        audio_size = video.audio_file_size_mb or 0.0
        transcript_size = round(_get_transcript_size_mb(video), 3)
        index_size = round(_estimate_index_size_mb(video), 3)
        total_size = audio_size + transcript_size + index_size

        breakdown = VideoDeleteBreakdown(
            video_id=video.id,
            title=video.title,
            audio_size_mb=round(audio_size, 3),
            transcript_size_mb=transcript_size,
            index_size_mb=index_size,
            total_size_mb=round(total_size, 3)
        )
        breakdowns.append(breakdown)

        # Delete files if requested
        if request.delete_audio and video.audio_file_path:
            try:
                audio_path = Path(video.audio_file_path)
                if audio_path.exists():
                    audio_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete audio file: {str(e)}")

        if request.delete_transcript and video.transcript_file_path:
            try:
                transcript_path = Path(video.transcript_file_path)
                if transcript_path.exists():
                    transcript_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete transcript file: {str(e)}")

        # Delete from vector store if requested
        if request.delete_search_index:
            try:
                vector_store_service.delete_video(video.id)
            except Exception as e:
                print(f"Warning: Failed to delete video from vector store: {str(e)}")

        # Soft delete from database if requested
        if request.remove_from_library:
            video.is_deleted = True
            video.deleted_at = None  # Will be set by model

        total_savings += total_size

    db.commit()

    return VideoDeleteResponse(
        deleted_count=len(videos),
        videos=breakdowns,
        total_savings_mb=round(total_savings, 3),
        message=f"Successfully deleted {len(videos)} video(s)"
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a single video (backward compatibility endpoint).

    Soft deletes from library and removes from search index.

    Args:
        video_id: Video UUID

    Returns:
        Success message
    """
    request = VideoDeleteRequest(
        video_ids=[video_id],
        remove_from_library=True,
        delete_search_index=True,
        delete_audio=True,
        delete_transcript=True
    )
    return await delete_videos(request, db, current_user)


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
