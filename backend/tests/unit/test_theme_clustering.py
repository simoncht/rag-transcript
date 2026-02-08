"""
Unit tests for LLM-powered theme clustering (Phase 4).

Tests k selection, clustering, LLM labeling, and persistence.
"""
import json
import uuid
from collections import Counter
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.theme_service import ThemeService


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_video(video_id=None, summary=None, key_topics=None, title="Test Video"):
    video = MagicMock()
    video.id = video_id or uuid.uuid4()
    video.title = title
    video.summary = summary
    video.key_topics = key_topics or []
    video.is_deleted = False
    video.content_type = "youtube"
    video.thumbnail_url = None
    video.duration_seconds = 600
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


# ── K Selection Tests ────────────────────────────────────────────────────


class TestKSelection:
    def test_minimum_k(self, service):
        assert service._select_k(3) == 2  # max(2, min(1, 10)) = 2
        assert service._select_k(5) == 2  # max(2, min(1, 10)) = 2

    def test_scales_with_videos(self, service):
        assert service._select_k(6) == 2
        assert service._select_k(9) == 3
        assert service._select_k(12) == 4
        assert service._select_k(30) == 10

    def test_capped_at_10(self, service):
        assert service._select_k(100) == 10
        assert service._select_k(50) == 10


# ── KMeans Clustering Tests ─────────────────────────────────────────────


class TestKMeansClustering:
    def test_basic_clustering(self, service):
        # 4 points, 2 obvious clusters
        embeddings = np.array([
            [0.0, 0.0],
            [0.1, 0.1],
            [10.0, 10.0],
            [10.1, 10.1],
        ])
        labels = service._run_kmeans(embeddings, k=2)

        assert len(labels) == 4
        # Points 0,1 should be in same cluster
        assert labels[0] == labels[1]
        # Points 2,3 should be in same cluster
        assert labels[2] == labels[3]
        # Different clusters
        assert labels[0] != labels[2]

    def test_single_cluster(self, service):
        embeddings = np.array([
            [1.0, 1.0],
            [1.1, 1.1],
            [0.9, 0.9],
        ])
        # k=1 isn't used but k=2 with tight data should still work
        labels = service._run_kmeans(embeddings, k=2)
        assert len(labels) == 3


# ── Group By Cluster Tests ──────────────────────────────────────────────


class TestGroupByCluster:
    def test_basic_grouping(self, service):
        videos = [
            _make_video(title="V1"),
            _make_video(title="V2"),
            _make_video(title="V3"),
        ]
        labels = np.array([0, 1, 0])

        groups = service._group_by_cluster(videos, labels)

        assert len(groups) == 2
        assert len(groups[0]) == 2  # V1, V3
        assert len(groups[1]) == 1  # V2

    def test_all_same_cluster(self, service):
        videos = [_make_video() for _ in range(3)]
        labels = np.array([0, 0, 0])

        groups = service._group_by_cluster(videos, labels)
        assert len(groups) == 1
        assert len(groups[0]) == 3


# ── LLM Label Cluster Tests ────────────────────────────────────────────


class TestLabelCluster:
    def test_label_with_llm_success(self, service):
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "label": "Machine Learning Fundamentals",
            "description": "Videos covering core ML concepts.",
        })

        with patch("app.services.theme_service.ThemeService._llm_label_cluster") as mock_llm:
            mock_llm.return_value = ("Machine Learning Fundamentals", "Videos covering core ML concepts.")

            videos = [
                _make_video(title="Intro to ML", key_topics=["machine learning", "AI"]),
                _make_video(title="Neural Networks", key_topics=["deep learning", "AI"]),
            ]

            result = service._label_cluster(0, videos)

            assert result["theme_label"] == "Machine Learning Fundamentals"
            assert result["theme_description"] == "Videos covering core ML concepts."
            assert len(result["video_ids"]) == 2

    def test_label_fallback_on_error(self, service):
        with patch("app.services.theme_service.ThemeService._llm_label_cluster") as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")

            videos = [
                _make_video(title="V1", key_topics=["AI", "Python"]),
                _make_video(title="V2", key_topics=["AI", "ML"]),
            ]

            result = service._label_cluster(0, videos)

            # Should fallback to top keywords
            assert "ai" in result["theme_label"].lower()
            assert result["theme_description"] == "Contains 2 videos"

    def test_label_no_topics_fallback(self, service):
        with patch("app.services.theme_service.ThemeService._llm_label_cluster") as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")

            videos = [
                _make_video(title="V1", key_topics=[]),
                _make_video(title="V2", key_topics=None),
            ]

            result = service._label_cluster(0, videos)

            assert result["theme_label"] == "Cluster 1"

    def test_topic_keywords_normalized(self, service):
        with patch("app.services.theme_service.ThemeService._llm_label_cluster") as mock_llm:
            mock_llm.return_value = ("Test Theme", "Test desc")

            videos = [
                _make_video(key_topics=["Machine Learning", "  AI  "]),
            ]

            result = service._label_cluster(0, videos)
            assert "machine learning" in result["topic_keywords"]
            assert "ai" in result["topic_keywords"]


