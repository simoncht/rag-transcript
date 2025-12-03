"""
Celery tasks for video processing pipeline.

Tasks:
- download_youtube_audio: Download audio from YouTube
- transcribe_audio: Transcribe audio with Whisper
- chunk_and_enrich: Chunk transcript and add contextual enrichment
- embed_and_index: Generate embeddings and index in vector store
- process_video_pipeline: Orchestrate full pipeline
"""
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.base import SessionLocal
from app.models import Video, Transcript, Chunk, Job
from app.services.youtube import youtube_service, YouTubeDownloadError
from app.services.transcription import transcription_service
from app.services.chunking import TranscriptChunker, TranscriptSegment
from app.services.enrichment import ContextualEnricher
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store_service
from app.services.storage import storage_service
from app.core.config import settings


def update_video_status(db: Session, video_id: UUID, status: str, progress: float, error: str = None):
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


def update_job_status(db: Session, job_id: UUID, status: str, progress: float, current_step: str = None, error: str = None):
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
    db = SessionLocal()
    video_uuid = UUID(video_id)
    user_uuid = UUID(user_id)

    try:
        # Update status
        update_video_status(db, video_uuid, "downloading", 10.0)

        # Progress callback
        def progress_callback(progress_dict):
            if progress_dict["status"] == "downloading":
                downloaded = progress_dict.get("downloaded_bytes", 0)
                total = progress_dict.get("total_bytes", 1)
                percent = min(90, 10 + (downloaded / total) * 80) if total > 0 else 10
                update_video_status(db, video_uuid, "downloading", percent)

        # Download audio
        audio_path, file_size_mb = youtube_service.download_audio(
            url=youtube_url,
            user_id=user_uuid,
            video_id=video_uuid,
            progress_callback=progress_callback
        )

        # Update video record
        video = db.query(Video).filter(Video.id == video_uuid).first()
        video.audio_file_path = audio_path
        video.audio_file_size_mb = file_size_mb
        video.status = "downloaded"
        video.progress_percent = 100.0
        db.commit()

        return {
            "audio_path": audio_path,
            "file_size_mb": file_size_mb
        }

    except YouTubeDownloadError as e:
        update_video_status(db, video_uuid, "failed", 0.0, str(e))
        raise

    except Exception as e:
        # Retry on unexpected errors
        update_video_status(db, video_uuid, "failed", 0.0, f"Download failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)  # Retry after 1 minute

    finally:
        db.close()


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
    db = SessionLocal()
    video_uuid = UUID(video_id)

    try:
        # Update status
        update_video_status(db, video_uuid, "transcribing", 10.0)

        # Get video for context
        video = db.query(Video).filter(Video.id == video_uuid).first()

        # Progress callback
        def progress_callback(progress_dict):
            status = progress_dict.get("status")
            if status == "transcribing":
                update_video_status(db, video_uuid, "transcribing", 50.0, None)
            elif status == "processing":
                update_video_status(db, video_uuid, "transcribing", 80.0, None)

        # Transcribe
        result = transcription_service.transcribe_file(
            audio_path=audio_path,
            progress_callback=progress_callback
        )

        # Save transcript to database
        transcript = Transcript(
            video_id=video_uuid,
            full_text=result.full_text,
            segments=[
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": seg.speaker
                }
                for seg in result.segments
            ],
            language=result.language,
            word_count=result.word_count,
            duration_seconds=int(result.duration_seconds),
            has_speaker_labels=any(seg.speaker for seg in result.segments)
        )
        db.add(transcript)

        # Update video
        video.transcription_language = result.language
        video.status = "transcribed"
        video.progress_percent = 100.0
        db.commit()

        # Save transcript to storage
        transcript_data = {
            "full_text": result.full_text,
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": seg.speaker
                }
                for seg in result.segments
            ],
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "word_count": result.word_count
        }
        storage_service.save_transcript(video.user_id, video_uuid, transcript_data)

        # Optionally delete audio file after transcription
        if settings.cleanup_audio_after_transcription:
            storage_service.delete_audio(video.user_id, video_uuid)

        return {
            "transcript_id": str(transcript.id),
            "language": result.language,
            "word_count": result.word_count,
            "segment_count": len(result.segments)
        }

    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Transcription failed: {str(e)}")
        raise self.retry(exc=e, countdown=120)  # Retry after 2 minutes

    finally:
        db.close()


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
    db = SessionLocal()
    video_uuid = UUID(video_id)
    transcript_uuid = UUID(transcript_id)

    try:
        # Update status
        update_video_status(db, video_uuid, "chunking", 10.0)

        # Get video and transcript
        video = db.query(Video).filter(Video.id == video_uuid).first()
        transcript = db.query(Transcript).filter(Transcript.id == transcript_uuid).first()

        # Convert segments to TranscriptSegment objects
        segments = [
            TranscriptSegment(
                text=seg["text"],
                start=seg["start"],
                end=seg["end"],
                speaker=seg.get("speaker")
            )
            for seg in transcript.segments
        ]

        # Chunk transcript
        chunker = TranscriptChunker()
        chunks = chunker.chunk_transcript(segments, video.chapters)

        update_video_status(db, video_uuid, "chunking", 40.0)

        # Enrich chunks
        enricher = ContextualEnricher()
        enricher.set_video_context(video.title, video.description)

        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            enriched = enricher.enrich_chunk(chunk)
            enriched_chunks.append(enriched)

            # Update progress
            progress = 40.0 + (i + 1) / len(chunks) * 50.0
            update_video_status(db, video_uuid, "enriching", progress)

        # Save chunks to database
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
                enriched_at=datetime.utcnow()
            )
            db.add(db_chunk)

        # Update video
        video.chunk_count = len(enriched_chunks)
        video.status = "chunked"
        video.progress_percent = 90.0
        db.commit()

        return {
            "chunk_count": len(enriched_chunks)
        }

    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Chunking failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()


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
    db = SessionLocal()
    video_uuid = UUID(video_id)
    user_uuid = UUID(user_id)

    try:
        # Update status
        update_video_status(db, video_uuid, "indexing", 10.0)

        # Get chunks
        chunks = db.query(Chunk).filter(
            Chunk.video_id == video_uuid,
            Chunk.is_indexed == False
        ).order_by(Chunk.chunk_index).all()

        if not chunks:
            update_video_status(db, video_uuid, "completed", 100.0)
            return {"indexed_count": 0}

        # Prepare embedding texts
        embedding_texts = [chunk.embedding_text or chunk.text for chunk in chunks]

        # Generate embeddings in batches
        embeddings = embedding_service.embed_batch(embedding_texts, show_progress=False)

        update_video_status(db, video_uuid, "indexing", 60.0)

        # Convert chunks to EnrichedChunk format for vector store
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
                chunk_index=db_chunk.chunk_index
            )

            enriched = EnrichedChunk(
                chunk=chunk_data,
                summary=db_chunk.chunk_summary,
                title=db_chunk.chunk_title,
                keywords=db_chunk.keywords
            )
            enriched_chunks.append(enriched)

        # Initialize vector store if needed
        vector_store_service.initialize(embedding_service.get_dimensions())

        # Index in vector store
        vector_store_service.index_video_chunks(
            enriched_chunks=enriched_chunks,
            embeddings=embeddings,
            user_id=user_uuid,
            video_id=video_uuid
        )

        # Mark chunks as indexed
        for chunk in chunks:
            chunk.is_indexed = True
            chunk.indexed_at = datetime.utcnow()

        # Update video
        video = db.query(Video).filter(Video.id == video_uuid).first()
        video.status = "completed"
        video.progress_percent = 100.0
        video.completed_at = datetime.utcnow()
        db.commit()

        return {"indexed_count": len(chunks)}

    except Exception as e:
        update_video_status(db, video_uuid, "failed", 0.0, f"Indexing failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()


@celery_app.task
def process_video_pipeline(video_id: str, youtube_url: str, user_id: str, job_id: str):
    """
    Orchestrate the full video processing pipeline.

    Pipeline:
    1. Download audio
    2. Transcribe
    3. Chunk and enrich
    4. Embed and index

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

        # Step 1: Download audio
        update_job_status(db, UUID(job_id), "running", 10.0, "Downloading audio")
        download_result = download_youtube_audio(video_id, youtube_url, user_id)

        # Step 2: Transcribe
        update_job_status(db, UUID(job_id), "running", 30.0, "Transcribing audio")
        transcribe_result = transcribe_audio(video_id, download_result["audio_path"])

        # Step 3: Chunk and enrich
        update_job_status(db, UUID(job_id), "running", 60.0, "Chunking and enriching")
        chunk_result = chunk_and_enrich(video_id, transcribe_result["transcript_id"])

        # Step 4: Embed and index
        update_job_status(db, UUID(job_id), "running", 90.0, "Generating embeddings and indexing")
        index_result = embed_and_index(video_id, user_id)

        # Complete
        update_job_status(db, UUID(job_id), "completed", 100.0, "Pipeline completed")

        return {
            "status": "completed",
            "chunk_count": chunk_result["chunk_count"],
            "indexed_count": index_result["indexed_count"]
        }

    except Exception as e:
        update_job_status(db, UUID(job_id), "failed", 0.0, None, str(e))
        raise

    finally:
        db.close()
