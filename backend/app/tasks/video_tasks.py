"""
Celery tasks for video processing pipeline.

Tasks:
- download_youtube_audio: Download audio from YouTube
- transcribe_audio: Transcribe audio with Whisper
- chunk_and_enrich: Chunk transcript and add contextual enrichment
- embed_and_index: Generate embeddings and index in vector store
- process_video_pipeline: Orchestrate full pipeline
"""
import threading
import time
import logging
from uuid import UUID
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.celery_app import celery_app
from app.db.base import SessionLocal
from app.models import Video, Transcript, Chunk, Job
from app.services.youtube import youtube_service, YouTubeDownloadError
from app.services.transcription import TranscriptionService
from app.services.chunking import TranscriptChunker, TranscriptSegment
from app.services.enrichment import ContextualEnricher
from app.services.embeddings import (
    embedding_service,
    resolve_collection_name,
    set_active_embedding_model,
)
from app.services.vector_store import vector_store_service
from app.services.storage import storage_service
from app.services.usage_tracker import UsageTracker, QuotaExceededError
from app.core.config import settings
from app.services.job_cancellation import check_if_canceled


def _create_transcript_from_captions(video_id: str, caption_data: dict):
    """
    Create transcript record from extracted YouTube captions.

    This is the fast path - no audio download or Whisper transcription needed.
    Typically completes in 1-4 seconds vs 15-90 seconds for Whisper.

    Args:
        video_id: Video UUID string
        caption_data: Caption data from youtube_service.get_captions()

    Returns:
        Dict with transcript_id and metadata
    """
    db = SessionLocal()
    video_uuid = UUID(video_id)

    try:
        logger.info(f"[Pipeline] Creating transcript from captions for video={video_id}")
        update_video_status(db, video_uuid, "transcribing", 50.0)

        video = db.query(Video).filter(Video.id == video_uuid).first()

        # Create transcript record
        transcript = Transcript(
            video_id=video_uuid,
            full_text=caption_data["full_text"],
            segments=caption_data["segments"],
            language=caption_data["language"],
            word_count=caption_data["word_count"],
            duration_seconds=int(caption_data["duration_seconds"]),
            has_speaker_labels=False,  # Captions typically don't have speaker labels
        )
        db.add(transcript)

        # Update video with transcript source
        video.transcription_language = caption_data["language"]
        video.transcript_source = "captions"
        video.status = "transcribed"
        video.progress_percent = 100.0
        db.commit()

        # Save transcript to storage
        transcript_data = {
            "full_text": caption_data["full_text"],
            "segments": caption_data["segments"],
            "language": caption_data["language"],
            "duration_seconds": caption_data["duration_seconds"],
            "word_count": caption_data["word_count"],
            "source": "captions",
        }
        transcript_path = storage_service.save_transcript(
            video.user_id, video_uuid, transcript_data
        )
        video.transcript_file_path = transcript_path
        db.commit()

        logger.info(
            f"[Pipeline] Caption-based transcript created for video={video_id}, "
            f"segments={len(caption_data['segments'])}, words={caption_data['word_count']}"
        )

        return {
            "transcript_id": str(transcript.id),
            "language": caption_data["language"],
            "word_count": caption_data["word_count"],
            "segment_count": len(caption_data["segments"]),
            "source": "captions",
        }

    except Exception as e:
        update_video_status(
            db, video_uuid, "failed", 0.0, f"Caption processing failed: {str(e)}"
        )
        raise
    finally:
        db.close()


def update_video_status(
    db: Session, video_id: UUID, status: str, progress: float, error: str = None
):
    """Helper to update video processing status."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        video.status = status
        video.progress_percent = progress
        if error:
            video.error_message = error
        if status == "completed":
            video.completed_at = datetime.utcnow()
        db.commit()


def update_job_status(
    db: Session,
    job_id: UUID,
    status: str,
    progress: float,
    current_step: str = None,
    error: str = None,
):
    """Helper to update job status."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = status
        job.progress_percent = progress
        if current_step:
            job.current_step = current_step
        if error:
            job.error_message = error
        if status == "running" and not job.started_at:
            job.started_at = datetime.utcnow()
        if status in ["completed", "failed"]:
            job.completed_at = datetime.utcnow()
        db.commit()


