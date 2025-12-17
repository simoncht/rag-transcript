from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Chunk, Transcript, Video
from app.services.vector_store import vector_store_service


def reset_video_processing(
    db: Session,
    *,
    video: Video,
    delete_files: bool = True,
    delete_vectors: bool = True,
) -> None:
    """
    Reset a video's derived artifacts so the full pipeline can be rerun.

    This clears DB transcript/chunks (to avoid unique constraints / duplicates),
    optionally deletes local transcript/audio artifacts, and removes vector index
    entries for the video.
    """
    transcript = db.query(Transcript).filter(Transcript.video_id == video.id).first()
    if transcript:
        db.delete(transcript)

    db.query(Chunk).filter(Chunk.video_id == video.id).delete(synchronize_session=False)

    if delete_vectors:
        try:
            vector_store_service.delete_video(video.id)
        except Exception:
            pass

    if delete_files:
        for file_path in [video.transcript_file_path, video.audio_file_path]:
            if not file_path:
                continue
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    video.transcript_file_path = None
    video.audio_file_path = None
    video.audio_file_size_mb = None

    video.status = "pending"
    video.progress_percent = 0.0
    video.error_message = None
    video.completed_at = None
    video.chunk_count = 0
    video.transcription_language = None
    video.transcription_model = None

    db.commit()
    db.refresh(video)
