"""
API endpoints for usage and quota insights.

Provides a summary of storage usage, quotas, and artifact counts
to help monitor billed usage.
"""
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import Video, Transcript, Chunk, User
from app.schemas import UsageSummary, StorageBreakdown, UsageCounts, VectorStoreStat, QuotaStat
from app.services.storage import storage_service
from app.services.usage_tracker import UsageTracker
from app.services.vector_store import vector_store_service

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


@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a usage and storage summary for the current user.
    """
    usage_tracker = UsageTracker(db)
    base_summary = usage_tracker.get_usage_summary(current_user.id)

    # Base video query (non-deleted, current user)
    video_query = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.is_deleted == False  # noqa: E712
    )

    # Audio storage from DB (MB)
    audio_mb = video_query.with_entities(func.coalesce(func.sum(Video.audio_file_size_mb), 0.0)).scalar() or 0.0

    # Transcript counts and estimated size (MB) based on text length
    transcript_query = (
        db.query(Transcript)
        .join(Video, Video.id == Transcript.video_id)
        .filter(
            Video.user_id == current_user.id,
            Video.is_deleted == False,  # noqa: E712
        )
    )
    transcripts = transcript_query.all()
    transcript_count = len(transcripts)
    transcript_mb_estimate = (
        sum(len(t.full_text.encode("utf-8")) for t in transcripts) / (1024 * 1024)
        if transcripts
        else 0.0
    )
    transcript_file_mb = 0.0
    # Prefer on-disk transcript file sizes when available
    videos_with_transcripts = video_query.filter(Video.transcript_file_path.isnot(None)).all()
    for video in videos_with_transcripts:
        path = video.transcript_file_path
        if not path:
            continue
        try:
            transcript_file_mb += Path(path).stat().st_size / (1024 * 1024)
        except Exception:
            # Fallback to DB-based estimate if file missing
            continue
    transcript_mb = transcript_file_mb if transcript_file_mb > 0 else transcript_mb_estimate

    # Chunk counts for the user
    chunk_count = db.query(func.count(Chunk.id)).filter(Chunk.user_id == current_user.id).scalar() or 0

    # Video counts by status
    video_query = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.is_deleted == False  # noqa: E712
    )
    videos_total = video_query.count()
    videos_completed = video_query.filter(Video.status == "completed").count()
    videos_processing = video_query.filter(Video.status.notin_(["completed", "failed"])).count()
    videos_failed = video_query.filter(Video.status == "failed").count()

    # Disk usage from storage service (audio + transcript files on disk)
    try:
        disk_usage_mb = storage_service.get_storage_usage(current_user.id)
    except Exception:
        disk_usage_mb = 0.0

    storage_quota = base_summary["storage_mb"]
    limit_mb = float(storage_quota["limit"])
    quota_used_mb = float(storage_quota["used"])
    measured_storage_mb = max(
        float(round(audio_mb + transcript_mb, 3)),
        float(round(disk_usage_mb, 3)),
    )
    effective_storage_used_mb = max(quota_used_mb, measured_storage_mb)
    storage_remaining_mb = max(limit_mb - effective_storage_used_mb, 0.0)
    storage_percentage = (
        (effective_storage_used_mb / limit_mb * 100) if limit_mb > 0 else 0.0
    )

    # Vector store stats (collection-wide; per-user stats not available)
    vector_stats: Optional[VectorStoreStat] = None
    try:
        stats = vector_store_service.get_stats()
        vector_stats = VectorStoreStat(
            collection_name=stats.get("collection_name", "default"),
            total_points=stats.get("total_points", 0),
            vectors_count=stats.get("vectors_count", 0),
            indexed_vectors_count=stats.get("indexed_vectors_count", 0),
        )
    except Exception:
        vector_stats = None

    return UsageSummary(
        period_start=base_summary["period_start"],
        period_end=base_summary["period_end"],
        videos=QuotaStat(**base_summary["videos"]),
        minutes=QuotaStat(**base_summary["minutes"]),
        messages=QuotaStat(**base_summary["messages"]),
        storage_mb=QuotaStat(
            used=effective_storage_used_mb,
            limit=limit_mb,
            remaining=storage_remaining_mb,
            percentage=storage_percentage,
        ),
        storage_breakdown=StorageBreakdown(
            total_mb=effective_storage_used_mb,
            limit_mb=limit_mb,
            remaining_mb=storage_remaining_mb,
            percentage=storage_percentage,
            audio_mb=float(round(audio_mb, 3)),
            transcript_mb=float(round(transcript_mb_estimate, 3)),
            disk_usage_mb=float(round(disk_usage_mb, 3)),
        ),
        counts=UsageCounts(
            videos_total=videos_total,
            videos_completed=videos_completed,
            videos_processing=videos_processing,
            videos_failed=videos_failed,
            transcripts=transcript_count,
            chunks=int(chunk_count),
        ),
        vector_store=vector_stats,
    )