def _download_youtube_audio(video_id: str, youtube_url: str, user_id: str):
    """Internal helper to download audio (used by Celery task and sync pipeline)."""
    db = SessionLocal()
    video_uuid = UUID(video_id)
    user_uuid = UUID(user_id)
    usage_tracker = UsageTracker(db)

    try:
        print(f"[pipeline] Download start for video={video_id}")
        update_video_status(db, video_uuid, "downloading", 10.0)

        def progress_callback(progress_dict):
            if progress_dict["status"] == "downloading":
                downloaded = progress_dict.get("downloaded_bytes", 0)
                total = progress_dict.get("total_bytes", 1)
                percent = min(90, 10 + (downloaded / total) * 80) if total > 0 else 10
                update_video_status(db, video_uuid, "downloading", percent)

        audio_path, file_size_mb = youtube_service.download_audio(
            url=youtube_url,
            user_id=user_uuid,
            video_id=video_uuid,
            progress_callback=progress_callback,
        )

        video = db.query(Video).filter(Video.id == video_uuid).first()
        video.audio_file_path = audio_path
        video.audio_file_size_mb = file_size_mb
        video.status = "downloaded"
        video.progress_percent = 100.0
        db.commit()

        # Track download/storage usage now that we know the file size
        try:
            usage_tracker.check_quota(user_uuid, "storage", file_size_mb)
        except Exception:
            # Quota check failure should stop the pipeline
            raise

        try:
            usage_tracker.track_video_ingestion(
                user_uuid,
                video_uuid,
                video.duration_seconds or 0,
                file_size_mb,
            )
        except Exception as e:
            print(f"[usage] Failed to track ingestion for video={video_id}: {e}")

        print(
            f"[pipeline] Download complete for video={video_id}, size_mb={file_size_mb}"
        )
        return {"audio_path": audio_path, "file_size_mb": file_size_mb}
    except QuotaExceededError as e:
        update_video_status(
            db, video_uuid, "failed", 0.0, f"Storage quota exceeded: {str(e)}"
        )
        try:
            storage_service.delete_audio(user_uuid, video_uuid)
        except Exception:
            pass
        raise
    except YouTubeDownloadError as e:
        update_video_status(db, video_uuid, "failed", 0.0, str(e))
        raise
    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Download failed: {str(e)}")
        raise
    finally:
        db.close()


