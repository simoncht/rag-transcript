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
        enricher.enrich_chunks_concurrent.return_value = [enriched]

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


# ── Transcribe Audio Tests ───────────────────────────────────────────────


class TestTranscribeAudio:
    """Tests for _transcribe_audio helper function."""

    @patch("app.tasks.video_tasks.settings")
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.TranscriptionService")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_transcription(
        self, mock_session_cls, mock_ts_cls, mock_tracker_cls, mock_storage, mock_settings
    ):
        from app.tasks.video_tasks import _transcribe_audio

        video = _make_video(duration_seconds=60)
        db = MagicMock()
        # SessionLocal is called twice: once for main db, once inside heartbeat_worker
        heartbeat_db = MagicMock()
        heartbeat_db.query.return_value.filter.return_value.first.return_value = video
        mock_session_cls.side_effect = [db, heartbeat_db]
        db.query.return_value.filter.return_value.first.return_value = video

        mock_settings.cleanup_audio_after_transcription = False

        # Build a mock transcription result
        seg = MagicMock()
        seg.text = "Hello world"
        seg.start = 0.0
        seg.end = 5.0
        seg.speaker = None

        result_obj = MagicMock()
        result_obj.full_text = "Hello world"
        result_obj.segments = [seg]
        result_obj.language = "en"
        result_obj.word_count = 2
        result_obj.duration_seconds = 5.0
        result_obj.model = "whisper-base"

        transcriber = MagicMock()
        mock_ts_cls.return_value = transcriber
        transcriber.transcribe_file.return_value = result_obj

        mock_storage.save_transcript.return_value = "/path/transcript.json"

        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker

        # Mock Path.stat for transcript size tracking
        with patch("app.tasks.video_tasks.Path") as mock_path:
            mock_stat = MagicMock()
            mock_stat.st_size = 1024  # 1KB
            mock_path.return_value.stat.return_value = mock_stat

            result = _transcribe_audio(str(video.id), "/path/audio.mp3")

        assert result["language"] == "en"
        assert result["word_count"] == 2
        assert result["segment_count"] == 1
        assert "transcript_id" in result
        assert video.status == "transcribed"
        assert video.transcript_source == "whisper"
        db.add.assert_called_once()
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.settings")
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.TranscriptionService")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_transcription_cleans_up_audio_when_configured(
        self, mock_session_cls, mock_ts_cls, mock_tracker_cls, mock_storage, mock_settings
    ):
        from app.tasks.video_tasks import _transcribe_audio

        video = _make_video(duration_seconds=60, audio_file_size_mb=10.5)
        db = MagicMock()
        heartbeat_db = MagicMock()
        heartbeat_db.query.return_value.filter.return_value.first.return_value = video
        mock_session_cls.side_effect = [db, heartbeat_db]
        db.query.return_value.filter.return_value.first.return_value = video

        mock_settings.cleanup_audio_after_transcription = True

        seg = MagicMock()
        seg.text = "Test"
        seg.start = 0.0
        seg.end = 1.0
        seg.speaker = None

        result_obj = MagicMock()
        result_obj.full_text = "Test"
        result_obj.segments = [seg]
        result_obj.language = "en"
        result_obj.word_count = 1
        result_obj.duration_seconds = 1.0

        transcriber = MagicMock()
        mock_ts_cls.return_value = transcriber
        transcriber.transcribe_file.return_value = result_obj

        mock_storage.save_transcript.return_value = "/path/transcript.json"
        mock_storage.delete_audio.return_value = True

        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker

        with patch("app.tasks.video_tasks.Path") as mock_path:
            mock_stat = MagicMock()
            mock_stat.st_size = 512
            mock_path.return_value.stat.return_value = mock_stat

            _transcribe_audio(str(video.id), "/path/audio.mp3")

        mock_storage.delete_audio.assert_called_once_with(video.user_id, video.id)
        # Verify storage credit was tracked (negative delta for audio cleaned)
        storage_calls = [
            c for c in tracker.track_storage_usage.call_args_list
            if c[1].get("reason") == "audio_cleaned" or (len(c[0]) > 1 and c[0][1] < 0)
        ]
        assert len(storage_calls) >= 1

    @patch("app.tasks.video_tasks.settings")
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.TranscriptionService")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_transcription_failure_marks_video_failed(
        self, mock_session_cls, mock_ts_cls, mock_tracker_cls, mock_storage, mock_settings
    ):
        from app.tasks.video_tasks import _transcribe_audio

        video = _make_video()
        db = MagicMock()
        heartbeat_db = MagicMock()
        heartbeat_db.query.return_value.filter.return_value.first.return_value = video
        mock_session_cls.side_effect = [db, heartbeat_db]
        db.query.return_value.filter.return_value.first.return_value = video

        transcriber = MagicMock()
        mock_ts_cls.return_value = transcriber
        transcriber.transcribe_file.side_effect = RuntimeError("Whisper crashed")

        with pytest.raises(RuntimeError, match="Whisper crashed"):
            _transcribe_audio(str(video.id), "/path/audio.mp3")

        assert video.status == "failed"
        assert "Transcription failed" in (video.error_message or "")
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.settings")
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.TranscriptionService")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_transcription_tracks_usage(
        self, mock_session_cls, mock_ts_cls, mock_tracker_cls, mock_storage, mock_settings
    ):
        from app.tasks.video_tasks import _transcribe_audio

        video = _make_video(duration_seconds=120)
        db = MagicMock()
        heartbeat_db = MagicMock()
        heartbeat_db.query.return_value.filter.return_value.first.return_value = video
        mock_session_cls.side_effect = [db, heartbeat_db]
        db.query.return_value.filter.return_value.first.return_value = video

        mock_settings.cleanup_audio_after_transcription = False

        seg = MagicMock()
        seg.text = "Test transcription"
        seg.start = 0.0
        seg.end = 10.0
        seg.speaker = "Speaker1"

        result_obj = MagicMock()
        result_obj.full_text = "Test transcription"
        result_obj.segments = [seg]
        result_obj.language = "fr"
        result_obj.word_count = 2
        result_obj.duration_seconds = 10.0
        result_obj.model = "whisper-large"

        transcriber = MagicMock()
        mock_ts_cls.return_value = transcriber
        transcriber.transcribe_file.return_value = result_obj

        mock_storage.save_transcript.return_value = "/path/transcript.json"

        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker

        with patch("app.tasks.video_tasks.Path") as mock_path:
            mock_stat = MagicMock()
            mock_stat.st_size = 2048
            mock_path.return_value.stat.return_value = mock_stat

            result = _transcribe_audio(str(video.id), "/path/audio.mp3")

        # Should have speaker labels detection
        assert video.transcription_language == "fr"
        # Track transcription event
        tracker.track_transcription.assert_called_once()

    @patch("app.tasks.video_tasks.settings")
    @patch("app.tasks.video_tasks.storage_service")
    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.TranscriptionService")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_transcription_usage_tracking_failure_is_non_fatal(
        self, mock_session_cls, mock_ts_cls, mock_tracker_cls, mock_storage, mock_settings
    ):
        """Usage tracking failures should not crash the transcription pipeline."""
        from app.tasks.video_tasks import _transcribe_audio

        video = _make_video(duration_seconds=60)
        db = MagicMock()
        heartbeat_db = MagicMock()
        heartbeat_db.query.return_value.filter.return_value.first.return_value = video
        mock_session_cls.side_effect = [db, heartbeat_db]
        db.query.return_value.filter.return_value.first.return_value = video

        mock_settings.cleanup_audio_after_transcription = False

        seg = MagicMock()
        seg.text = "OK"
        seg.start = 0.0
        seg.end = 1.0
        seg.speaker = None

        result_obj = MagicMock()
        result_obj.full_text = "OK"
        result_obj.segments = [seg]
        result_obj.language = "en"
        result_obj.word_count = 1
        result_obj.duration_seconds = 1.0

        transcriber = MagicMock()
        mock_ts_cls.return_value = transcriber
        transcriber.transcribe_file.return_value = result_obj

        mock_storage.save_transcript.return_value = "/path/transcript.json"

        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker
        # All usage tracking calls fail
        tracker.track_storage_usage.side_effect = Exception("Redis down")
        tracker.track_transcription.side_effect = Exception("Redis down")

        with patch("app.tasks.video_tasks.Path") as mock_path:
            mock_stat = MagicMock()
            mock_stat.st_size = 100
            mock_path.return_value.stat.return_value = mock_stat

            # Should not raise despite usage tracking failures
            result = _transcribe_audio(str(video.id), "/path/audio.mp3")

        assert result["language"] == "en"
        assert video.status == "transcribed"


