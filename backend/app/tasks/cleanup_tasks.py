"""
Celery tasks for automatic cleanup of stale/orphaned data.

Tasks:
- cleanup_stale_videos: Cancel videos stuck in processing for too long
- cleanup_orphaned_files: Remove files without matching video records
- consolidate_conversation_memory: Prune and deduplicate conversation facts
"""

from datetime import datetime, timedelta
from pathlib import Path

from decimal import Decimal

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.base import SessionLocal
from app.models import Video, User, UserQuota, Chunk
from app.services.job_cancellation import (
    cancel_video_processing,
    CleanupOption,
    CANCELABLE_STATUSES,
)
from app.services.storage_calculator import StorageCalculator
from app.services.storage import storage_service


# How long a video can be in pending/downloading before auto-cancel (hours)
STALE_THRESHOLD_HOURS = 24

# How long since last message before consolidating conversation memory (hours)
MEMORY_CONSOLIDATION_STALE_HOURS = 24


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


# Threshold for quota discrepancy correction (MB)
QUOTA_DISCREPANCY_THRESHOLD_MB = 10.0


@celery_app.task
def reconcile_storage_quotas():
    """
    Daily task to reconcile quota storage with actual usage.

    Fixes discrepancies between tracked quota storage_mb_used and actual storage
    (disk files + database text + vectors). This handles drift from:
    - Cleanup operations that didn't update quotas
    - Manual database modifications
    - Edge cases in storage tracking

    Only corrects discrepancies larger than QUOTA_DISCREPANCY_THRESHOLD_MB (10 MB)
    to avoid unnecessary database churn.
    """
    db = SessionLocal()

    try:
        # First, clean up orphaned chunks from soft-deleted videos
        # This prevents drift where chunks remain after video soft-deletion
        orphaned_chunk_count = (
            db.query(Chunk)
            .filter(
                Chunk.video_id.in_(
                    db.query(Video.id).filter(Video.is_deleted.is_(True))
                )
            )
            .delete(synchronize_session=False)
        )
        if orphaned_chunk_count > 0:
            db.commit()
            print(
                f"[reconcile] Deleted {orphaned_chunk_count} orphaned chunks "
                "from soft-deleted videos"
            )

        # Get all user quotas
        quotas = db.query(UserQuota).all()

        if not quotas:
            print("[reconcile] No user quotas found")
            return {"users_checked": 0, "corrections": 0}

        corrections_made = 0
        users_checked = 0
        discrepancies = []

        for quota in quotas:
            users_checked += 1

            try:
                # Calculate actual comprehensive storage
                calculator = StorageCalculator(db)
                storage_breakdown = calculator.calculate_total_storage_mb(quota.user_id)

                # Disk usage from storage service
                disk_usage_mb = storage_service.get_storage_usage(quota.user_id)

                # Total = disk files + database text + vectors
                actual_storage = disk_usage_mb + storage_breakdown["database_mb"] + storage_breakdown["vector_mb"]

                # Get tracked storage
                tracked_storage = float(quota.storage_mb_used)

                # Calculate discrepancy
                discrepancy = abs(actual_storage - tracked_storage)

                # Only correct if discrepancy exceeds threshold
                if discrepancy > QUOTA_DISCREPANCY_THRESHOLD_MB:
                    user = db.query(User).filter(User.id == quota.user_id).first()
                    user_email = user.email if user else str(quota.user_id)

                    discrepancies.append({
                        "user_id": str(quota.user_id),
                        "user_email": user_email,
                        "tracked_mb": round(tracked_storage, 2),
                        "actual_mb": round(actual_storage, 2),
                        "discrepancy_mb": round(discrepancy, 2),
                        "breakdown": {
                            "disk_mb": round(disk_usage_mb, 2),
                            "database_mb": round(storage_breakdown["database_mb"], 2),
                            "vector_mb": round(storage_breakdown["vector_mb"], 2),
                        },
                    })

                    # Apply correction
                    quota.storage_mb_used = Decimal(str(round(actual_storage, 3)))
                    corrections_made += 1

                    print(
                        f"[reconcile] Corrected user {user_email}: "
                        f"{tracked_storage:.2f} MB -> {actual_storage:.2f} MB "
                        f"(delta: {discrepancy:.2f} MB)"
                    )

            except Exception as e:
                print(f"[reconcile] Error processing user {quota.user_id}: {e}")

        # Commit all corrections at once
        if corrections_made > 0:
            db.commit()

        print(
            f"[reconcile] Storage quota reconciliation complete: "
            f"checked={users_checked}, corrections={corrections_made}"
        )

        return {
            "users_checked": users_checked,
            "corrections": corrections_made,
            "threshold_mb": QUOTA_DISCREPANCY_THRESHOLD_MB,
            "discrepancies": discrepancies if discrepancies else None,
        }

    except Exception as e:
        print(f"[reconcile] Storage quota reconciliation task failed: {e}")
        raise

    finally:
        db.close()


@celery_app.task
def consolidate_conversation_memory():
    """
    Daily task to consolidate and prune conversation facts.

    Based on OpenAI/Anthropic memory best practices:
    - Deduplicates semantically similar facts
    - Applies decay to old, unused facts
    - Prunes low-importance facts when conversations have too many

    Only processes conversations that haven't been active in the last 24 hours
    to avoid interfering with active sessions.
    """
    db = SessionLocal()

    try:
        from app.services.memory_consolidation import memory_consolidation_service

        stats = memory_consolidation_service.consolidate_all_stale(
            db=db,
            stale_hours=MEMORY_CONSOLIDATION_STALE_HOURS,
            dry_run=False,
        )

        print(
            f"[memory] Consolidation complete: "
            f"conversations={stats['conversations']}, "
            f"merged={stats['merged']}, "
            f"decayed={stats['decayed']}, "
            f"pruned={stats['pruned']}"
        )

        return stats

    except Exception as e:
        print(f"[memory] Conversation memory consolidation task failed: {e}")
        raise

    finally:
        db.close()