def _transcribe_audio(video_id: str, audio_path: str):
    """Internal helper to transcribe audio synchronously."""
    db = SessionLocal()
    video_uuid = UUID(video_id)
    usage_tracker = UsageTracker(db)

    try:
        print(
            f"[pipeline] Transcription start for video={video_id}, audio={audio_path}"
        )
        update_video_status(db, video_uuid, "transcribing", 10.0)

        video = db.query(Video).filter(Video.id == video_uuid).first()

        def progress_callback(progress_dict):
            status = progress_dict.get("status")
            if status == "transcribing":
                update_video_status(db, video_uuid, "transcribing", 50.0, None)
            elif status == "processing":
                update_video_status(db, video_uuid, "transcribing", 80.0, None)

        # Start heartbeat thread to update updated_at and simulate progress every 30 seconds
        # This signals to the frontend that the process is still alive
        heartbeat_active = threading.Event()
        heartbeat_active.set()
        heartbeat_start_time = datetime.utcnow()
        # Estimate: transcription takes ~2x video duration on CPU
        estimated_total_seconds = (video.duration_seconds or 3600) * 2

        def heartbeat_worker():
            """Update timestamp and simulate progress every 30 seconds."""
            while heartbeat_active.is_set():
                try:
                    db_heartbeat = SessionLocal()
                    v = db_heartbeat.query(Video).filter(Video.id == video_uuid).first()
                    if v and v.status == "transcribing":
                        v.updated_at = datetime.utcnow()
                        # Simulate progress: 10% to 85% based on elapsed time
                        elapsed = (datetime.utcnow() - heartbeat_start_time).total_seconds()
                        simulated_progress = min(85, 10 + (elapsed / estimated_total_seconds) * 75)
                        v.progress_percent = simulated_progress
                        db_heartbeat.commit()
                        logger.info(f"[heartbeat] video={video_id} progress={simulated_progress:.1f}%")
                    db_heartbeat.close()
                except Exception as e:
                    logger.warning(f"[heartbeat] Error: {e}")
                # Sleep in small increments to allow quick shutdown
                for _ in range(30):
                    if not heartbeat_active.is_set():
                        break
                    time.sleep(1)

        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()

        try:
            # Create a fresh transcription service per process to avoid fork-safety issues
            local_transcription_service = TranscriptionService()
            result = local_transcription_service.transcribe_file(
                audio_path=audio_path, progress_callback=progress_callback
            )
        finally:
            # Stop heartbeat thread
            heartbeat_active.clear()
            heartbeat_thread.join(timeout=5)
            logger.info(f"[heartbeat] Stopped for video={video_id}")

        transcript = Transcript(
            video_id=video_uuid,
            full_text=result.full_text,
            segments=[
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": seg.speaker,
                }
                for seg in result.segments
            ],
            language=result.language,
            word_count=result.word_count,
            duration_seconds=int(result.duration_seconds),
            has_speaker_labels=any(seg.speaker for seg in result.segments),
        )
        db.add(transcript)

        video.transcription_language = result.language
        video.transcript_source = "whisper"
        video.status = "transcribed"
        video.progress_percent = 100.0
        db.commit()

        transcript_data = {
            "full_text": result.full_text,
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": seg.speaker,
                }
                for seg in result.segments
            ],
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "word_count": result.word_count,
        }
        transcript_path = storage_service.save_transcript(
            video.user_id, video_uuid, transcript_data
        )
        video.transcript_file_path = transcript_path
        db.commit()

        transcript_size_mb = 0.0
        try:
            transcript_size_mb = Path(transcript_path).stat().st_size / (1024 * 1024)
            usage_tracker.track_storage_usage(
                video.user_id,
                transcript_size_mb,
                reason="transcript_saved",
                video_id=video_uuid,
                extra_metadata={"segments": len(result.segments)},
            )
        except Exception as e:
            print(
                f"[usage] Failed to track transcript storage for video={video_id}: {e}"
            )

        if settings.cleanup_audio_after_transcription:
            audio_removed = storage_service.delete_audio(video.user_id, video_uuid)
            try:
                if audio_removed and video.audio_file_size_mb:
                    usage_tracker.track_storage_usage(
                        video.user_id,
                        -video.audio_file_size_mb,
                        reason="audio_cleaned",
                        video_id=video_uuid,
                    )
            except Exception as e:
                print(
                    f"[usage] Failed to track audio cleanup for video={video_id}: {e}"
                )

        try:
            usage_tracker.track_transcription(
                video.user_id,
                video_uuid,
                result.duration_seconds,
                len(result.segments),
                getattr(result, "model", None) or "whisper",
            )
        except Exception as e:
            print(
                f"[usage] Failed to track transcription event for video={video_id}: {e}"
            )

        print(f"[pipeline] Transcription complete for video={video_id}")

        return {
            "transcript_id": str(transcript.id),
            "language": result.language,
            "word_count": result.word_count,
            "segment_count": len(result.segments),
        }
    except Exception as e:
        update_video_status(
            db, video_uuid, "failed", 0.0, f"Transcription failed: {str(e)}"
        )
        raise
    finally:
        db.close()