# ── LLM Label Cluster Static Method Tests ───────────────────────────────


class TestLLMLabelClusterMethod:
    @patch("app.services.llm_providers.llm_service")
    def test_parses_json_response(self, mock_llm):
        mock_response = MagicMock()
        mock_response.content = '{"label": "AI Basics", "description": "Introduction to AI."}'
        mock_llm.complete.return_value = mock_response

        label, desc = ThemeService._llm_label_cluster(
            ["Intro to AI", "ML Basics"], ["ai", "machine learning"]
        )

        assert label == "AI Basics"
        assert desc == "Introduction to AI."

    @patch("app.services.llm_providers.llm_service")
    def test_handles_markdown_code_block(self, mock_llm):
        mock_response = MagicMock()
        mock_response.content = '```json\n{"label": "AI Basics", "description": "Test."}\n```'
        mock_llm.complete.return_value = mock_response

        label, desc = ThemeService._llm_label_cluster(["Title"], ["ai"])

        assert label == "AI Basics"
        assert desc == "Test."

    @patch("app.services.llm_providers.llm_service")
    def test_truncates_long_label(self, mock_llm):
        mock_response = MagicMock()
        long_label = "A" * 300
        mock_response.content = json.dumps({"label": long_label, "description": "Test"})
        mock_llm.complete.return_value = mock_response

        label, _ = ThemeService._llm_label_cluster(["Title"], ["ai"])
        assert len(label) <= 255


# ── Save Clustered Themes Tests ─────────────────────────────────────────


class TestSaveClusteredThemes:
    def test_saves_themes(self, service):
        db = MagicMock()
        collection_id = uuid.uuid4()
        themes = [
            {
                "theme_label": "AI Fundamentals",
                "theme_description": "Core AI concepts",
                "video_ids": [str(uuid.uuid4())],
                "relevance_score": 3.0,
                "topic_keywords": ["ai", "ml"],
            },
        ]

        with patch("app.models.collection_theme.CollectionTheme") as MockTheme:
            MockTheme.collection_id = collection_id
            service._save_clustered_themes(db, collection_id, themes)

        # Should delete old themes and add new ones
        db.query.return_value.filter.return_value.delete.assert_called_once()
        assert db.add.call_count == 1
        db.commit.assert_called_once()


# ── Full Clustering Pipeline Tests ──────────────────────────────────────


class TestClusterCollectionThemes:
    def test_too_few_videos_falls_back(self, service):
        db = MagicMock()
        collection = _make_collection()
        db.query.return_value.filter.return_value.first.return_value = collection

        # Only 2 videos with summaries (below MIN_VIDEOS_FOR_CLUSTERING=3)
        videos = [_make_video(summary="Summary") for _ in range(2)]
        db.query.return_value.join.return_value.filter.return_value.all.return_value = videos

        with patch.object(service, "aggregate_collection_themes") as mock_agg:
            mock_agg.return_value = [{"topic": "ai", "count": 1, "video_ids": []}]
            result = service.cluster_collection_themes(
                db=db,
                collection_id=collection.id,
                user_id=collection.user_id,
            )

        mock_agg.assert_called_once()

    def test_collection_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = service.cluster_collection_themes(
            db=db,
            collection_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
        assert result == []

    def test_embedding_failure_falls_back(self, service):
        db = MagicMock()
        collection = _make_collection()
        db.query.return_value.filter.return_value.first.return_value = collection

        videos = [_make_video(summary="Summary") for _ in range(5)]
        db.query.return_value.join.return_value.filter.return_value.all.return_value = videos

        with patch.object(service, "_embed_summaries", side_effect=Exception("embed failed")):
            with patch.object(service, "aggregate_collection_themes") as mock_agg:
                mock_agg.return_value = []
                result = service.cluster_collection_themes(
                    db=db,
                    collection_id=collection.id,
                    user_id=collection.user_id,
                )

        mock_agg.assert_called_once()

    def test_full_pipeline(self, service):
        db = MagicMock()
        collection = _make_collection()
        db.query.return_value.filter.return_value.first.return_value = collection

        videos = [
            _make_video(summary=f"Summary {i}", key_topics=[f"topic_{i}"])
            for i in range(6)
        ]
        db.query.return_value.join.return_value.filter.return_value.all.return_value = videos

        mock_embeddings = np.random.rand(6, 384)

        with patch.object(service, "_embed_summaries", return_value=mock_embeddings):
            with patch.object(service, "_llm_label_cluster") as mock_llm:
                mock_llm.return_value = ("Test Theme", "Description")
                with patch.object(service, "_save_clustered_themes"):
                    result = service.cluster_collection_themes(
                        db=db,
                        collection_id=collection.id,
                        user_id=collection.user_id,
                    )

        assert len(result) == 2  # k = max(2, min(6//3, 10)) = 2
        assert all("theme_label" in t for t in result)
        assert all("video_ids" in t for t in result)
