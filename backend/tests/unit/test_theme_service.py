"""
Unit tests for the ThemeService.

Tests theme aggregation, normalization, caching, and edge cases.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.theme_service import (
    ThemeService,
    THEME_CACHE_TTL_SECONDS,
    MAX_THEMES_PER_COLLECTION,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_video(video_id=None, key_topics=None):
    video = MagicMock()
    video.id = video_id or uuid.uuid4()
    video.key_topics = key_topics
    video.is_deleted = False
    return video


def _make_collection(collection_id=None, meta=None):
    collection = MagicMock()
    collection.id = collection_id or uuid.uuid4()
    collection.user_id = uuid.uuid4()
    collection.is_deleted = False
    collection.meta = meta or {}
    return collection


@pytest.fixture
def service():
    return ThemeService()


# ── Normalization Tests ──────────────────────────────────────────────────


class TestNormalization:
    def test_lowercase(self, service):
        assert service._normalize_topic("Machine Learning") == "machine learning"

    def test_strip_whitespace(self, service):
        assert service._normalize_topic("  AI  ") == "ai"

    def test_already_normalized(self, service):
        assert service._normalize_topic("python") == "python"

    def test_empty_string(self, service):
        assert service._normalize_topic("") == ""

    def test_mixed_case_and_whitespace(self, service):
        assert service._normalize_topic("  Deep Learning  ") == "deep learning"


# ── Theme Computation Tests ──────────────────────────────────────────────


class TestThemeComputation:
    def test_basic_aggregation(self, service):
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        videos = [
            _make_video(video_id=vid1, key_topics=["AI", "Machine Learning"]),
            _make_video(video_id=vid2, key_topics=["AI", "Python"]),
        ]
        themes = service._compute_themes(videos)

        # AI appears in both videos, should be first
        assert len(themes) == 3
        assert themes[0]["topic"] == "ai"
        assert themes[0]["count"] == 2
        assert len(themes[0]["video_ids"]) == 2

    def test_frequency_ranking(self, service):
        videos = [
            _make_video(key_topics=["Python", "AI"]),
            _make_video(key_topics=["Python", "ML"]),
            _make_video(key_topics=["Python", "AI"]),
        ]
        themes = service._compute_themes(videos)

        assert themes[0]["topic"] == "python"
        assert themes[0]["count"] == 3
        assert themes[1]["topic"] == "ai"
        assert themes[1]["count"] == 2

    def test_normalization_merges_variants(self, service):
        videos = [
            _make_video(key_topics=["Machine Learning"]),
            _make_video(key_topics=["machine learning"]),
            _make_video(key_topics=["  Machine Learning  "]),
        ]
        themes = service._compute_themes(videos)

        assert len(themes) == 1
        assert themes[0]["topic"] == "machine learning"
        assert themes[0]["count"] == 3

    def test_empty_videos(self, service):
        themes = service._compute_themes([])
        assert themes == []

    def test_videos_with_no_topics(self, service):
        videos = [
            _make_video(key_topics=None),
            _make_video(key_topics=[]),
        ]
        themes = service._compute_themes(videos)
        assert themes == []

    def test_cap_at_max_themes(self, service):
        # Create 25 unique topics
        topics = [f"topic_{i}" for i in range(25)]
        videos = [_make_video(key_topics=topics)]
        themes = service._compute_themes(videos)

        assert len(themes) == MAX_THEMES_PER_COLLECTION

    def test_video_ids_are_strings(self, service):
        vid = uuid.uuid4()
        videos = [_make_video(video_id=vid, key_topics=["AI"])]
        themes = service._compute_themes(videos)

        assert themes[0]["video_ids"] == [str(vid)]

    def test_no_duplicate_video_ids(self, service):
        vid = uuid.uuid4()
        videos = [_make_video(video_id=vid, key_topics=["AI", "AI"])]
        themes = service._compute_themes(videos)

        # Same video should only appear once even if topic listed twice
        assert themes[0]["video_ids"] == [str(vid)]
        assert themes[0]["count"] == 2  # counted twice though

    def test_alphabetical_tiebreak(self, service):
        videos = [
            _make_video(key_topics=["Zebra", "Alpha"]),
        ]
        themes = service._compute_themes(videos)

        # Both have count=1, so alphabetical order
        assert themes[0]["topic"] == "alpha"
        assert themes[1]["topic"] == "zebra"


# ── Cache Tests ──────────────────────────────────────────────────────────


class TestCaching:
    def test_cache_hit(self, service):
        cached_themes = [{"topic": "ai", "count": 3, "video_ids": ["id1"]}]
        collection = _make_collection(
            meta={
                "cached_themes": cached_themes,
                "cached_themes_at": datetime.utcnow().isoformat(),
            }
        )

        result = service._get_cached_themes(collection)
        assert result == cached_themes

    def test_cache_miss_no_data(self, service):
        collection = _make_collection(meta={})
        result = service._get_cached_themes(collection)
        assert result is None

    def test_cache_miss_expired(self, service):
        expired_time = datetime.utcnow() - timedelta(
            seconds=THEME_CACHE_TTL_SECONDS + 60
        )
        collection = _make_collection(
            meta={
                "cached_themes": [{"topic": "ai", "count": 1, "video_ids": []}],
                "cached_themes_at": expired_time.isoformat(),
            }
        )

        result = service._get_cached_themes(collection)
        assert result is None

    def test_cache_miss_invalid_timestamp(self, service):
        collection = _make_collection(
            meta={
                "cached_themes": [{"topic": "ai", "count": 1, "video_ids": []}],
                "cached_themes_at": "not-a-date",
            }
        )

        result = service._get_cached_themes(collection)
        assert result is None

    def test_cache_miss_none_meta(self, service):
        collection = _make_collection()
        collection.meta = None
        result = service._get_cached_themes(collection)
        assert result is None

    def test_cache_write(self, service):
        db = MagicMock()
        collection = _make_collection(meta={"existing_key": "value"})
        themes = [{"topic": "ai", "count": 2, "video_ids": ["id1"]}]

        service._cache_themes(db, collection, themes)

        # Check meta was updated
        assert collection.meta["cached_themes"] == themes
        assert "cached_themes_at" in collection.meta
        # Existing keys preserved
        assert collection.meta["existing_key"] == "value"
        db.commit.assert_called_once()


# ── Integration-like Tests ───────────────────────────────────────────────


class TestAggregateCollectionThemes:
    def test_collection_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = service.aggregate_collection_themes(
            db=db,
            collection_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
        assert result == []

    def test_uses_cache_when_available(self, service):
        db = MagicMock()
        cached_themes = [{"topic": "cached", "count": 1, "video_ids": ["x"]}]
        collection = _make_collection(
            meta={
                "cached_themes": cached_themes,
                "cached_themes_at": datetime.utcnow().isoformat(),
            }
        )
        db.query.return_value.filter.return_value.first.return_value = collection

        result = service.aggregate_collection_themes(
            db=db,
            collection_id=collection.id,
            user_id=collection.user_id,
        )
        assert result == cached_themes

    def test_force_refresh_bypasses_cache(self, service):
        db = MagicMock()
        cached_themes = [{"topic": "cached", "count": 1, "video_ids": ["x"]}]
        collection = _make_collection(
            meta={
                "cached_themes": cached_themes,
                "cached_themes_at": datetime.utcnow().isoformat(),
            }
        )
        db.query.return_value.filter.return_value.first.return_value = collection

        # When forcing refresh, the DB query for videos will run
        videos = [_make_video(key_topics=["fresh topic"])]
        db.query.return_value.join.return_value.filter.return_value.all.return_value = (
            videos
        )

        result = service.aggregate_collection_themes(
            db=db,
            collection_id=collection.id,
            user_id=collection.user_id,
            force_refresh=True,
        )
        assert len(result) == 1
        assert result[0]["topic"] == "fresh topic"