def _chunk_and_enrich(video_id: str, transcript_id: str):
    """Internal helper to chunk and enrich transcript."""
    db = SessionLocal()
    video_uuid = UUID(video_id)
    transcript_uuid = UUID(transcript_id)

    try:
        print(f"[pipeline] Chunk/enrich start for video={video_id}")
        update_video_status(db, video_uuid, "chunking", 10.0)

        video = db.query(Video).filter(Video.id == video_uuid).first()
        transcript = (
            db.query(Transcript).filter(Transcript.id == transcript_uuid).first()
        )

        segments = [
            TranscriptSegment(
                text=seg["text"],
                start=seg["start"],
                end=seg["end"],
                speaker=seg.get("speaker"),
            )
            for seg in transcript.segments
        ]

        chunker = TranscriptChunker()
        chunks = chunker.chunk_transcript(segments, video.chapters)

        if not chunks and segments:
            # Fallback: short clips can be one chunk when chapter splits are tiny
            chunks = [chunker.create_chunk_from_segments(segments, chunk_index=0)]

        update_video_status(db, video_uuid, "chunking", 40.0)

        enricher = ContextualEnricher()
        enricher.set_video_context(video.title, video.description)
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            enriched = enricher.enrich_chunk(chunk)
            enriched_chunks.append(enriched)

            progress = 40.0 + (i + 1) / len(chunks) * 50.0
            update_video_status(db, video_uuid, "enriching", progress)

        for enriched_chunk in enriched_chunks:
            chunk = enriched_chunk.chunk
            db_chunk = Chunk(
                video_id=video_uuid,
                user_id=video.user_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
                duration_seconds=chunk.duration_seconds,
                speakers=chunk.speakers,
                chapter_title=chunk.chapter_title,
                chapter_index=chunk.chapter_index,
                chunk_summary=enriched_chunk.summary,
                chunk_title=enriched_chunk.title,
                keywords=enriched_chunk.keywords,
                embedding_text=enriched_chunk.embedding_text,
                enriched_at=datetime.utcnow(),
            )
            db.add(db_chunk)

        video.chunk_count = len(enriched_chunks)
        video.status = "chunked"
        video.progress_percent = 90.0
        db.commit()

        print(
            f"[pipeline] Chunk/enrich complete for video={video_id}, chunks={len(enriched_chunks)}"
        )
        return {"chunk_count": len(enriched_chunks)}
    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Chunking failed: {str(e)}")
        raise
    finally:
        db.close()


def _embed_and_index(video_id: str, user_id: str, force_reindex: bool = False):
    """Internal helper to embed and index chunks."""
    db = SessionLocal()
    video_uuid = UUID(video_id)
    user_uuid = UUID(user_id)
    usage_tracker = UsageTracker(db)

    try:
        print(f"[pipeline] Embed/index start for video={video_id}")
        update_video_status(db, video_uuid, "indexing", 10.0)

        query = db.query(Chunk).filter(Chunk.video_id == video_uuid)
        if not force_reindex:
            query = query.filter(Chunk.is_indexed.is_(False))
        chunks = query.order_by(Chunk.chunk_index).all()

        if not chunks:
            update_video_status(db, video_uuid, "completed", 100.0)
            return {"indexed_count": 0}

        embedding_texts = [chunk.embedding_text or chunk.text for chunk in chunks]
        embeddings = embedding_service.embed_batch(embedding_texts, show_progress=False)

        update_video_status(db, video_uuid, "indexing", 60.0)

        from app.services.enrichment import EnrichedChunk
        from app.services.chunking import Chunk as ChunkData

        enriched_chunks = []
        for db_chunk in chunks:
            chunk_data = ChunkData(
                text=db_chunk.text,
                start_timestamp=db_chunk.start_timestamp,
                end_timestamp=db_chunk.end_timestamp,
                token_count=db_chunk.token_count,
                speakers=db_chunk.speakers,
                chapter_title=db_chunk.chapter_title,
                chapter_index=db_chunk.chapter_index,
                chunk_index=db_chunk.chunk_index,
            )

            enriched = EnrichedChunk(
                chunk=chunk_data,
                summary=db_chunk.chunk_summary,
                title=db_chunk.chunk_title,
                keywords=db_chunk.keywords,
            )
            enriched_chunks.append(enriched)

        collection_name = resolve_collection_name(embedding_service)

        vector_store_service.initialize(
            embedding_service.get_dimensions(),
            collection_name=collection_name,
        )

        vector_store_service.index_video_chunks(
            enriched_chunks=enriched_chunks,
            embeddings=embeddings,
            user_id=user_uuid,
            video_id=video_uuid,
        )

        for chunk in chunks:
            chunk.is_indexed = True
            chunk.indexed_at = datetime.utcnow()

        video = db.query(Video).filter(Video.id == video_uuid).first()
        video.status = "completed"
        video.progress_percent = 100.0
        video.completed_at = datetime.utcnow()
        db.commit()

        try:
            usage_tracker.track_embedding_generation(
                user_uuid,
                len(chunks),
                embedding_service.get_model_name(),
                embedding_service.get_dimensions(),
            )
        except Exception as e:
            print(f"[usage] Failed to track embedding event for video={video_id}: {e}")

        print(
            f"[pipeline] Embed/index complete for video={video_id}, indexed={len(chunks)}"
        )
        return {"indexed_count": len(chunks)}
    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Indexing failed: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def download_youtube_audio(self, video_id: str, youtube_url: str, user_id: str):
    """
    Download audio from YouTube video.

    Args:
        video_id: Video UUID
        youtube_url: YouTube URL
        user_id: User UUID

    Returns:
        Dict with audio_path and file_size_mb
    """
    try:
        return _download_youtube_audio(video_id, youtube_url, user_id)

    except QuotaExceededError as e:
        # Bubble up quota failures without retries
        raise e

    except YouTubeDownloadError:
        raise

    except Exception as e:
        # Retry on unexpected errors
        raise self.retry(exc=e, countdown=60)  # Retry after 1 minute


