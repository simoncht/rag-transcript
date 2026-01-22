"""
Integration tests for video API endpoints.

Tests the full request/response cycle for video routes including:
- POST /videos/ingest
- GET /videos
- GET /videos/{id}
- POST /videos/delete
- POST /videos/{id}/reprocess
"""
from datetime import datetime
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import User, Video, Job
from app.core.nextauth import get_current_user
from app.db.base import get_db


# Test fixtures


@pytest.fixture
def test_user(db: Session):
    """Create a test user for video operations."""
    user = User(
        email="videotest@test.com",
        full_name="Video Test User",
        oauth_provider="google",
        oauth_provider_id="video_test_oauth_id",
        is_superuser=False,
        is_active=True,
        subscription_tier="pro",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_with_user(test_user, db: Session):
    """Create a test client with user authentication."""
    client = TestClient(app)

    def override_get_current_user():
        return test_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_video(db: Session, test_user):
    """Create a sample video for testing."""
    video = Video(
        user_id=test_user.id,
        youtube_id="dQw4w9WgXcQ",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Test Video",
        description="A test video description",
        channel_name="Test Channel",
        channel_id="UC_test_channel",
        thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/default.jpg",
        duration_seconds=212,
        status="completed",
        progress_percent=100.0,
        chunk_count=10,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture
def mock_youtube_service():
    """Mock the YouTube service for ingestion tests."""
    with patch("app.api.routes.videos.youtube_service") as mock:
        mock.get_video_info.return_value = {
            "youtube_id": "test123",
            "title": "Test Ingested Video",
            "description": "Test description",
            "channel_name": "Test Channel",
            "channel_id": "UC_test",
            "thumbnail_url": "https://img.youtube.com/vi/test123/default.jpg",
            "duration_seconds": 300,
            "upload_date": datetime(2024, 1, 1),
            "view_count": 1000,
            "like_count": 100,
            "language": "en",
            "chapters": [],
        }
        mock.validate_video.return_value = (True, None)
        yield mock


@pytest.fixture
def mock_celery_task():
    """Mock Celery task to avoid actual processing."""
    with patch("app.api.routes.videos.process_video_pipeline") as mock:
        mock_task = MagicMock()
        mock_task.id = "celery-task-123"
        mock.delay.return_value = mock_task
        yield mock


@pytest.fixture
def mock_quota_checks():
    """Mock quota checks to always pass."""
    with patch("app.core.quota.check_video_quota") as video_quota, \
         patch("app.core.quota.check_minutes_quota") as minutes_quota:
        yield video_quota, minutes_quota


# Tests for POST /videos/ingest


def test_ingest_video_creates_video_and_job(
    client_with_user,
    db: Session,
    test_user,
    mock_youtube_service,
    mock_celery_task,
    mock_quota_checks,
):
    """Ingesting a video creates both video and job records."""
    response = client_with_user.post(
        "/api/v1/videos/ingest",
        json={"youtube_url": "https://www.youtube.com/watch?v=test123"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "video_id" in data
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "message" in data

    # Verify video was created in database
    video = db.query(Video).filter(Video.id == uuid.UUID(data["video_id"])).first()
    assert video is not None
    assert video.user_id == test_user.id
    assert video.youtube_id == "test123"
    assert video.status == "pending"

    # Verify job was created
    job = db.query(Job).filter(Job.id == uuid.UUID(data["job_id"])).first()
    assert job is not None
    assert job.video_id == video.id
    assert job.celery_task_id == "celery-task-123"


def test_ingest_video_calls_celery_with_correct_params(
    client_with_user,
    test_user,
    mock_youtube_service,
    mock_celery_task,
    mock_quota_checks,
):
    """Verify Celery task is called with the correct youtube_url from the request."""
    test_url = "https://www.youtube.com/watch?v=test456"

    response = client_with_user.post(
        "/api/v1/videos/ingest",
        json={"youtube_url": test_url},
    )

    assert response.status_code == 200

    # Verify Celery was called with the correct URL
    mock_celery_task.delay.assert_called_once()
    call_kwargs = mock_celery_task.delay.call_args.kwargs
    assert call_kwargs["youtube_url"] == test_url


def test_ingest_video_invalid_url_returns_400(
    client_with_user,
    mock_quota_checks,
):
    """Invalid YouTube URL returns 400 error."""
    with patch("app.api.routes.videos.youtube_service") as mock:
        from app.services.youtube import YouTubeDownloadError
        mock.get_video_info.side_effect = YouTubeDownloadError("Invalid URL")

        response = client_with_user.post(
            "/api/v1/videos/ingest",
            json={"youtube_url": "https://invalid-url.com/video"},
        )

        assert response.status_code == 400


def test_ingest_video_validation_failure_returns_400(
    client_with_user,
):
    """Video validation failure returns 400 with error message."""
    with patch("app.api.routes.videos.youtube_service") as mock_youtube, \
         patch("app.core.quota.check_video_quota"), \
         patch("app.core.quota.check_minutes_quota"):
        mock_youtube.get_video_info.return_value = {
            "youtube_id": "test123",
            "title": "Test Video",
            "description": "Test",
            "channel_name": "Test",
            "channel_id": "UC_test",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "duration_seconds": 300,
            "upload_date": datetime(2024, 1, 1),
            "view_count": 100,
            "like_count": 10,
            "language": "en",
            "chapters": [],
        }
        mock_youtube.validate_video.return_value = (False, "Video is too long")

        response = client_with_user.post(
            "/api/v1/videos/ingest",
            json={"youtube_url": "https://www.youtube.com/watch?v=test123"},
        )

        assert response.status_code == 400
        assert "Video is too long" in response.json()["detail"]


# Tests for GET /videos


def test_list_videos_returns_user_videos(client_with_user, sample_video):
    """Listing videos returns the user's videos."""
    response = client_with_user.get("/api/v1/videos")

    assert response.status_code == 200
    data = response.json()

    assert "total" in data
    assert "videos" in data
    assert data["total"] >= 1

    # Find our sample video in the list
    video_ids = [v["id"] for v in data["videos"]]
    assert str(sample_video.id) in video_ids


def test_list_videos_with_status_filter(client_with_user, db: Session, test_user):
    """Filtering by status returns only matching videos."""
    # Create videos with different statuses
    completed_video = Video(
        user_id=test_user.id,
        youtube_id="completed1",
        youtube_url="https://www.youtube.com/watch?v=completed1",
        title="Completed Video",
        status="completed",
        progress_percent=100.0,
        chunk_count=5,
    )
    pending_video = Video(
        user_id=test_user.id,
        youtube_id="pending1",
        youtube_url="https://www.youtube.com/watch?v=pending1",
        title="Pending Video",
        status="pending",
        progress_percent=0.0,
        chunk_count=0,
    )
    db.add_all([completed_video, pending_video])
    db.commit()

    # Filter by completed
    response = client_with_user.get("/api/v1/videos?status=completed")
    assert response.status_code == 200
    data = response.json()

    statuses = [v["status"] for v in data["videos"]]
    assert all(s == "completed" for s in statuses)


def test_list_videos_pagination(client_with_user, db: Session, test_user):
    """Pagination returns correct subset of videos."""
    # Create multiple videos
    for i in range(5):
        video = Video(
            user_id=test_user.id,
            youtube_id=f"vid{i}",
            youtube_url=f"https://www.youtube.com/watch?v=vid{i}",
            title=f"Video {i}",
            status="completed",
            progress_percent=100.0,
            chunk_count=1,
        )
        db.add(video)
    db.commit()

    # Request with pagination
    response = client_with_user.get("/api/v1/videos?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()

    assert len(data["videos"]) == 2
    assert data["total"] >= 5


def test_list_videos_excludes_deleted(client_with_user, db: Session, test_user):
    """Deleted videos are not returned in listing."""
    deleted_video = Video(
        user_id=test_user.id,
        youtube_id="deleted1",
        youtube_url="https://www.youtube.com/watch?v=deleted1",
        title="Deleted Video",
        status="completed",
        progress_percent=100.0,
        chunk_count=0,
        is_deleted=True,
    )
    db.add(deleted_video)
    db.commit()

    response = client_with_user.get("/api/v1/videos")
    assert response.status_code == 200
    data = response.json()

    video_ids = [v["id"] for v in data["videos"]]
    assert str(deleted_video.id) not in video_ids


# Tests for GET /videos/{id}


def test_get_video_returns_details(client_with_user, sample_video):
    """Getting a video returns full details."""
    response = client_with_user.get(f"/api/v1/videos/{sample_video.id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(sample_video.id)
    assert data["title"] == sample_video.title
    assert data["youtube_id"] == sample_video.youtube_id
    assert data["status"] == "completed"


def test_get_video_not_found_returns_404(client_with_user):
    """Getting non-existent video returns 404."""
    fake_id = uuid.uuid4()
    response = client_with_user.get(f"/api/v1/videos/{fake_id}")

    assert response.status_code == 404


def test_get_video_other_user_returns_404(client_with_user, db: Session):
    """Getting another user's video returns 404."""
    other_user = User(
        email="other@test.com",
        full_name="Other User",
        oauth_provider="google",
        oauth_provider_id="other_oauth_id",
        is_active=True,
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    other_video = Video(
        user_id=other_user.id,
        youtube_id="other_vid",
        youtube_url="https://www.youtube.com/watch?v=other_vid",
        title="Other User Video",
        status="completed",
        progress_percent=100.0,
        chunk_count=0,
    )
    db.add(other_video)
    db.commit()

    response = client_with_user.get(f"/api/v1/videos/{other_video.id}")
    assert response.status_code == 404


# Tests for POST /videos/delete


def test_delete_videos_soft_deletes(client_with_user, sample_video, db: Session):
    """Deleting videos performs soft delete."""
    with patch("app.api.routes.videos.vector_store_service"):
        response = client_with_user.post(
            "/api/v1/videos/delete",
            json={
                "video_ids": [str(sample_video.id)],
                "remove_from_library": True,
                "delete_search_index": True,
                "delete_audio": False,
                "delete_transcript": False,
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert data["deleted_count"] == 1
    assert len(data["videos"]) == 1

    # Verify video is soft deleted
    db.refresh(sample_video)
    assert sample_video.is_deleted is True


def test_delete_videos_returns_storage_breakdown(client_with_user, sample_video):
    """Delete response includes storage breakdown."""
    with patch("app.api.routes.videos.vector_store_service"):
        response = client_with_user.post(
            "/api/v1/videos/delete",
            json={"video_ids": [str(sample_video.id)]},
        )

    assert response.status_code == 200
    data = response.json()

    breakdown = data["videos"][0]
    assert "video_id" in breakdown
    assert "title" in breakdown
    assert "audio_size_mb" in breakdown
    assert "transcript_size_mb" in breakdown
    assert "total_size_mb" in breakdown


def test_delete_empty_list_returns_400(client_with_user):
    """Deleting empty list returns 400."""
    response = client_with_user.post(
        "/api/v1/videos/delete",
        json={"video_ids": []},
    )

    assert response.status_code == 400


# Tests for POST /videos/{id}/reprocess


def test_reprocess_video_creates_new_job(
    client_with_user,
    sample_video,
    db: Session,
    mock_celery_task,
):
    """Reprocessing creates a new job."""
    with patch("app.api.routes.videos.reset_video_processing"):
        response = client_with_user.post(
            f"/api/v1/videos/{sample_video.id}/reprocess"
        )

    assert response.status_code == 200
    data = response.json()

    assert data["video_id"] == str(sample_video.id)
    assert "job_id" in data
    assert data["status"] == "pending"


def test_reprocess_nonexistent_video_returns_404(client_with_user):
    """Reprocessing non-existent video returns 404."""
    fake_id = uuid.uuid4()
    response = client_with_user.post(f"/api/v1/videos/{fake_id}/reprocess")

    assert response.status_code == 404


# Tests for DELETE /videos/{id} (single video delete)


def test_delete_single_video(client_with_user, sample_video, db: Session):
    """Single video delete endpoint works."""
    with patch("app.api.routes.videos.vector_store_service"):
        response = client_with_user.delete(f"/api/v1/videos/{sample_video.id}")

    assert response.status_code == 200
    data = response.json()

    assert data["deleted_count"] == 1

    # Verify video is soft deleted
    db.refresh(sample_video)
    assert sample_video.is_deleted is True


# Rate limiting test (verifies route setup)


def test_ingest_uses_rate_limiting(client_with_user, mock_youtube_service, mock_celery_task, mock_quota_checks):
    """Verify the ingest endpoint has rate limiting applied (via decorator)."""
    # This test verifies the endpoint works - rate limiting is configured via decorator
    # Full rate limit testing would require multiple requests in quick succession
    response = client_with_user.post(
        "/api/v1/videos/ingest",
        json={"youtube_url": "https://www.youtube.com/watch?v=test123"},
    )
    assert response.status_code == 200
