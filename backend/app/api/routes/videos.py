"""
API endpoints for video management.

Endpoints:
- POST /videos/ingest - Ingest YouTube video
- GET /videos - List user's videos
- GET /videos/{video_id} - Get video details
- DELETE /videos/{video_id} - Delete video
"""
import logging
import uuid
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.core.nextauth import get_current_user
from app.db.base import get_db
from app.models import Video, Job, Transcript, User, CollectionVideo, Chunk
from app.schemas import (
    VideoIngestRequest,
    VideoIngestResponse,
    VideoDetail,
    VideoList,
    VideoUpdateTagsRequest,
    TranscriptDetail,
    VideoDeleteRequest,
    VideoDeleteResponse,
    VideoDeleteBreakdown,
    VideoCancelRequest,
    VideoCancelResponse,
    CleanupSummary,
    BulkCancelRequest,
    BulkCancelResponse,
    BulkCancelResultItem,
    SimilarVideosResponse,
)
from app.services.youtube import youtube_service, YouTubeDownloadError
from app.services.video_processing import reset_video_processing
from app.services.vector_store import vector_store_service
from app.services.job_cancellation import (
    cancel_video_processing,
    is_cancelable,
    CleanupOption,
    CANCELABLE_STATUSES,
)
from app.tasks.video_tasks import process_video_pipeline
from app.core.rate_limit import limiter

router = APIRouter()


