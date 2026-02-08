"""
Unit tests for video processing pipeline tasks.

Tests pipeline orchestration, status updates, cancellation, and error handling.
"""
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_video(video_id=None, user_id=None, status="pending", **kwargs):
    video = MagicMock()
    video.id = video_id or uuid.uuid4()
    video.user_id = user_id or uuid.uuid4()
    video.status = status
    video.youtube_id = kwargs.get("youtube_id", "dQw4w9WgXcQ")
    video.title = kwargs.get("title", "Test Video")
    video.description = kwargs.get("description", "desc")
    video.duration_seconds = kwargs.get("duration_seconds", 300)
    video.audio_file_path = kwargs.get("audio_file_path", None)
    video.audio_file_size_mb = kwargs.get("audio_file_size_mb", None)
    video.transcript_file_path = None
    video.transcript_source = None
    video.transcription_language = None
    video.progress_percent = 0.0
    video.error_message = None
    video.completed_at = None
    video.chunk_count = 0
    video.chapters = None
    video.tags = []
    video.is_deleted = False
    return video


def _make_job(job_id=None, status="pending"):
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.status = status
    job.progress_percent = 0.0
    job.current_step = None
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    return job


def _make_transcript(transcript_id=None):
    transcript = MagicMock()
    transcript.id = transcript_id or uuid.uuid4()
    transcript.segments = [
        {"text": "Hello world", "start": 0.0, "end": 5.0, "speaker": None},
        {"text": "Testing stuff", "start": 5.0, "end": 10.0, "speaker": None},
    ]
    transcript.full_text = "Hello world Testing stuff"
    return transcript


# ── Status Update Tests ───────────────────────────────────────────────────


class TestUpdateVideoStatus:
    def test_updates_status_and_progress(self):
        from app.tasks.video_tasks import update_video_status

        db = MagicMock()
        video = _make_video()
        db.query.return_value.filter.return_value.first.return_value = video

        update_video_status(db, video.id, "downloading", 25.0)

        assert video.status == "downloading"
        assert video.progress_percent == 25.0
        db.commit.assert_called_once()

    def test_sets_error_message(self):
        from app.tasks.video_tasks import update_video_status

        db = MagicMock()
        video = _make_video()
        db.query.return_value.filter.return_value.first.return_value = video

        update_video_status(db, video.id, "failed", 0.0, "Something broke")

        assert video.error_message == "Something broke"
        assert video.status == "failed"

    def test_sets_completed_at_on_completion(self):
        from app.tasks.video_tasks import update_video_status

        db = MagicMock()
        video = _make_video()
        video.completed_at = None
        db.query.return_value.filter.return_value.first.return_value = video

        update_video_status(db, video.id, "completed", 100.0)

        assert video.completed_at is not None

    def test_no_video_found(self):
        from app.tasks.video_tasks import update_video_status

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        # Should not raise
        update_video_status(db, uuid.uuid4(), "downloading", 10.0)
        db.commit.assert_not_called()