@celery_app.task(bind=True, max_retries=2)
def transcribe_audio(self, video_id: str, audio_path: str):
    """
    Transcribe audio file with Whisper.

    Args:
        video_id: Video UUID
        audio_path: Path to audio file

    Returns:
        Dict with transcript data
    """
    try:
        return _transcribe_audio(video_id, audio_path)

    except Exception as e:
        raise self.retry(exc=e, countdown=120)  # Retry after 2 minutes


@celery_app.task(bind=True, max_retries=2)
def chunk_and_enrich(self, video_id: str, transcript_id: str):
    """
    Chunk transcript and add contextual enrichment.

    Args:
        video_id: Video UUID
        transcript_id: Transcript UUID

    Returns:
        Dict with chunk count
    """
    try:
        return _chunk_and_enrich(video_id, transcript_id)

    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def embed_and_index(self, video_id: str, user_id: str):
    """
    Generate embeddings and index chunks in vector store.

    Args:
        video_id: Video UUID
        user_id: User UUID

    Returns:
        Dict with indexed count
    """
    try:
        return _embed_and_index(video_id, user_id)

    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=1)
def reembed_all_videos(self, model_key: str):
    """
    Re-embed and re-index all videos using the specified embedding model key.
    """
    db = SessionLocal()
    try:
        set_active_embedding_model(model_key)
        videos = db.query(Video).filter(Video.is_deleted.is_(False)).all()
        for video in videos:
            _embed_and_index(str(video.id), str(video.user_id), force_reindex=True)
        return {
            "status": "completed",
            "video_count": len(videos),
            "model_key": model_key,
        }
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


class VideoCanceledException(Exception):
    """Raised when video processing is canceled."""

    pass


def _check_canceled_or_raise(db: Session, video_id: str, job_id: str, step_name: str):
    """
    Check if video is canceled and raise exception if so.

    This is called at checkpoints between pipeline stages to allow
    graceful abort when user requests cancellation.
    """
    video_uuid = UUID(video_id)
    if check_if_canceled(db, video_uuid):
        print(f"[pipeline] Canceled at checkpoint: {step_name} job={job_id}")
        raise VideoCanceledException(f"Video processing canceled at {step_name}")