@router.post("/ingest", response_model=VideoIngestResponse)
@limiter.limit("10/hour")
async def ingest_video(
    request: Request,
    ingest_request: VideoIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    try:
        # Extract and validate video info
        video_info = youtube_service.get_video_info(ingest_request.youtube_url)

        # Validate video
        is_valid, error_message = youtube_service.validate_video(video_info)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Check for duplicate - same YouTube video for same user
        existing_video = (
            db.query(Video)
            .filter(
                Video.user_id == current_user.id,
                Video.youtube_id == video_info["youtube_id"],
                Video.is_deleted.is_(False),
            )
            .first()
        )
        if existing_video:
            raise HTTPException(
                status_code=400,
                detail=f"Video already exists: '{existing_video.title}' (status: {existing_video.status}, id: {existing_video.id})",
            )

        # Check user quotas
        from app.core.quota import check_video_quota, check_minutes_quota, check_storage_quota
        await check_video_quota(current_user, db)
        duration_minutes = int(video_info["duration_seconds"] / 60)
        await check_minutes_quota(current_user, duration_minutes, db)

        # Estimate storage impact for quota check
        # ~100MB average per video (transcript + chunks + vectors)
        estimated_storage_mb = 100.0
        await check_storage_quota(current_user, estimated_storage_mb, db)

        # Create video record
        video = Video(
            user_id=current_user.id,
            youtube_id=video_info["youtube_id"],
            youtube_url=ingest_request.youtube_url,
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
            progress_percent=0.0,
        )
        db.add(video)
        db.flush()

        # Create job record
        job = Job(
            user_id=current_user.id,
            video_id=video.id,
            job_type="full_pipeline",
            status="pending",
            progress_percent=0.0,
        )
        db.add(job)
        db.commit()
        db.refresh(video)
        db.refresh(job)

        # Queue background task
        task = process_video_pipeline.delay(
            video_id=str(video.id),
            youtube_url=ingest_request.youtube_url,
            user_id=str(current_user.id),
            job_id=str(job.id),
        )

        # Update job with Celery task ID
        job.celery_task_id = task.id
        db.commit()

        return VideoIngestResponse(
            video_id=video.id,
            job_id=job.id,
            status="pending",
            message="Video ingestion started. Use the job_id to track progress.",
        )

    except YouTubeDownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is (e.g., validation failures, quota errors)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest video: {str(e)}")


SORT_MAP = {
    "created_at_desc": Video.created_at.desc(),
    "created_at_asc": Video.created_at.asc(),
    "upload_date_desc": Video.upload_date.desc().nullslast(),
    "duration_desc": Video.duration_seconds.desc().nullslast(),
    "duration_asc": Video.duration_seconds.asc().nullsfirst(),
    "title_asc": Video.title.asc(),
}


@router.get("", response_model=VideoList)
async def list_videos(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    q: Optional[str] = Query(None, max_length=200, description="Search title, description, channel"),
    sort: Optional[str] = Query(None, description="Sort order"),
    channel: Optional[str] = Query(None, max_length=255, description="Filter by channel name"),
    tags: Optional[str] = Query(None, max_length=500, description="Comma-separated tags (OR logic)"),
    duration_min: Optional[int] = Query(None, ge=0, description="Min duration in seconds"),
    duration_max: Optional[int] = Query(None, ge=0, description="Max duration in seconds"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user's videos with pagination, search, filtering, and sorting.

    Args:
        skip: Number of records to skip
        limit: Number of records to return
        status: Optional status filter
        q: Search across title, description, channel_name (ILIKE)
        sort: Sort order (created_at_desc, created_at_asc, upload_date_desc, duration_desc, duration_asc, title_asc)
        channel: Filter by exact channel_name
        tags: Comma-separated tag names, OR logic
        duration_min: Minimum duration in seconds
        duration_max: Maximum duration in seconds

    Returns:
        VideoList with videos and total count
    """
    query = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.is_deleted.is_(False),
        Video.content_type == "youtube",
    )

    # Apply status filter
    if status:
        query = query.filter(Video.status == status)

    # Apply text search
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            Video.title.ilike(search_term)
            | Video.description.ilike(search_term)
            | Video.channel_name.ilike(search_term)
        )

    # Apply channel filter
    if channel:
        query = query.filter(Video.channel_name == channel)

    # Apply tag filter (OR logic using PostgreSQL array overlap)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            query = query.filter(Video.tags.overlap(tag_list))

    # Apply duration filters
    if duration_min is not None:
        query = query.filter(Video.duration_seconds >= duration_min)
    if duration_max is not None:
        query = query.filter(Video.duration_seconds <= duration_max)

    # Get total count
    total = query.count()

    # Apply sort
    sort_clause = SORT_MAP.get(sort, Video.created_at.desc())
    videos = query.order_by(sort_clause).offset(skip).limit(limit).all()

    video_ids = [v.id for v in videos]
    transcripts = (
        db.query(Transcript).filter(Transcript.video_id.in_(video_ids)).all()
        if video_ids
        else []
    )
    transcript_map = {t.video_id: t for t in transcripts}

    # Calculate chunk storage per video (sum of all text fields: text + chunk_summary + embedding_text)
    # This matches StorageCalculator behavior for consistent storage reporting
    chunk_sizes = (
        db.query(
            Chunk.video_id,
            func.sum(
                func.coalesce(func.length(Chunk.text), 0)
                + func.coalesce(func.length(Chunk.chunk_summary), 0)
                + func.coalesce(func.length(Chunk.embedding_text), 0)
            ).label("chunk_bytes"),
        )
        .filter(Chunk.video_id.in_(video_ids))
        .group_by(Chunk.video_id)
        .all()
        if video_ids
        else []
    )
    chunk_size_map = {cs.video_id: cs.chunk_bytes or 0 for cs in chunk_sizes}

    def get_transcript_size_mb(video: Video) -> float:
        # Priority: actual file size > text encoding estimate
        if video.transcript_file_path:
            try:
                file_path = Path(video.transcript_file_path)
                if file_path.exists():
                    return file_path.stat().st_size / (1024 * 1024)
            except (OSError, IOError):
                pass  # Fall through to estimate

        # Fallback to text encoding estimate
        transcript = transcript_map.get(video.id)
        if transcript and transcript.full_text:
            return len(transcript.full_text.encode("utf-8")) / (1024 * 1024)
        return 0.0

    def get_chunk_storage_mb(video: Video) -> float:
        """Calculate chunk storage in MB from text bytes."""
        text_bytes = chunk_size_map.get(video.id, 0)
        return text_bytes / (1024 * 1024)

    def get_vector_storage_mb(video: Video) -> float:
        """Estimate vector storage: ~5KB per chunk."""
        if video.chunk_count == 0:
            return 0.0
        return (video.chunk_count * 5.0) / 1024.0

    video_details: List[VideoDetail] = []
    for video in videos:
        transcript_size_mb = round(get_transcript_size_mb(video), 3)
        chunk_storage_mb = round(get_chunk_storage_mb(video), 3)
        vector_storage_mb = round(get_vector_storage_mb(video), 3)
        # Total is now: transcript + chunks + vectors (audio is 0)
        storage_total_mb = round(transcript_size_mb + chunk_storage_mb + vector_storage_mb, 3)
        base = VideoDetail.model_validate(video)
        video_details.append(
            base.model_copy(
                update={
                    "transcript_size_mb": transcript_size_mb,
                    "chunk_storage_mb": chunk_storage_mb,
                    "vector_storage_mb": vector_storage_mb,
                    "storage_total_mb": storage_total_mb,
                }
            )
        )

    return VideoList(total=total, videos=video_details)


@router.get("/filters")
async def get_video_filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get available filter values for the current user's videos.

    Returns channels and tags with counts for populating filter dropdowns.
    """
    base_filter = [
        Video.user_id == current_user.id,
        Video.is_deleted.is_(False),
        Video.content_type == "youtube",
    ]

    # Get channels with counts
    channels = (
        db.query(Video.channel_name, func.count(Video.id).label("count"))
        .filter(*base_filter)
        .filter(Video.channel_name.isnot(None))
        .group_by(Video.channel_name)
        .order_by(func.count(Video.id).desc())
        .all()
    )

    # Get tags with counts using unnest
    tag_counts = (
        db.query(
            func.unnest(Video.tags).label("tag"),
            func.count().label("count"),
        )
        .filter(*base_filter)
        .group_by("tag")
        .order_by(func.count().desc())
        .all()
    )

    # Get status counts
    status_counts = (
        db.query(Video.status, func.count(Video.id).label("count"))
        .filter(*base_filter)
        .group_by(Video.status)
        .all()
    )

    return {
        "channels": [{"name": ch.channel_name, "count": ch.count} for ch in channels],
        "tags": [{"name": t.tag, "count": t.count} for t in tag_counts],
        "statuses": [{"name": s.status, "count": s.count} for s in status_counts],
    }


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific video.

    Args:
        video_id: Video UUID

    Returns:
        VideoDetail with full video information
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
            Video.content_type == "youtube",
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Calculate transcript size - prefer actual file size over text estimate
    transcript_size_mb = 0.0
    if video.transcript_file_path:
        try:
            file_path = Path(video.transcript_file_path)
            if file_path.exists():
                transcript_size_mb = file_path.stat().st_size / (1024 * 1024)
        except (OSError, IOError):
            pass

    # Fallback to text encoding estimate if file not found
    if transcript_size_mb == 0.0:
        transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
        if transcript and transcript.full_text:
            transcript_size_mb = len(transcript.full_text.encode("utf-8")) / (1024 * 1024)

    # Calculate chunk storage (sum of all text fields: text + chunk_summary + embedding_text)
    # This matches StorageCalculator behavior for consistent storage reporting
    chunk_bytes = (
        db.query(
            func.sum(
                func.coalesce(func.length(Chunk.text), 0)
                + func.coalesce(func.length(Chunk.chunk_summary), 0)
                + func.coalesce(func.length(Chunk.embedding_text), 0)
            )
        )
        .filter(Chunk.video_id == video_id)
        .scalar()
        or 0
    )
    chunk_storage_mb = chunk_bytes / (1024 * 1024)

    # Estimate vector storage: ~5KB per chunk
    vector_storage_mb = (video.chunk_count * 5.0) / 1024.0 if video.chunk_count > 0 else 0.0

    transcript_size_mb = round(transcript_size_mb, 3)
    chunk_storage_mb = round(chunk_storage_mb, 3)
    vector_storage_mb = round(vector_storage_mb, 3)
    # Total is now: transcript + chunks + vectors (audio is 0)
    storage_total_mb = round(transcript_size_mb + chunk_storage_mb + vector_storage_mb, 3)

    base = VideoDetail.model_validate(video)
    return base.model_copy(
        update={
            "transcript_size_mb": transcript_size_mb,
            "chunk_storage_mb": chunk_storage_mb,
            "vector_storage_mb": vector_storage_mb,
            "storage_total_mb": storage_total_mb,
        }
    )


@router.get("/{video_id}/transcript", response_model=TranscriptDetail)
async def get_video_transcript(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the full transcript for a processed video.

    Returns the complete text plus time-coded segments for review.
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available yet")

    return TranscriptDetail.model_validate(transcript)


@router.get("/{video_id}/collections")
async def get_video_collections(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the list of collection IDs that contain this video.

    Args:
        video_id: Video UUID

    Returns:
        Dict with collection_ids array
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get all collection IDs for this video
    collection_ids = (
        db.query(CollectionVideo.collection_id)
        .filter(CollectionVideo.video_id == video_id)
        .all()
    )

    return {
        "collection_ids": [str(cid[0]) for cid in collection_ids]
    }


@router.post("/{video_id}/reprocess", response_model=VideoIngestResponse)
async def reprocess_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run the full processing pipeline for an existing video.

    This is used to recover videos stuck mid-pipeline or to rebuild missing artifacts
    (transcript/chunks/index) without requiring a fresh ingest.
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )  # noqa: E712
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check user quotas before reprocessing
    # Note: Video already exists so we don't check video count quota
    # But we do check minutes and storage since reprocessing regenerates artifacts
    from app.core.quota import check_minutes_quota, check_storage_quota

    duration_minutes = int((video.duration_seconds or 0) / 60)
    await check_minutes_quota(current_user, duration_minutes, db)

    # Estimate storage impact for quota check (~100MB per video)
    estimated_storage_mb = 100.0
    await check_storage_quota(current_user, estimated_storage_mb, db)

    reset_video_processing(db, video=video, delete_files=False, delete_vectors=True)

    job = Job(
        user_id=current_user.id,
        video_id=video.id,
        job_type="full_pipeline",
        status="pending",
        progress_percent=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = process_video_pipeline.delay(
        video_id=str(video.id),
        youtube_url=video.youtube_url,
        user_id=str(current_user.id),
        job_id=str(job.id),
    )
    job.celery_task_id = task.id
    db.commit()

    return VideoIngestResponse(
        video_id=video.id,
        job_id=job.id,
        status="pending",
        message="Video reprocessing started. Use the job_id to track progress.",
    )


@router.post("/{video_id}/cancel", response_model=VideoCancelResponse)
async def cancel_video(
    video_id: uuid.UUID,
    cancel_request: VideoCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a video's processing and clean up partial data.

    Args:
        video_id: Video UUID
        cancel_request: Cancel options (cleanup_option: 'keep_video' or 'full_delete')

    Returns:
        VideoCancelResponse with operation summary
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if video can be canceled
    if not is_cancelable(video):
        raise HTTPException(
            status_code=400,
            detail=f"Video cannot be canceled - status is '{video.status}'. Only videos in non-terminal statuses can be canceled.",
        )

    # Parse cleanup option
    try:
        cleanup_option = CleanupOption(cancel_request.cleanup_option)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cleanup_option: {cancel_request.cleanup_option}. Must be 'keep_video' or 'full_delete'.",
        )

    # Cancel the video
    result = cancel_video_processing(db, video, cleanup_option)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return VideoCancelResponse(
        video_id=result.video_id,
        previous_status=result.previous_status,
        new_status=result.new_status,
        celery_task_revoked=result.celery_task_revoked,
        cleanup_summary=CleanupSummary(
            transcript_deleted=result.cleanup_summary.transcript_deleted,
            chunks_deleted=result.cleanup_summary.chunks_deleted,
            audio_file_deleted=result.cleanup_summary.audio_file_deleted,
            transcript_file_deleted=result.cleanup_summary.transcript_file_deleted,
            vectors_deleted=result.cleanup_summary.vectors_deleted,
        ),
    )


@router.post("/cancel-bulk", response_model=BulkCancelResponse)
async def cancel_videos_bulk(
    bulk_request: BulkCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel multiple videos at once.

    Args:
        bulk_request: List of video IDs and cleanup option

    Returns:
        BulkCancelResponse with per-video results
    """
    if not bulk_request.video_ids:
        raise HTTPException(status_code=400, detail="No videos specified")

    # Parse cleanup option
    try:
        cleanup_option = CleanupOption(bulk_request.cleanup_option)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cleanup_option: {bulk_request.cleanup_option}. Must be 'keep_video' or 'full_delete'.",
        )

    results = []
    canceled_count = 0
    skipped_count = 0

    for video_id in bulk_request.video_ids:
        video = (
            db.query(Video)
            .filter(
                Video.id == video_id,
                Video.user_id == current_user.id,
                Video.is_deleted.is_(False),
            )
            .first()
        )

        if not video:
            results.append(
                BulkCancelResultItem(
                    video_id=video_id,
                    success=False,
                    error="Video not found",
                )
            )
            skipped_count += 1
            continue

        if not is_cancelable(video):
            results.append(
                BulkCancelResultItem(
                    video_id=video_id,
                    success=False,
                    previous_status=video.status,
                    error=f"Cannot cancel - status is '{video.status}'",
                )
            )
            skipped_count += 1
            continue

        result = cancel_video_processing(db, video, cleanup_option)

        if result.error:
            results.append(
                BulkCancelResultItem(
                    video_id=video_id,
                    success=False,
                    previous_status=result.previous_status,
                    error=result.error,
                )
            )
            skipped_count += 1
        else:
            results.append(
                BulkCancelResultItem(
                    video_id=video_id,
                    success=True,
                    previous_status=result.previous_status,
                    new_status=result.new_status,
                )
            )
            canceled_count += 1

    return BulkCancelResponse(
        total=len(bulk_request.video_ids),
        canceled=canceled_count,
        skipped=skipped_count,
        results=results,
    )


def _get_transcript_size_mb(video: Video) -> float:
    """
    Get transcript size in MB.

    Priority:
    1. Actual file size on disk (most accurate)
    2. Text encoding estimate (fallback if file not found)
    """
    # Try actual file size first
    if video.transcript_file_path:
        try:
            file_path = Path(video.transcript_file_path)
            if file_path.exists():
                return file_path.stat().st_size / (1024 * 1024)
        except (OSError, IOError):
            pass  # Fall through to estimate

    # Fallback to text encoding estimate
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
    current_user: User = Depends(get_current_user),
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

    videos = (
        db.query(Video)
        .filter(
            Video.id.in_(request.video_ids),
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .all()
    )

    if not videos:
        raise HTTPException(status_code=404, detail="No deletable videos found")

    if len(videos) != len(request.video_ids):
        raise HTTPException(
            status_code=404, detail="Some videos not found or already deleted"
        )

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
            total_size_mb=round(total_size, 3),
        )
        breakdowns.append(breakdown)

        # Delete files if requested
        if request.delete_audio and video.audio_file_path:
            try:
                audio_path = Path(video.audio_file_path)
                if audio_path.exists():
                    audio_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete audio file: {str(e)}")

        if request.delete_transcript and video.transcript_file_path:
            try:
                transcript_path = Path(video.transcript_file_path)
                if transcript_path.exists():
                    transcript_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete transcript file: {str(e)}")

        # Delete from vector store and clean up chunks if requested
        if request.delete_search_index:
            try:
                vector_store_service.delete_video(video.id)
            except Exception as e:
                logger.warning(f"Failed to delete video from vector store: {str(e)}")

            # Also delete chunk rows from PostgreSQL to avoid orphaned data
            try:
                deleted_chunks = (
                    db.query(Chunk)
                    .filter(Chunk.video_id == video.id)
                    .delete(synchronize_session=False)
                )
                if deleted_chunks > 0:
                    logger.debug(f"Deleted {deleted_chunks} chunks for video {video.id}")
            except Exception as e:
                logger.warning(f"Failed to delete chunks from database: {str(e)}")

        # Soft delete from database if requested
        if request.remove_from_library:
            video.is_deleted = True
            video.deleted_at = None  # Will be set by model

            # Clean up CollectionVideo entries to maintain count consistency
            try:
                deleted_cv = (
                    db.query(CollectionVideo)
                    .filter(CollectionVideo.video_id == video.id)
                    .delete(synchronize_session=False)
                )
                if deleted_cv > 0:
                    logger.debug(f"Removed video {video.id} from {deleted_cv} collection(s)")
            except Exception as e:
                logger.warning(f"Failed to clean up collection associations: {str(e)}")

        total_savings += total_size

    db.commit()

    return VideoDeleteResponse(
        deleted_count=len(videos),
        videos=breakdowns,
        total_savings_mb=round(total_savings, 3),
        message=f"Successfully deleted {len(videos)} video(s)",
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        delete_transcript=True,
    )
    return await delete_videos(request, db, current_user)


@router.patch("/{video_id}/tags", response_model=VideoDetail)
async def update_video_tags(
    video_id: uuid.UUID,
    request: VideoUpdateTagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update tags for a video.

    Args:
        video_id: Video UUID
        request: Request with tags array

    Returns:
        VideoDetail with updated video
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video.tags = request.tags
    db.commit()
    db.refresh(video)

    return VideoDetail.model_validate(video)


@router.patch("/tags/bulk")
async def bulk_update_tags(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk add/remove tags for multiple videos.

    Body:
        video_ids: list of video UUIDs
        add_tags: list of tags to add
        remove_tags: list of tags to remove
    """
    video_ids = body.get("video_ids", [])
    add_tags = body.get("add_tags", [])
    remove_tags = body.get("remove_tags", [])

    if not video_ids:
        raise HTTPException(status_code=400, detail="No videos specified")
    if not add_tags and not remove_tags:
        raise HTTPException(status_code=400, detail="No tags to add or remove")

    videos = (
        db.query(Video)
        .filter(
            Video.id.in_(video_ids),
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .all()
    )

    if not videos:
        raise HTTPException(status_code=404, detail="No videos found")

    updated = 0
    for video in videos:
        current_tags = set(video.tags or [])
        new_tags = (current_tags | set(add_tags)) - set(remove_tags)
        if new_tags != current_tags:
            video.tags = sorted(new_tags)
            updated += 1

    db.commit()

    return {
        "updated": updated,
        "total": len(videos),
        "message": f"Updated tags on {updated} video(s)",
    }


@router.get("/{video_id}/similar", response_model=SimilarVideosResponse)
async def get_similar_videos(
    video_id: uuid.UUID,
    limit: int = Query(5, ge=1, le=20, description="Max similar videos to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Find videos similar to the given video based on shared topics.

    Uses Jaccard similarity on key_topics arrays.
    Scoped to the current user's videos only.

    Args:
        video_id: Source video UUID
        limit: Maximum number of similar videos to return

    Returns:
        SimilarVideosResponse with ranked similar videos
    """
    # Verify video exists and belongs to user
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    from app.services.theme_service import get_theme_service

    theme_service = get_theme_service()
    similar = theme_service.find_similar_videos(
        db=db,
        video_id=video_id,
        user_id=current_user.id,
        limit=limit,
    )

    return SimilarVideosResponse(
        source_video_id=video_id,
        similar_videos=similar,
    )


@router.get("/{video_id}/chunks")
async def list_video_chunks(
    video_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200, description="Search in chunk text, title, keywords"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all indexed chunks for a video with enrichment metadata.

    Returns paginated chunks with title, keywords, summary, timestamps, and token counts.
    Supports text search across chunk text, titles, and keywords.
    """
    # Verify video exists and belongs to user
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    query = db.query(Chunk).filter(Chunk.video_id == video_id)

    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            func.lower(Chunk.text).like(search_term)
            | func.lower(func.coalesce(Chunk.chunk_title, "")).like(search_term)
            | func.lower(func.coalesce(Chunk.chunk_summary, "")).like(search_term)
        )

    total = query.count()

    chunks = (
        query.order_by(Chunk.chunk_index.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Calculate average token count
    avg_tokens = 0
    if total > 0:
        avg_result = (
            db.query(func.avg(Chunk.token_count))
            .filter(Chunk.video_id == video_id)
            .scalar()
        )
        avg_tokens = int(avg_result) if avg_result else 0

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "avg_token_count": avg_tokens,
        "chunks": [
            {
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text[:300] if chunk.text else "",
                "full_text": chunk.text if search else None,  # Only return full text when searching
                "chunk_title": chunk.chunk_title,
                "keywords": chunk.keywords,
                "chunk_summary": chunk.chunk_summary,
                "token_count": chunk.token_count,
                "start_timestamp": chunk.start_timestamp,
                "end_timestamp": chunk.end_timestamp,
                "chapter_title": chunk.chapter_title,
                "speakers": chunk.speakers,
                "page_number": getattr(chunk, "page_number", None),
                "section_heading": getattr(chunk, "section_heading", None),
            }
            for chunk in chunks
        ],
    }
