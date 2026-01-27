"""
Job cancellation service for stopping in-progress video processing and cleaning up partial data.

Handles:
- Revoking Celery tasks (soft revoke for graceful shutdown)
- Cleaning up partial data (files, DB records, vectors)
- Supporting both "keep_video" (status=canceled) and "full_delete" options
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID

from celery import current_app
from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.models import Video, Transcript, Chunk, Job
from app.services.vector_store import vector_store_service
from app.services.storage import storage_service
from app.services.storage_calculator import StorageCalculator, BYTES_PER_VECTOR


class CleanupOption(str, Enum):
    """Options for cleanup after cancellation."""

    KEEP_VIDEO = "keep_video"  # Set status to canceled, keep video record
    FULL_DELETE = "full_delete"  # Hard delete video and all related data


@dataclass
class CleanupSummary:
    """Summary of cleanup actions taken."""

    transcript_deleted: bool = False
    chunks_deleted: int = 0
    audio_file_deleted: bool = False
    transcript_file_deleted: bool = False
    vectors_deleted: bool = False
    storage_freed_mb: float = 0.0  # Total storage freed across all cleanup actions


@dataclass
class CancelResult:
    """Result of cancel operation."""

    video_id: UUID
    previous_status: str
    new_status: str
    celery_task_revoked: bool
    cleanup_summary: CleanupSummary
    error: Optional[str] = None


# Terminal statuses that cannot be canceled
TERMINAL_STATUSES = {"completed", "failed", "canceled"}

# Cancelable statuses (non-terminal)
CANCELABLE_STATUSES = {
    "pending",
    "downloading",
    "transcribing",
    "chunking",
    "enriching",
    "indexing",
}


def is_cancelable(video: Video) -> bool:
    """Check if a video can be canceled."""
    return video.status in CANCELABLE_STATUSES


def revoke_celery_task(task_id: str, terminate: bool = False) -> bool:
    """
    Revoke a Celery task.

    Args:
        task_id: The Celery task ID to revoke
        terminate: If True, forcefully terminate (SIGTERM). If False, soft revoke.

    Returns:
        True if revoke was issued, False if task not found or already finished
    """
    if not task_id:
        return False

    try:
        result = AsyncResult(task_id, app=current_app)

        # Check if task is still pending or running
        if result.state in ("PENDING", "STARTED", "RETRY"):
            # Soft revoke - task will stop at next checkpoint
            current_app.control.revoke(task_id, terminate=terminate)
            return True

        return False
    except Exception as e:
        print(f"[cancel] Error revoking task {task_id}: {e}")
        return False


def cleanup_video_data(
    db: Session,
    video: Video,
    delete_files: bool = True,
    delete_vectors: bool = True,
    delete_db_records: bool = True,
    track_quota: bool = True,
) -> CleanupSummary:
    """
    Clean up all data associated with a video and track storage freed.

    Args:
        db: Database session
        video: Video to clean up
        delete_files: Whether to delete audio/transcript files
        delete_vectors: Whether to delete vectors from Qdrant
        delete_db_records: Whether to delete transcript/chunk DB records
        track_quota: Whether to credit freed storage back to user quota

    Returns:
        CleanupSummary with details of what was deleted
    """
    from sqlalchemy import func
    from app.services.usage_tracker import UsageTracker

    summary = CleanupSummary()
    storage_freed_bytes = 0

    # Calculate chunk storage before deletion (text + summary + embedding_text)
    chunk_text_bytes = 0
    indexed_chunk_count = 0
    if delete_db_records:
        try:
            # Get total text bytes from chunks
            chunk_storage = (
                db.query(
                    func.coalesce(
                        func.sum(
                            func.length(Chunk.text)
                            + func.coalesce(func.length(Chunk.chunk_summary), 0)
                            + func.coalesce(func.length(Chunk.embedding_text), 0)
                        ),
                        0,
                    )
                )
                .filter(Chunk.video_id == video.id)
                .scalar()
                or 0
            )
            chunk_text_bytes = chunk_storage

            # Count indexed chunks for vector storage estimation
            indexed_chunk_count = (
                db.query(func.count(Chunk.id))
                .filter(Chunk.video_id == video.id, Chunk.is_indexed.is_(True))
                .scalar()
                or 0
            )
        except Exception as e:
            print(f"[cleanup] Error calculating chunk storage for video {video.id}: {e}")

    # 1. Delete vectors from Qdrant
    if delete_vectors:
        try:
            vector_store_service.delete_video(video.id)
            summary.vectors_deleted = True
            # Estimate vector storage freed
            storage_freed_bytes += indexed_chunk_count * BYTES_PER_VECTOR
        except Exception as e:
            print(f"[cleanup] Error deleting vectors for video {video.id}: {e}")

    # 2. Delete chunk records from DB
    if delete_db_records:
        try:
            chunk_count = (
                db.query(Chunk).filter(Chunk.video_id == video.id).delete(
                    synchronize_session=False
                )
            )
            summary.chunks_deleted = chunk_count
            # Add text storage freed
            storage_freed_bytes += chunk_text_bytes
        except Exception as e:
            print(f"[cleanup] Error deleting chunks for video {video.id}: {e}")

    # 3. Delete transcript record from DB
    if delete_db_records:
        try:
            transcript = (
                db.query(Transcript).filter(Transcript.video_id == video.id).first()
            )
            if transcript:
                db.delete(transcript)
                summary.transcript_deleted = True
        except Exception as e:
            print(f"[cleanup] Error deleting transcript for video {video.id}: {e}")

    # 4. Delete audio file
    if delete_files and video.audio_file_path:
        try:
            audio_path = Path(video.audio_file_path)
            if audio_path.exists():
                # Track file size before deletion
                storage_freed_bytes += audio_path.stat().st_size
                audio_path.unlink()
                summary.audio_file_deleted = True
            # Also try to remove the parent directory if empty
            if audio_path.parent.exists() and not any(audio_path.parent.iterdir()):
                audio_path.parent.rmdir()
        except Exception as e:
            print(f"[cleanup] Error deleting audio file for video {video.id}: {e}")

    # 5. Delete transcript JSON file
    if delete_files and video.transcript_file_path:
        try:
            transcript_path = Path(video.transcript_file_path)
            if transcript_path.exists():
                # Track file size before deletion
                storage_freed_bytes += transcript_path.stat().st_size
                transcript_path.unlink()
                summary.transcript_file_deleted = True
            # Also try to remove the parent directory if empty
            if transcript_path.parent.exists() and not any(
                transcript_path.parent.iterdir()
            ):
                transcript_path.parent.rmdir()
        except Exception as e:
            print(
                f"[cleanup] Error deleting transcript file for video {video.id}: {e}"
            )

    # Calculate storage freed in MB
    summary.storage_freed_mb = storage_freed_bytes / (1024 * 1024)

    # Credit freed storage back to user quota
    if track_quota and summary.storage_freed_mb > 0 and video.user_id:
        try:
            usage_tracker = UsageTracker(db)
            usage_tracker.track_storage_usage(
                user_id=video.user_id,
                delta_mb=-summary.storage_freed_mb,  # Negative = credit back
                reason="video_cleanup",
                video_id=video.id,
                extra_metadata={
                    "chunks_deleted": summary.chunks_deleted,
                    "audio_deleted": summary.audio_file_deleted,
                    "vectors_deleted": summary.vectors_deleted,
                },
            )
            print(
                f"[cleanup] Credited {summary.storage_freed_mb:.2f} MB back to user {video.user_id}"
            )
        except Exception as e:
            print(f"[cleanup] Error crediting storage back for video {video.id}: {e}")

    # Clear file path references on video
    video.audio_file_path = None
    video.audio_file_size_mb = None
    video.transcript_file_path = None
    video.chunk_count = 0

    return summary


def cancel_video_processing(
    db: Session,
    video: Video,
    cleanup_option: CleanupOption = CleanupOption.KEEP_VIDEO,
) -> CancelResult:
    """
    Cancel video processing and clean up partial data.

    Args:
        db: Database session
        video: Video to cancel
        cleanup_option: How to handle the video record after cleanup

    Returns:
        CancelResult with details of the operation
    """
    previous_status = video.status
    celery_task_revoked = False

    # Check if video is in a terminal state (re-fetch to avoid race condition)
    db.refresh(video)
    if video.status in TERMINAL_STATUSES:
        return CancelResult(
            video_id=video.id,
            previous_status=previous_status,
            new_status=video.status,
            celery_task_revoked=False,
            cleanup_summary=CleanupSummary(),
            error=f"Video is already in terminal status: {video.status}",
        )

    # Mark as canceled first to signal active tasks to stop
    video.status = "canceled"
    video.error_message = "Processing canceled by user"
    db.commit()

    # Try to revoke any active Celery task
    job = db.query(Job).filter(Job.video_id == video.id).order_by(Job.created_at.desc()).first()
    if job and job.celery_task_id:
        celery_task_revoked = revoke_celery_task(job.celery_task_id)
        if celery_task_revoked:
            job.status = "canceled"
            job.error_message = "Task revoked due to cancellation"
            db.commit()

    # Clean up all partial data
    cleanup_summary = cleanup_video_data(
        db,
        video,
        delete_files=True,
        delete_vectors=True,
        delete_db_records=True,
    )

    # Handle cleanup option
    if cleanup_option == CleanupOption.FULL_DELETE:
        # Hard delete the video record
        video.is_deleted = True
        video.deleted_at = datetime.utcnow()
        db.commit()
        new_status = "deleted"
    else:
        # Keep video with canceled status
        video.progress_percent = 0.0
        db.commit()
        new_status = "canceled"

    return CancelResult(
        video_id=video.id,
        previous_status=previous_status,
        new_status=new_status,
        celery_task_revoked=celery_task_revoked,
        cleanup_summary=cleanup_summary,
    )


def check_if_canceled(db: Session, video_id: UUID) -> bool:
    """
    Check if a video has been marked as canceled.

    This is called by pipeline tasks at checkpoints to gracefully abort.

    Args:
        db: Database session
        video_id: Video ID to check

    Returns:
        True if video status is "canceled"
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        return True  # Video doesn't exist, treat as canceled

    return video.status == "canceled"