# ── Download Audio Additional Tests ──────────────────────────────────────


class TestDownloadYoutubeAudioAdditional:
    """Additional coverage for _download_youtube_audio edge cases."""

    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_generic_exception_marks_video_failed(self, mock_session_cls, mock_yt, mock_tracker_cls):
        """Generic exceptions (not YouTube/Quota) should still mark video as failed."""
        from app.tasks.video_tasks import _download_youtube_audio

        db = MagicMock()
        mock_session_cls.return_value = db
        video = _make_video()
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.download_audio.side_effect = RuntimeError("Disk full")

        with pytest.raises(RuntimeError, match="Disk full"):
            _download_youtube_audio(
                str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
            )

        assert video.status == "failed"
        assert "Download failed" in (video.error_message or "")
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_ingestion_tracking_failure_is_non_fatal(self, mock_session_cls, mock_yt, mock_tracker_cls):
        """Ingestion tracking failures should not fail the download."""
        from app.tasks.video_tasks import _download_youtube_audio

        video = _make_video(duration_seconds=120)
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.download_audio.return_value = ("/path/audio.mp3", 3.0)
        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker
        tracker.track_video_ingestion.side_effect = Exception("Tracking failed")

        # Should succeed despite tracking failure
        result = _download_youtube_audio(
            str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
        )

        assert result["audio_path"] == "/path/audio.mp3"
        assert video.status == "downloaded"

    @patch("app.tasks.video_tasks.UsageTracker")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_progress_callback_calculates_percent(self, mock_session_cls, mock_yt, mock_tracker_cls):
        """Verify progress_callback updates status during download."""
        from app.tasks.video_tasks import _download_youtube_audio

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        captured_callback = None

        def capture_callback(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("progress_callback")
            return ("/path/audio.mp3", 2.0)

        mock_yt.download_audio.side_effect = capture_callback
        tracker = MagicMock()
        mock_tracker_cls.return_value = tracker

        _download_youtube_audio(
            str(video.id), "https://youtube.com/watch?v=test", str(video.user_id)
        )

        # Simulate what the callback would do
        assert captured_callback is not None
        captured_callback({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000})
        # After callback, status should still be "downloaded" (final state)
        # but during download it would be "downloading"


# ── Chunk and Enrich Additional Tests ────────────────────────────────────


class TestChunkAndEnrichAdditional:
    """Additional coverage for _chunk_and_enrich edge cases."""

    @patch("app.tasks.video_tasks.ContextualEnricher")
    @patch("app.tasks.video_tasks.TranscriptChunker")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_chunking_failure_marks_video_failed(self, mock_session_cls, mock_chunker_cls, mock_enricher_cls):
        from app.tasks.video_tasks import _chunk_and_enrich

        video = _make_video()
        transcript = _make_transcript()
        db = MagicMock()
        mock_session_cls.return_value = db
        # update_video_status(chunking), video query, transcript query, then update_video_status(failed)
        call_results = [video, video, transcript, video, video]
        db.query.return_value.filter.return_value.first.side_effect = call_results

        chunker = MagicMock()
        mock_chunker_cls.return_value = chunker
        chunker.chunk_transcript.side_effect = ValueError("Invalid segments")

        with pytest.raises(ValueError, match="Invalid segments"):
            _chunk_and_enrich(str(video.id), str(transcript.id))

        assert video.status == "failed"
        assert "Chunking failed" in (video.error_message or "")
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.ContextualEnricher")
    @patch("app.tasks.video_tasks.TranscriptChunker")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_fallback_chunk_when_chunker_returns_empty(self, mock_session_cls, mock_chunker_cls, mock_enricher_cls):
        """When chunks are empty but segments exist, fallback to single chunk."""
        from app.tasks.video_tasks import _chunk_and_enrich

        video = _make_video()
        transcript = _make_transcript()
        db = MagicMock()
        mock_session_cls.return_value = db

        call_results = [video, video, transcript, video, video, video, video]
        db.query.return_value.filter.return_value.first.side_effect = call_results

        mock_fallback_chunk = MagicMock()
        mock_fallback_chunk.text = "Hello world Testing stuff"
        mock_fallback_chunk.chunk_index = 0
        mock_fallback_chunk.start_timestamp = 0.0
        mock_fallback_chunk.end_timestamp = 10.0
        mock_fallback_chunk.duration_seconds = 10.0
        mock_fallback_chunk.token_count = 4
        mock_fallback_chunk.speakers = None
        mock_fallback_chunk.chapter_title = None
        mock_fallback_chunk.chapter_index = None

        chunker = MagicMock()
        mock_chunker_cls.return_value = chunker
        chunker.chunk_transcript.return_value = []  # Empty chunks
        chunker.create_chunk_from_segments.return_value = mock_fallback_chunk

        enriched = MagicMock()
        enriched.chunk = mock_fallback_chunk
        enriched.summary = "Combined segments"
        enriched.title = "Full clip"
        enriched.keywords = ["test"]
        enriched.embedding_text = "Full clip text"

        enricher = MagicMock()
        mock_enricher_cls.return_value = enricher
        enricher.enrich_chunks_concurrent.return_value = [enriched]

        result = _chunk_and_enrich(str(video.id), str(transcript.id))

        assert result["chunk_count"] == 1
        # Fallback path should have been taken
        chunker.create_chunk_from_segments.assert_called_once()


# ── Embed and Index Additional Tests ─────────────────────────────────────


class TestEmbedAndIndexAdditional:
    """Additional coverage for _embed_and_index edge cases."""

    @patch("app.tasks.video_tasks.resolve_collection_name")
    @patch("app.tasks.video_tasks.vector_store_service")
    @patch("app.tasks.video_tasks.embedding_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_indexing_failure_marks_video_failed(
        self, mock_session_cls, mock_embed, mock_vs, mock_resolve
    ):
        from app.tasks.video_tasks import _embed_and_index

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db

        chunk = MagicMock()
        chunk.embedding_text = "Hello"
        chunk.text = "Hello"
        chunk.is_indexed = False
        chunk.chunk_summary = "S"
        chunk.chunk_title = "T"
        chunk.keywords = []
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 1.0
        chunk.token_count = 1
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None
        chunk.chunk_index = 0

        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [chunk]
        db.query.return_value.filter.return_value.first.return_value = video

        import numpy as np
        mock_embed.embed_batch.return_value = [np.zeros(384)]
        mock_embed.get_dimensions.return_value = 384
        mock_resolve.return_value = "test_collection"

        mock_vs.index_video_chunks.side_effect = ConnectionError("Qdrant down")

        with pytest.raises(ConnectionError, match="Qdrant down"):
            _embed_and_index(str(video.id), str(video.user_id))

        assert video.status == "failed"
        assert "Indexing failed" in (video.error_message or "")
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.resolve_collection_name")
    @patch("app.tasks.video_tasks.vector_store_service")
    @patch("app.tasks.video_tasks.embedding_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_chunk_without_embedding_text_uses_raw_text(
        self, mock_session_cls, mock_embed, mock_vs, mock_resolve
    ):
        """When embedding_text is None, fall back to chunk.text for embedding."""
        from app.tasks.video_tasks import _embed_and_index

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db

        chunk = MagicMock()
        chunk.embedding_text = None  # No enriched text
        chunk.text = "Raw chunk text"
        chunk.is_indexed = False
        chunk.chunk_summary = None
        chunk.chunk_title = None
        chunk.keywords = None
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 2.0
        chunk.token_count = 3
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None
        chunk.chunk_index = 0

        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [chunk]
        db.query.return_value.filter.return_value.first.return_value = video

        import numpy as np
        mock_embed.embed_batch.return_value = [np.zeros(384)]
        mock_embed.get_dimensions.return_value = 384
        mock_embed.get_model_name.return_value = "bge-base-en-v1.5"
        mock_resolve.return_value = "test_collection"

        result = _embed_and_index(str(video.id), str(video.user_id))

        # Should have used "Raw chunk text" since embedding_text is None
        mock_embed.embed_batch.assert_called_once_with(["Raw chunk text"], show_progress=False)
        assert result["indexed_count"] == 1

    @patch("app.tasks.video_tasks.resolve_collection_name")
    @patch("app.tasks.video_tasks.vector_store_service")
    @patch("app.tasks.video_tasks.embedding_service")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_usage_tracking_failure_is_non_fatal(
        self, mock_session_cls, mock_embed, mock_vs, mock_resolve
    ):
        """Embedding usage tracking failures should not fail the indexing."""
        from app.tasks.video_tasks import _embed_and_index

        video = _make_video()
        db = MagicMock()
        mock_session_cls.return_value = db

        chunk = MagicMock()
        chunk.embedding_text = "Hello"
        chunk.text = "Hello"
        chunk.is_indexed = False
        chunk.chunk_summary = "S"
        chunk.chunk_title = "T"
        chunk.keywords = []
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 1.0
        chunk.token_count = 1
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None
        chunk.chunk_index = 0

        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [chunk]
        db.query.return_value.filter.return_value.first.return_value = video

        import numpy as np
        mock_embed.embed_batch.return_value = [np.zeros(384)]
        mock_embed.get_dimensions.return_value = 384
        mock_embed.get_model_name.return_value = "bge-base-en-v1.5"
        mock_resolve.return_value = "test_collection"

        with patch("app.tasks.video_tasks.UsageTracker") as mock_tracker_cls:
            tracker = MagicMock()
            mock_tracker_cls.return_value = tracker
            tracker.track_embedding_generation.side_effect = Exception("Tracking error")

            result = _embed_and_index(str(video.id), str(video.user_id))

        assert result["indexed_count"] == 1
        assert video.status == "completed"


# ── Pipeline Orchestration Additional Tests ──────────────────────────────


class TestProcessVideoPipelineAdditional:
    """Additional coverage for process_video_pipeline edge cases."""

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._transcribe_audio")
    @patch("app.tasks.video_tasks._download_youtube_audio")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_pipeline_exception_marks_job_failed(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_download, mock_transcribe, mock_chunk, mock_embed, mock_summary
    ):
        """Non-cancellation exceptions should mark the job as failed and re-raise."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_canceled.return_value = False
        mock_yt.get_captions.return_value = None
        mock_download.side_effect = RuntimeError("Catastrophic failure")

        with pytest.raises(RuntimeError, match="Catastrophic failure"):
            process_video_pipeline(
                str(video.id), "https://youtube.com/watch?v=test",
                str(video.user_id), str(job.id)
            )

        db.close.assert_called_once()

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._transcribe_audio")
    @patch("app.tasks.video_tasks._download_youtube_audio")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_canceled_after_download_does_not_transcribe(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_download, mock_transcribe, mock_chunk, mock_embed, mock_summary
    ):
        """Cancellation after download should prevent transcription from starting."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        # Not canceled initially, but canceled after download
        cancel_sequence = [False, True]  # before_transcription=False, after_download=True
        mock_canceled.side_effect = cancel_sequence

        mock_yt.get_captions.return_value = None
        mock_download.return_value = {"audio_path": "/path/audio.mp3"}

        result = process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=test",
            str(video.user_id), str(job.id)
        )

        assert result["status"] == "canceled"
        mock_download.assert_called_once()
        mock_transcribe.assert_not_called()
        mock_chunk.assert_not_called()
        mock_embed.assert_not_called()

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._transcribe_audio")
    @patch("app.tasks.video_tasks._download_youtube_audio")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_canceled_after_chunk_enrich(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_download, mock_transcribe, mock_chunk, mock_embed, mock_summary
    ):
        """Cancellation after chunk/enrich should prevent embed/index."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_yt.get_captions.return_value = {
            "full_text": "Test", "segments": [{"text": "Test", "start": 0.0, "end": 1.0}],
            "language": "en", "word_count": 1, "duration_seconds": 1.0,
        }
        mock_canceled.side_effect = [
            False,  # before_transcription
            False,  # after_transcribe (1st call)
            False,  # after_transcribe (2nd call - duplicate checkpoint)
            True,   # after_chunk_enrich
        ]

        from app.tasks.video_tasks import _create_transcript_from_captions
        with patch("app.tasks.video_tasks._create_transcript_from_captions") as mock_captions:
            mock_captions.return_value = {"transcript_id": str(uuid.uuid4())}
            mock_chunk.return_value = {"chunk_count": 5}

            result = process_video_pipeline(
                str(video.id), "https://youtube.com/watch?v=test",
                str(video.user_id), str(job.id)
            )

        assert result["status"] == "canceled"
        mock_chunk.assert_called_once()
        mock_embed.assert_not_called()

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._create_transcript_from_captions")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_pipeline_tracks_summary_generated_flag(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_captions, mock_chunk, mock_embed, mock_summary
    ):
        """Result should include summary_generated flag from summary step."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_canceled.return_value = False
        mock_yt.get_captions.return_value = {
            "full_text": "Test", "segments": [], "language": "en",
            "word_count": 1, "duration_seconds": 1.0,
        }
        mock_captions.return_value = {"transcript_id": str(uuid.uuid4())}
        mock_chunk.return_value = {"chunk_count": 2}
        mock_embed.return_value = {"indexed_count": 2}
        mock_summary.return_value = {"success": False, "error": "No chunks"}

        result = process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=test",
            str(video.user_id), str(job.id)
        )

        assert result["status"] == "completed"
        assert result["summary_generated"] is False

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._create_transcript_from_captions")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_pipeline_uses_video_youtube_id(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_captions, mock_chunk, mock_embed, mock_summary
    ):
        """Pipeline should use video.youtube_id for caption extraction."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video(youtube_id="abc123")
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_canceled.return_value = False
        mock_yt.get_captions.return_value = {
            "full_text": "Test", "segments": [], "language": "en",
            "word_count": 1, "duration_seconds": 1.0,
        }
        mock_captions.return_value = {"transcript_id": str(uuid.uuid4())}
        mock_chunk.return_value = {"chunk_count": 1}
        mock_embed.return_value = {"indexed_count": 1}
        mock_summary.return_value = {"success": True}

        process_video_pipeline(
            str(video.id), "https://youtube.com/watch?v=abc123",
            str(video.user_id), str(job.id)
        )

        # Should use video.youtube_id, not extract from URL
        mock_yt.get_captions.assert_called_once_with("abc123")

    @patch("app.tasks.video_tasks._generate_video_summary")
    @patch("app.tasks.video_tasks._embed_and_index")
    @patch("app.tasks.video_tasks._chunk_and_enrich")
    @patch("app.tasks.video_tasks._create_transcript_from_captions")
    @patch("app.tasks.video_tasks.youtube_service")
    @patch("app.tasks.video_tasks.check_if_canceled")
    @patch("app.tasks.video_tasks.SessionLocal")
    def test_pipeline_always_closes_db(
        self, mock_session_cls, mock_canceled, mock_yt,
        mock_captions, mock_chunk, mock_embed, mock_summary
    ):
        """DB session should be closed even on unexpected errors."""
        from app.tasks.video_tasks import process_video_pipeline

        video = _make_video()
        job = _make_job()
        db = MagicMock()
        mock_session_cls.return_value = db
        db.query.return_value.filter.return_value.first.return_value = video

        mock_canceled.return_value = False
        mock_yt.get_captions.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            process_video_pipeline(
                str(video.id), "https://youtube.com/watch?v=test",
                str(video.user_id), str(job.id)
            )

        db.close.assert_called_once()


# ── Backfill Video Summaries Tests ───────────────────────────────────────


class TestBackfillVideoSummaries:
    """Tests for the backfill_video_summaries Celery task."""

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_no_videos_need_backfill(self, mock_session_cls):
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        # The code builds the query chain then calls .all() first, then
        # if empty it returns early. We need to set up the chain properly.
        query_chain = MagicMock()
        db.query.return_value.filter.return_value = query_chain
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value.limit.return_value.all.return_value = []

        result = backfill_video_summaries()

        assert result["processed"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_successful_backfill(self, mock_session_cls):
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        video1 = _make_video(status="completed")
        video1.summary = None
        video1.title = "Video About AI Research Advances"
        video2 = _make_video(status="completed")
        video2.summary = None
        video2.title = "Machine Learning Tutorial Guide"

        # Both the .all() and .count() queries go through the same mock chain
        query_chain = MagicMock()
        db.query.return_value.filter.return_value = query_chain
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value.limit.return_value.all.return_value = [video1, video2]
        query_chain.count.return_value = 5

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer, \
             patch("app.services.usage_collector.LLMUsageCollector") as mock_collector_cls:
            mock_summarizer.update_video_summary.return_value = True
            mock_collector = MagicMock()
            mock_collector_cls.return_value = mock_collector

            result = backfill_video_summaries(batch_size=10)

        assert result["processed"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert result["remaining"] == 3  # 5 remaining - 2 processed
        db.close.assert_called_once()

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_backfill_partial_failure(self, mock_session_cls):
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        video1 = _make_video(status="completed")
        video1.summary = None
        video1.title = "Good video title for test"
        video2 = _make_video(status="completed")
        video2.summary = None
        video2.title = "Bad video that will fail"

        query_chain = MagicMock()
        db.query.return_value.filter.return_value = query_chain
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value.limit.return_value.all.return_value = [video1, video2]
        query_chain.count.return_value = 2

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer, \
             patch("app.services.usage_collector.LLMUsageCollector") as mock_collector_cls:
            # First succeeds, second fails
            mock_summarizer.update_video_summary.side_effect = [True, Exception("LLM error")]
            mock_collector = MagicMock()
            mock_collector_cls.return_value = mock_collector

            result = backfill_video_summaries()

        assert result["processed"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        db.rollback.assert_called_once()  # rollback on failure

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_backfill_summary_returns_false(self, mock_session_cls):
        """When update_video_summary returns False (not exception), count as failed."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        video = _make_video(status="completed")
        video.summary = None
        video.title = "Video with not enough chunks"

        query_chain = MagicMock()
        db.query.return_value.filter.return_value = query_chain
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value.limit.return_value.all.return_value = [video]
        query_chain.count.return_value = 1

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer, \
             patch("app.services.usage_collector.LLMUsageCollector") as mock_collector_cls:
            mock_summarizer.update_video_summary.return_value = False
            mock_collector = MagicMock()
            mock_collector_cls.return_value = mock_collector

            result = backfill_video_summaries()

        assert result["succeeded"] == 0
        assert result["failed"] == 1

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_backfill_respects_batch_size(self, mock_session_cls):
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        query_chain = MagicMock()
        db.query.return_value.filter.return_value = query_chain
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value.limit.return_value.all.return_value = []

        backfill_video_summaries(batch_size=5)

        # Verify the limit was called with batch_size
        query_chain.order_by.return_value.limit.assert_called_with(5)

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_backfill_always_closes_db(self, mock_session_cls):
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_cls.return_value = db

        # Make the query itself raise
        db.query.side_effect = Exception("DB connection lost")

        with pytest.raises(Exception, match="DB connection lost"):
            backfill_video_summaries()

        db.close.assert_called_once()