class TestUpdateJobStatus:
    def test_updates_job_status(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        job = _make_job()
        db.query.return_value.filter.return_value.first.return_value = job

        update_job_status(db, job.id, "running", 50.0, "Processing")

        assert job.status == "running"
        assert job.progress_percent == 50.0
        assert job.current_step == "Processing"

    def test_sets_started_at_on_first_running(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        job = _make_job()
        job.started_at = None
        db.query.return_value.filter.return_value.first.return_value = job

        update_job_status(db, job.id, "running", 10.0)

        assert job.started_at is not None

    def test_sets_completed_at_on_finished(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        job = _make_job(status="running")
        job.completed_at = None
        db.query.return_value.filter.return_value.first.return_value = job

        update_job_status(db, job.id, "completed", 100.0)
        assert job.completed_at is not None

    def test_sets_completed_at_on_failure(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        job = _make_job(status="running")
        job.completed_at = None
        db.query.return_value.filter.return_value.first.return_value = job

        update_job_status(db, job.id, "failed", 0.0, error="Boom")
        assert job.completed_at is not None
        assert job.error_message == "Boom"


# ── Cancellation Tests ────────────────────────────────────────────────────


class TestCheckCanceledOrRaise:
    @patch("app.tasks.video_tasks.check_if_canceled")
    def test_raises_when_canceled(self, mock_check):
        from app.tasks.video_tasks import _check_canceled_or_raise, VideoCanceledException

        mock_check.return_value = True
        db = MagicMock()
        vid = str(uuid.uuid4())
        jid = str(uuid.uuid4())

        with pytest.raises(VideoCanceledException, match="canceled"):
            _check_canceled_or_raise(db, vid, jid, "after_download")

    @patch("app.tasks.video_tasks.check_if_canceled")
    def test_passes_when_not_canceled(self, mock_check):
        from app.tasks.video_tasks import _check_canceled_or_raise

        mock_check.return_value = False
        db = MagicMock()

        # Should not raise
        _check_canceled_or_raise(db, str(uuid.uuid4()), str(uuid.uuid4()), "step")


# ── Create Transcript From Captions Tests ─────────────────────────────────


class TestCreateTranscriptFromCaptions:
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_creates_transcript_from_captions(self, mock_session_cls, mock_storage):
        from app.tasks.video_tasks import _create_transcript_from_captions

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video
        mock_storage.save_transcript.return_value = "/path/to/transcript.json"

        caption_data = {
            "full_text": "Hello world. Testing captions.",
            "segments": [
                {"text": "Hello world.", "start": 0.0, "end": 3.0},
                {"text": "Testing captions.", "start": 3.0, "end": 6.0},
            ],
            "language": "en",
            "word_count": 4,
            "duration_seconds": 6.0,
        }

        result = _create_transcript_from_captions(str(video.id), caption_data)

        assert result["source"] == "captions"
        assert result["language"] == "en"
        assert result["word_count"] == 4
        assert result["segment_count"] == 2
        assert video.transcript_source == "captions"
        db.add.assert_called_once()
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_handles_error_and_marks_failed(self, mock_session_cls, mock_storage):
        from app.tasks.video_tasks import _create_transcript_from_captions

        db = MagicMock()
        mock_session_cls.return_value = db
        video = _make_video()
        db.query.return_value.filter.return_value.first.return_value = video
        # Make db.add raise to simulate error
        db.add.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            _create_transcript_from_captions(str(video.id), {
                "full_text": "test", "segments": [], "language": "en",
                "word_count": 1, "duration_seconds": 1.0,
            })

        db.close.assert_called_once()


# ── Download Audio Tests ──────────────────────────────────────────────────


class TestDownloadYoutubeAudio:
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_download(self, mock_session_cls, mock_yt, mock_tracker_cls):
        from app.tasks.video_tasks import _download_youtube_audio

        video = _make_video(duration_seconds=120)
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.download_audio.return_value = ("/path/audio.mp3", 5.2)
        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker

        result = _download_youtube_audio(
            str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
        )

        assert result["audio_path"] == "/path/audio.mp3"
        assert result["file_size_mb"] == 5.2
        assert video.audio_file_path == "/path/audio.mp3"
        assert video.status == "downloaded"
        tracker.check_quota.assert_called_once()
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_quota_exceeded_cleans_up(self, mock_session_cls, mock_yt, mock_tracker_cls, mock_storage):
        from app.tasks.video_tasks import _download_youtube_audio
        from app.services.usage_tracker import QuotaExceededError

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.download_audio.return_value = ("/path/audio.mp3", 5.2)
        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker
        tracker.check_quota.side_effect = QuotaExceededError("storage", 100.0, 50.0)

        with pytest.raises(QuotaExceededError):
            _download_youtube_audio(
                str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
            )

        mock_storage.delete_audio.assert_called_once()
        assert video.status == "failed"

    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_youtube_download_error(self, mock_session_cls, mock_yt, mock_tracker_cls):
        from app.tasks.video_tasks import _download_youtube_audio
        from app.services.youtube import YouTubeDownloadError

        db = MagicMock()
        mock_session_cls.return_value = db
        video = _make_video()
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.download_audio.side_effect = YouTubeDownloadError("Video unavailable")

        with pytest.raises(YouTubeDownloadError):
            _download_youtube_audio(
                str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
            )

        assert video.status == "failed"


# ── Chunk and Enrich Tests ────────────────────────────────────────────────


class TestChunkAndEnrich:
    @patch("app.tasks.video_tasks.ContextualEnricher")
    @patch("app.tasks.video_tasks.TranscriptChunker")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_chunk_and_enrich(self, mock_session_cls, mock_chunker_cls, mock_enricher_cls):
        from app.tasks.video_tasks import _chunk_and_enrich
        from app.services.chunking import Chunk

        video = _make_video()
        transcript = _make_transcript()
        db = MagicMock()
        mock_session_cls.return_value = db

        # Multiple db.query(...).filter(...).first() calls:
        # 1. update_video_status → Video
        # 2. _chunk_and_enrich → Video
        # 3. _chunk_and_enrich → Transcript
        # 4+ update_video_status calls during enrichment loop and after
        db.query.return_value.filter.return_value.first.side_effect = (
            lambda: video  # Default returns video
        )
        # Override to return transcript for Transcript queries
        # Use a counter-based approach
        call_results = [video, video, transcript, video, video, video, video]
        db.query.return_value.filter.return_value.first.side_effect = call_results

        mock_chunk = MagicMock(spec=Chunk)
        mock_chunk.text = "Hello world"
        mock_chunk.chunk_index = 0
        mock_chunk.start_timestamp = 0.0
        mock_chunk.end_timestamp = 5.0
        mock_chunk.duration_seconds = 5.0
        mock_chunk.token_count = 5
        mock_chunk.speakers = None
        mock_chunk.chapter_title = None
        mock_chunk.chapter_index = None

        chunker = MagicMock()
        mock_chunker_cls.return_value = chunker
        chunker.chunk_transcript.return_value = [mock_chunk]

        enriched = MagicMock()
        enriched.chunk = mock_chunk
        enriched.summary = "A greeting"
        enriched.title = "Hello"
        enriched.keywords = ["greeting"]
        enriched.embedding_text = "Hello. A greeting\n\nHello world"

        enricher = MagicMock()
        mock_enricher_cls.return_value = enricher
        enricher.enrich_chunk.return_value = enriched

        result = _chunk_and_enrich(str(video.id), str(transcript.id))

        assert result["chunk_count"] == 1
        assert video.chunk_count == 1
        assert video.status == "chunked"
        db.close.assert_called_once()


# ── Embed and Index Tests ─────────────────────────────────────────────────


class TestEmbedAndIndex:
    @patch("app.tasks.video_tasks.resolve_collection_name")
    @patch("app.tasks.video_tasks.vector_store_service")
    @patch("app.tasks.video_tasks.embedding_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_embed_and_index(
        self, mock_session_cls, mock_embed, mock_vs, mock_resolve
    ):
        from app.tasks.video_tasks import _embed_and_index

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db

        chunk = MagicMock()
        chunk.video_id = video.id
        chunk.chunk_index = 0
        chunk.text = "Hello"
        chunk.embedding_text = "Hello enriched"
        chunk.is_indexed = False
        chunk.chunk_summary = "Summary"
        chunk.chunk_title = "Title"
        chunk.keywords = ["key"]
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 5.0
        chunk.token_count = 3
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None

        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [chunk]
        # For video lookup
        db.query.return_value.filter.return_value.first.return_value = video

        import numpy as np
        mock_embed.embed_batch.return_value = [np.zeros(384)]
        mock_embed.get_dimensions.return_value = 384
        mock_embed.get_model_name.return_value = "bge-base-en-v1.5"
        mock_resolve.return_value = "test_collection"

        result = _embed_and_index(str(video.id), str(video.user_id))

        assert result["indexed_count"] == 1
        assert chunk.is_indexed is True
        mock_vs.initialize.assert_called_once()
        mock_vs.index_video_chunks.assert_called_once()

    @patch("app.tasks.video_tasks.embedding_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_no_chunks_completes_immediately(self, mock_session_cls, mock_embed):
        from app.tasks.video_tasks import _embed_and_index

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = video

        result = _embed_and_index(str(video.id), str(video.user_id))

        assert result["indexed_count"] == 0
        assert video.status == "completed"
        mock_embed.embed_batch.assert_not_called()


# ── Generate Video Summary Tests ──────────────────────────────────────────


class TestGenerateVideoSummary:
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_summary(self, mock_session_cls):
        from app.tasks.video_tasks import _generate_video_summary

        db = MagicMock()
        mock_session_cls.return_value = db

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer:
            mock_summarizer.update_video_summary.return_value = True
            result = _generate_video_summary(str(uuid.uuid4()))

        assert result["success"] is True
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_summary_failure_does_not_raise(self, mock_session_cls):
        from app.tasks.video_tasks import _generate_video_summary

        db = MagicMock()
        mock_session_cls.return_value = db

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer:
            mock_summarizer.update_video_summary.side_effect = Exception("LLM down")
            result = _generate_video_summary(str(uuid.uuid4()))

        assert result["success"] is False
        assert "LLM down" in result["error"]


# ── Pipeline Orchestration Tests ──────────────────────────────────────────


class TestProcessVideoPipeline:
    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._create_transcript_from_captions")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_caption_fast_path(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_captions, mock_chunk, mock_embed, mock_summary
    ):
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.side_effect = [
            job,  # update_job_status
            video,  # video lookup in pipeline
            video,  # update_video_status calls
            job,   # update_job_status
            job,   # update_job_status
            video,  # various status updates
            job,
            job,
            job,
            job,
            job,
        ]

        mock_canceled.return_value = False
        mock_yt.get_captions.return_value = {
            "full_text": "Caption text",
            "segments": [{"text": "Caption text", "start": 0.0, "end": 5.0}],
            "language": "en",
            "word_count": 2,
            "duration_seconds": 5.0,
        }
        mock_captions.return_value = {"transcript_id": str(uuid.uuid4())}
        mock_chunk.return_value = {"chunk_count": 3}
        mock_embed.return_value = {"indexed_count": 3}
        mock_summary.return_value = {"success": True}

        result = process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=test",
            str(video.user_id), str(job.id)
        )

        assert result["status"] == "completed"
        assert result["chunk_count"] == 3
        # Caption path means _download_youtube_audio should NOT be called
        mock_captions.assert_called_once()

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._transcribe_audio")
    @patch("app.tasks.video_tasks._download_youtube_audio")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_whisper_fallback_when_no_captions(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_download, mock_transcribe, mock_chunk, mock_embed, mock_summary
    ):
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_canceled.return_value = False
        mock_yt.get_captions.return_value = None  # No captions available
        mock_download.return_value = {"audio_path": "/path/audio.mp3"}
        mock_transcribe.return_value = {"transcript_id": str(uuid.uuid4())}
        mock_chunk.return_value = {"chunk_count": 5}
        mock_embed.return_value = {"indexed_count": 5}
        mock_summary.return_value = {"success": True}

        result = process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=test",
            str(video.user_id), str(job.id)
        )

        assert result["status"] == "completed"
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()

    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_pipeline_canceled_at_checkpoint(
        self, mock_session_cls, mock_canceled, mock_yt
    ):
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        # Cancel at the first checkpoint
        mock_canceled.return_value = True

        result = process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=test",
            str(video.user_id), str(job.id)
        )

        assert result["status"] == "canceled"


# ── Regenerate Collection Themes Task Tests ───────────────────────────────


class TestRegenerateCollectionThemesTask:
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_regeneration(self, mock_session_cls):
        from app.tasks.video_tasks import regenerate_collection_themes

        db = MagicMock()
        mock_session_cls.return_value = db

        collection_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch("app.services.theme_service.get_theme_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.cluster_collection_themes.return_value = [
                {"theme_label": "AI", "video_ids": []},
                {"theme_label": "ML", "video_ids": []},
            ]

            result = regenerate_collection_themes(collection_id, user_id)

        assert result["status"] == "completed"
        assert result["theme_count"] == 2
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_regeneration_error_propagates(self, mock_session_cls):
        from app.tasks.video_tasks import regenerate_collection_themes

        db = MagicMock()
        mock_session_cls.return_value = db

        with patch("app.services.theme_service.get_theme_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.cluster_collection_themes.side_effect = Exception("Cluster failed")

            with pytest.raises(Exception, match="Cluster failed"):
                regenerate_collection_themes(str(uuid.uuid4()), str(uuid.uuid4()))

        db.close.assert_called_once()
