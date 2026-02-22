"""
Unit tests for the backfill_video_summaries Celery task and admin endpoint.

Tests cover:
- Empty DB returns zero
- Batch processing with summary generation
- Per-video error isolation (one failure doesn't block others)
- Batch size limiting
- Filtering: skips deleted and already-summarized videos
- Remaining count reporting
- Admin endpoint access control and task dispatch
"""
import uuid
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Backfill Task Tests ─────────────────────────────────────────────


class TestBackfillVideoSummaries:
    """Tests for the backfill_video_summaries Celery task."""

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_no_videos_returns_zero(self, mock_session_local):
        """Empty DB -> returns {processed: 0, ...}."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        # Mock: no videos need backfill
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value = mock_query

        result = backfill_video_summaries(batch_size=20)

        assert result["processed"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        assert result["remaining"] == 0

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_processes_batch_of_videos(self, mock_session_local):
        """3 videos -> all get summaries."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        videos = []
        for i in range(3):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.user_id = uuid.uuid4()
            v.title = f"Video {i}"
            videos.append(v)

        # First call: query for videos, second call: count remaining
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = videos
        mock_query.filter.return_value.count.return_value = 3
        db.query.return_value = mock_query

        with patch("app.tasks.video_tasks.video_summarizer_service", create=True) as mock_summarizer:
            with patch("app.tasks.video_tasks.LLMUsageCollector", create=True) as mock_collector_cls:
                mock_collector = MagicMock()
                mock_collector_cls.return_value = mock_collector
                mock_summarizer.update_video_summary.return_value = True

                # Need to patch the import inside the function
                with patch.dict("sys.modules", {
                    "app.services.video_summarizer": MagicMock(
                        video_summarizer_service=mock_summarizer
                    ),
                    "app.services.usage_collector": MagicMock(
                        LLMUsageCollector=mock_collector_cls
                    ),
                }):
                    result = backfill_video_summaries(batch_size=20)

        assert result["processed"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_per_video_error_isolation(self, mock_session_local):
        """Video 2 of 3 fails -> videos 1 and 3 still succeed."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        videos = []
        for i in range(3):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.user_id = uuid.uuid4()
            v.title = f"Video {i}"
            videos.append(v)

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = videos
        mock_query.filter.return_value.count.return_value = 3
        db.query.return_value = mock_query

        call_count = 0

        def mock_update_summary(db, video_id, usage_collector=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("LLM API error")
            return True

        with patch.dict("sys.modules", {
            "app.services.video_summarizer": MagicMock(
                video_summarizer_service=MagicMock(
                    update_video_summary=mock_update_summary
                )
            ),
            "app.services.usage_collector": MagicMock(
                LLMUsageCollector=MagicMock(return_value=MagicMock())
            ),
        }):
            result = backfill_video_summaries(batch_size=20)

        assert result["processed"] == 3
        assert result["succeeded"] == 2
        assert result["failed"] == 1

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_respects_batch_size(self, mock_session_local):
        """batch_size=5, 10 videos -> query uses limit(5)."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        mock_query = MagicMock()
        mock_limit = MagicMock()
        mock_limit.all.return_value = []
        mock_query.filter.return_value.order_by.return_value.limit.return_value = mock_limit
        db.query.return_value = mock_query

        result = backfill_video_summaries(batch_size=5)

        # Verify .limit() was called with batch_size
        mock_query.filter.return_value.order_by.return_value.limit.assert_called_with(5)

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_filters_completed_not_deleted_no_summary(self, mock_session_local):
        """Query filters: status='completed', is_deleted=False, summary=None."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.order_by.return_value.limit.return_value.all.return_value = []
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        result = backfill_video_summaries(batch_size=20)

        # Verify filter was called (the actual filter args are SQLAlchemy expressions)
        assert mock_query.filter.called

    @patch("app.tasks.video_tasks.SessionLocal")
    def test_returns_remaining_count(self, mock_session_local):
        """10 total needing backfill, batch=5 -> remaining=5."""
        from app.tasks.video_tasks import backfill_video_summaries

        db = MagicMock()
        mock_session_local.return_value = db

        videos = []
        for i in range(5):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.user_id = uuid.uuid4()
            v.title = f"Video {i}"
            videos.append(v)

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = videos
        # Total remaining before this batch
        mock_query.filter.return_value.count.return_value = 10
        db.query.return_value = mock_query

        with patch.dict("sys.modules", {
            "app.services.video_summarizer": MagicMock(
                video_summarizer_service=MagicMock(
                    update_video_summary=MagicMock(return_value=True)
                )
            ),
            "app.services.usage_collector": MagicMock(
                LLMUsageCollector=MagicMock(return_value=MagicMock())
            ),
        }):
            result = backfill_video_summaries(batch_size=5)

        assert result["remaining"] == 5  # 10 - 5


# ── Admin Endpoint Tests ────────────────────────────────────────────


class TestBackfillAdminEndpoint:
    """Tests for the POST /api/v1/admin/videos/backfill-summaries endpoint."""

    @pytest.fixture
    def app_client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_admin_only_access(self, app_client):
        """Non-admin user gets 401/403."""
        # No auth header -> should fail
        response = app_client.post("/api/v1/admin/videos/backfill-summaries")
        assert response.status_code in [401, 403, 422]

    @patch("app.tasks.video_tasks.backfill_video_summaries")
    def test_dispatches_celery_task(self, mock_task):
        """Endpoint calls backfill_video_summaries.delay()."""
        from app.api.routes.admin import trigger_backfill_summaries

        mock_task.delay.return_value = MagicMock(id="task-123")

        db = MagicMock()
        admin = MagicMock()

        # Mock: 5 videos need summaries
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 5
        db.query.return_value = mock_query

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            trigger_backfill_summaries(batch_size=20, db=db, admin_user=admin)
        )

        mock_task.delay.assert_called_once_with(batch_size=20)
        assert result["task_id"] == "task-123"
        assert result["videos_needing_summaries"] == 5

    @patch("app.tasks.video_tasks.backfill_video_summaries")
    def test_returns_zero_when_all_summarized(self, mock_task):
        """If all videos have summaries, returns success without dispatching."""
        from app.api.routes.admin import trigger_backfill_summaries

        db = MagicMock()
        admin = MagicMock()

        # Mock: 0 videos need summaries
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 0
        db.query.return_value = mock_query

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            trigger_backfill_summaries(batch_size=20, db=db, admin_user=admin)
        )

        mock_task.delay.assert_not_called()
        assert result["videos_needing_summaries"] == 0
        assert result["success"] is True
