"""
Celery tasks for automatic cleanup of stale/orphaned data.

Tasks:
- cleanup_stale_videos: Cancel videos stuck in processing for too long
- cleanup_orphaned_files: Remove files without matching video records
"""

from datetime import datetime, timedelta
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.base import SessionLocal
from app.models import Video
from app.services.job_cancellation import (
    cancel_video_processing,
    CleanupOption,
    CANCELABLE_STATUSES,
)


# How long a video can be in pending/downloading before auto-cancel (hours)
STALE_THRESHOLD_HOURS = 24


@celery_app.task
def cleanup_stale_videos():
    """
    Hourly task to clean up videos stuck in processing for too long.

    Cancels videos that have been in pending/downloading status for more than 24 hours.
    These are likely failed or stuck jobs that didn't properly update their status.
    """
    db = SessionLocal()

    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=STALE_THRESHOLD_HOURS)

        # Find videos stuck in early processing stages
        stale_videos = (
            db.query(Video)
            .filter(
                Video.status.in_(["pending", "downloading"]),
                Video.created_at < cutoff_time,
                Video.is_deleted.is_(False),
            )
            .all()
        )

        if not stale_videos:
            print("[cleanup] No stale videos found")
            return {"canceled": 0, "message": "No stale videos found"}

        canceled_count = 0
        errors = []

        for video in stale_videos:
            try:
                hours_old = (datetime.utcnow() - video.created_at).total_seconds() / 3600
                print(
                    f"[cleanup] Canceling stale video {video.id} "
                    f"(status={video.status}, age={hours_old:.1f}h)"
                )

                result = cancel_video_processing(
                    db, video, CleanupOption.KEEP_VIDEO
                )

                if result.error:
                    errors.append(f"{video.id}: {result.error}")
                else:
                    canceled_count += 1

            except Exception as e:
                errors.append(f"{video.id}: {str(e)}")
                print(f"[cleanup] Error canceling stale video {video.id}: {e}")

        print(
            f"[cleanup] Stale videos cleanup complete: "
            f"canceled={canceled_count}, errors={len(errors)}"
        )

        return {
            "canceled": canceled_count,
            "total_stale": len(stale_videos),
            "errors": errors if errors else None,
        }

    except Exception as e:
        print(f"[cleanup] Stale videos cleanup task failed: {e}")
        raise

    finally:
        db.close()


@celery_app.task
def cleanup_orphaned_files():
    """
    Periodic task to clean up orphaned files that don't have matching video records.

    Scans the storage directories and removes files for videos that no longer exist.
    This handles edge cases where video records were deleted but files remain.
    """
    db = SessionLocal()

    try:
        storage_path = Path(settings.local_storage_path)
        audio_path = storage_path / "audio"
        transcript_path = storage_path / "transcripts"

        orphaned_audio_count = 0
        orphaned_transcript_count = 0
        freed_bytes = 0

        # Scan audio directory
        if audio_path.exists():
            for user_dir in audio_path.iterdir():
                if not user_dir.is_dir():
                    continue

                for video_dir in user_dir.iterdir():
                    if not video_dir.is_dir():
                        continue

                    try:
                        video_id = video_dir.name
                        # Check if video exists in DB
                        video = (
                            db.query(Video)
                            .filter(Video.id == video_id)
                            .first()
                        )

                        if not video:
                            # Orphaned - remove
                            dir_size = sum(
                                f.stat().st_size for f in video_dir.rglob("*") if f.is_file()
                            )
                            import shutil
                            shutil.rmtree(video_dir)
                            orphaned_audio_count += 1
                            freed_bytes += dir_size
                            print(f"[cleanup] Removed orphaned audio dir: {video_dir}")
                    except Exception as e:
                        print(f"[cleanup] Error checking audio dir {video_dir}: {e}")

        # Scan transcript directory
        if transcript_path.exists():
            for user_dir in transcript_path.iterdir():
                if not user_dir.is_dir():
                    continue

                for video_dir in user_dir.iterdir():
                    if not video_dir.is_dir():
                        continue

                    try:
                        video_id = video_dir.name
                        video = (
                            db.query(Video)
                            .filter(Video.id == video_id)
                            .first()
                        )

                        if not video:
                            dir_size = sum(
                                f.stat().st_size for f in video_dir.rglob("*") if f.is_file()
                            )
                            import shutil
                            shutil.rmtree(video_dir)
                            orphaned_transcript_count += 1
                            freed_bytes += dir_size
                            print(f"[cleanup] Removed orphaned transcript dir: {video_dir}")
                    except Exception as e:
                        print(f"[cleanup] Error checking transcript dir {video_dir}: {e}")

        freed_mb = freed_bytes / (1024 * 1024)
        print(
            f"[cleanup] Orphaned files cleanup complete: "
            f"audio_dirs={orphaned_audio_count}, "
            f"transcript_dirs={orphaned_transcript_count}, "
            f"freed_mb={freed_mb:.2f}"
        )

        return {
            "orphaned_audio_dirs": orphaned_audio_count,
            "orphaned_transcript_dirs": orphaned_transcript_count,
            "freed_mb": round(freed_mb, 2),
        }

    except Exception as e:
        print(f"[cleanup] Orphaned files cleanup task failed: {e}")
        raise

    finally:
        db.close()