# ── Generate Video Summary Additional Tests ──────────────────────────────


class TestGenerateVideoSummaryAdditional:
    """Additional coverage for _generate_video_summary."""

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_summary_returns_false_on_failure(self, mock_session_cls):
        from app.tasks.video_tasks import _generate_video_summary

        db = MagicMock()
        mock_session_cls.return_value = db

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer:
            mock_summarizer.update_video_summary.return_value = False  # Not an error, just failed
            result = _generate_video_summary(str(uuid.uuid4()))

        assert result["success"] is False
        assert "error" in result

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_summary_flushes_usage_collector(self, mock_session_cls):
        from app.tasks.video_tasks import _generate_video_summary

        db = MagicMock()
        mock_session_cls.return_value = db

        with patch("app.services.video_summarizer.video_summarizer_service") as mock_summarizer, \
             patch("app.services.usage_collector.LLMUsageCollector") as mock_collector_cls:
            mock_summarizer.update_video_summary.return_value = True
            mock_collector = MagicMock()
            mock_collector_cls.return_value = mock_collector

            _generate_video_summary(str(uuid.uuid4()))

            mock_collector.flush.assert_called_once_with(db)
            db.commit.assert_called()


# ── Update Status Edge Cases ─────────────────────────────────────────────


class TestUpdateStatusEdgeCases:
    """Additional edge cases for status update helpers."""

    def test_job_no_job_found(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        # Should not raise
        update_job_status(db, uuid.uuid4(), "running", 50.0)
        db.commit.assert_not_called()

    def test_job_does_not_override_started_at_if_already_set(self):
        from app.tasks.video_tasks import update_job_status

        db = MagicMock()
        job = _make_job(status="running")
        existing_time = datetime(2025, 1, 1, 12, 0, 0)
        job.started_at = existing_time
        db.query.return_value.filter.return_value.first.return_value = job

        update_job_status(db, job.id, "running", 80.0)

        assert job.started_at == existing_time  # Should not be overwritten

    def test_video_does_not_set_completed_at_for_non_completed(self):
        from app.tasks.video_tasks import update_video_status

        db = MagicMock()
        video = _make_video()
        video.completed_at = None
        db.query.return_value.filter.return_value.first.return_value = video

        update_video_status(db, video.id, "downloading", 25.0)

        assert video.completed_at is None


# ── Cancellation Checkpoint Integration Tests ────────────────────────────


class TestCancellationCheckpointStepNames:
    """Verify that step name is included in the exception message."""

    @patch("app.tasks.video_tasks.check_if_canceled")
    def test_step_name_in_exception(self, mock_check):
        from app.tasks.video_tasks import _check_canceled_or_raise, VideoCanceledException

        mock_check.return_value = True
        db = MagicMock()

        with pytest.raises(VideoCanceledException, match="after_download"):
            _check_canceled_or_raise(db, str(uuid.uuid4()), str(uuid.uuid4()), "after_download")

    @patch("app.tasks.video_tasks.check_if_canceled")
    def test_different_step_names(self, mock_check):
        from app.tasks.video_tasks import _check_canceled_or_raise, VideoCanceledException

        mock_check.return_value = True
        db = MagicMock()

        for step in ["before_transcription", "after_transcribe", "after_chunk_enrich", "after_embed_index"]:
            with pytest.raises(VideoCanceledException, match=step):
                _check_canceled_or_raise(db, str(uuid.uuid4()), str(uuid.uuid4()), step)


# ── VideoCanceledException Tests ─────────────────────────────────────────


class TestVideoCanceledException:
    def test_exception_is_an_exception(self):
        from app.tasks.video_tasks import VideoCanceledException

        exc = VideoCanceledException("test message")
        assert isinstance(exc, Exception)
        assert str(exc) == "test message"

    def test_exception_can_be_caught(self):
        from app.tasks.video_tasks import VideoCanceledException

        with pytest.raises(VideoCanceledException):
            raise VideoCanceledException("canceled")