@celery_app.task
def process_video_pipeline(video_id: str, youtube_url: str, user_id: str, job_id: str):
    """
    Orchestrate the full video processing pipeline.

    Pipeline (with caption-first optimization):
    1. Try: Extract YouTube captions (fast path: 1-4s)
       OR Fallback: Download audio + Whisper transcription (15-90s)
    2. Chunk and enrich
    3. Embed and index

    Includes cancellation checkpoints between stages for graceful abort.

    Args:
        video_id: Video UUID
        youtube_url: YouTube URL
        user_id: User UUID
        job_id: Job UUID for tracking
    """
    db = SessionLocal()

    try:
        # Update job
        update_job_status(db, UUID(job_id), "running", 0.0, "Starting pipeline")

        # Checkpoint: before transcription
        _check_canceled_or_raise(db, video_id, job_id, "before_transcription")

        # Get video info to extract youtube_id
        video = db.query(Video).filter(Video.id == UUID(video_id)).first()
        youtube_id = video.youtube_id if video else youtube_service.extract_video_id(youtube_url)

        # Step 1: Try caption extraction first (fast path)
        logger.info(f"[Pipeline] Attempting caption extraction for video={video_id}")
        update_job_status(db, UUID(job_id), "running", 5.0, "Checking for captions")

        caption_data = youtube_service.get_captions(youtube_id)

        if caption_data:
            # Fast path: Use captions directly (no audio download needed)
            logger.info(f"[Pipeline] Using YouTube captions for video={video_id} (fast path)")
            update_job_status(db, UUID(job_id), "running", 10.0, "Processing captions")
            transcribe_result = _create_transcript_from_captions(video_id, caption_data)
            logger.info(f"[Pipeline] Caption-based transcription complete for video={video_id}")
        else:
            # Fallback: Download audio and transcribe with Whisper
            logger.info(f"[Pipeline] No captions available, falling back to Whisper for video={video_id}")

            # Step 1a: Download audio
            logger.info(f"[Pipeline] Step 1a: download start job={job_id}")
            update_job_status(db, UUID(job_id), "running", 10.0, "Downloading audio")
            download_result = _download_youtube_audio(video_id, youtube_url, user_id)
            logger.info(f"[Pipeline] Step 1a: download done job={job_id}")

            # Checkpoint: after download
            _check_canceled_or_raise(db, video_id, job_id, "after_download")

            # Step 1b: Transcribe with Whisper
            logger.info(f"[Pipeline] Step 1b: transcribe start job={job_id}")
            update_job_status(db, UUID(job_id), "running", 30.0, "Transcribing audio")
            transcribe_result = _transcribe_audio(video_id, download_result["audio_path"])
            logger.info(f"[Pipeline] Step 1b: transcribe done job={job_id}")

        # Checkpoint: after transcription
        _check_canceled_or_raise(db, video_id, job_id, "after_transcribe")

        # Checkpoint: after transcribe
        _check_canceled_or_raise(db, video_id, job_id, "after_transcribe")

        # Step 3: Chunk and enrich
        print(f"[pipeline] Step 3: chunk/enrich start job={job_id}")
        update_job_status(db, UUID(job_id), "running", 60.0, "Chunking and enriching")
        chunk_result = _chunk_and_enrich(video_id, transcribe_result["transcript_id"])
        print(f"[pipeline] Step 3: chunk/enrich done job={job_id}")

        # Checkpoint: after chunk/enrich
        _check_canceled_or_raise(db, video_id, job_id, "after_chunk_enrich")

        # Step 4: Embed and index
        print(f"[pipeline] Step 4: embed/index start job={job_id}")
        update_job_status(
            db, UUID(job_id), "running", 90.0, "Generating embeddings and indexing"
        )
        index_result = _embed_and_index(video_id, user_id)
        print(f"[pipeline] Step 4: embed/index done job={job_id}")

        # Complete
        update_job_status(db, UUID(job_id), "completed", 100.0, "Pipeline completed")

        return {
            "status": "completed",
            "chunk_count": chunk_result["chunk_count"],
            "indexed_count": index_result["indexed_count"],
        }

    except VideoCanceledException:
        # Graceful cancellation - don't mark as failed
        update_job_status(db, UUID(job_id), "canceled", 0.0, "Processing canceled")
        return {
            "status": "canceled",
            "message": "Video processing was canceled by user",
        }

    except Exception as e:
        update_job_status(db, UUID(job_id), "failed", 0.0, None, str(e))
        raise

    finally:
        db.close()
