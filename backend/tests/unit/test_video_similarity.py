"""
Unit tests for video similarity search (Jaccard on key_topics).

Tests Jaccard calculation, ranking, edge cases, and filtering.
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.services.theme_service import ThemeService


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_video(video_id=None, key_topics=None, title="Test Video"):
    video = MagicMock()
    video.id = video_id or uuid.uuid4()
    video.title = title
    video.key_topics = key_topics
    video.is_deleted = False
    video.content_type = "youtube"
    video.thumbnail_url = None
    video.duration_seconds = 600
    return video


@pytest.fixture
def service():
    return ThemeService()


# ── Jaccard Similarity Tests ─────────────────────────────────────────────


class TestJaccardSimilarity:
    def test_identical_sets(self, service):
        assert service._jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self, service):
        assert service._jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self, service):
        # {a, b, c} & {b, c, d} = {b, c}, union = {a, b, c, d}
        result = service._jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert result == pytest.approx(0.5)

    def test_single_shared(self, service):
        # {a, b} & {a, c} = {a}, union = {a, b, c}
        result = service._jaccard_similarity({"a", "b"}, {"a", "c"})
        assert result == pytest.approx(1 / 3)

    def test_empty_first_set(self, service):
        assert service._jaccard_similarity(set(), {"a", "b"}) == 0.0

    def test_empty_second_set(self, service):
        assert service._jaccard_similarity({"a", "b"}, set()) == 0.0

    def test_both_empty(self, service):
        assert service._jaccard_similarity(set(), set()) == 0.0

    def test_subset(self, service):
        # {a} & {a, b, c} = {a}, union = {a, b, c}
        result = service._jaccard_similarity({"a"}, {"a", "b", "c"})
        assert result == pytest.approx(1 / 3)


# ── Find Similar Videos Tests ────────────────────────────────────────────


class TestFindSimilarVideos:
    def test_basic_similarity(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["AI", "Machine Learning", "Python"],
        )
        source.user_id = user_id

        candidate1 = _make_video(
            key_topics=["AI", "Machine Learning", "Java"],
            title="Similar Video",
        )
        candidate2 = _make_video(
            key_topics=["Cooking", "Recipes"],
            title="Different Video",
        )

        db = MagicMock()
        # First query: get source video
        db.query.return_value.filter.return_value.first.return_value = source
        # Second query: get candidate videos
        db.query.return_value.filter.return_value.all.return_value = [
            candidate1,
            candidate2,
        ]

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )

        # Only the similar video should be returned (cooking has 0 overlap)
        assert len(result) == 1
        assert result[0]["title"] == "Similar Video"
        assert result[0]["similarity"] > 0
        assert "ai" in result[0]["shared_topics"]
        assert "machine learning" in result[0]["shared_topics"]

    def test_source_no_topics(self, service):
        db = MagicMock()
        source = _make_video(key_topics=None)
        db.query.return_value.filter.return_value.first.return_value = source

        result = service.find_similar_videos(
            db=db, video_id=source.id, user_id=uuid.uuid4()
        )
        assert result == []

    def test_source_empty_topics(self, service):
        db = MagicMock()
        source = _make_video(key_topics=[])
        db.query.return_value.filter.return_value.first.return_value = source

        result = service.find_similar_videos(
            db=db, video_id=source.id, user_id=uuid.uuid4()
        )
        assert result == []

    def test_source_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = service.find_similar_videos(
            db=db, video_id=uuid.uuid4(), user_id=uuid.uuid4()
        )
        assert result == []

    def test_no_candidates(self, service):
        source_id = uuid.uuid4()
        db = MagicMock()
        source = _make_video(video_id=source_id, key_topics=["AI"])
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = []

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=uuid.uuid4()
        )
        assert result == []

    def test_ranking_order(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["AI", "ML", "Python", "Data Science"],
        )
        source.user_id = user_id

        # High similarity - 3 out of 5 shared
        high_match = _make_video(
            key_topics=["AI", "ML", "Python"],
            title="High Match",
        )
        # Low similarity - 1 out of 5 shared
        low_match = _make_video(
            key_topics=["AI", "Cooking"],
            title="Low Match",
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = [
            low_match,
            high_match,
        ]

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )

        assert len(result) == 2
        assert result[0]["title"] == "High Match"
        assert result[1]["title"] == "Low Match"
        assert result[0]["similarity"] > result[1]["similarity"]

    def test_limit_results(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["AI"],
        )
        source.user_id = user_id

        candidates = [
            _make_video(key_topics=["AI"], title=f"Video {i}") for i in range(10)
        ]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = candidates

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id, limit=3
        )
        assert len(result) == 3

    def test_min_similarity_filter(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["AI", "ML", "Python", "Data", "Stats", "Math", "Linear Algebra", "Calculus", "NLP", "CV"],
        )
        source.user_id = user_id

        # Very low overlap: 1/19 = ~0.05
        weak_candidate = _make_video(
            key_topics=["AI", "Cooking", "Baking", "Recipes", "Kitchen",
                         "Grilling", "Sushi", "Pasta", "Pizza", "Salads"],
            title="Weak Match",
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = [weak_candidate]

        # Default min_similarity=0.1 should filter out very weak matches
        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )
        assert len(result) == 0

    def test_normalization_in_similarity(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["Machine Learning"],
        )
        source.user_id = user_id

        candidate = _make_video(
            key_topics=["machine learning"],
            title="Same Topic",
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = [candidate]

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )
        assert len(result) == 1
        assert result[0]["similarity"] == 1.0

    def test_shared_topics_sorted(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        source = _make_video(
            video_id=source_id,
            key_topics=["Python", "AI", "ML"],
        )
        source.user_id = user_id

        candidate = _make_video(
            key_topics=["ML", "Python"],
            title="Match",
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = [candidate]

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )
        assert result[0]["shared_topics"] == ["ml", "python"]  # alphabetically sorted

    def test_video_id_as_string(self, service):
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()
        candidate_id = uuid.uuid4()

        source = _make_video(video_id=source_id, key_topics=["AI"])
        source.user_id = user_id
        candidate = _make_video(video_id=candidate_id, key_topics=["AI"])

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source
        db.query.return_value.filter.return_value.all.return_value = [candidate]

        result = service.find_similar_videos(
            db=db, video_id=source_id, user_id=user_id
        )
        assert result[0]["video_id"] == str(candidate_id)
