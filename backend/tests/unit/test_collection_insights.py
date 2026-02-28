"""
Unit tests for collection insights service.

Tests cover:
- Getting video IDs from collection
- Caching behavior
- Empty collection handling
"""

import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.collection_insights import CollectionInsightsService
from app.models.collection_insight import CollectionInsight


class TestCollectionInsightsService:

    @pytest.fixture
    def service(self):
        return CollectionInsightsService()

    @pytest.fixture
    def mock_db(self):
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    def test_raises_on_empty_collection(self, service, mock_db):
        """Should raise ValueError when no completed videos in collection."""
        collection_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Mock _get_collection_video_ids to return empty
        with patch.object(
            CollectionInsightsService,
            "_get_collection_video_ids",
            return_value=[],
        ):
            with pytest.raises(ValueError, match="No completed videos"):
                service.get_or_generate_insights(
                    db=mock_db,
                    collection_id=collection_id,
                    user_id=user_id,
                )

    def test_returns_cached_insights_when_video_set_unchanged(self, service, mock_db):
        """Should return cached insights if video set hasn't changed."""
        collection_id = uuid.uuid4()
        user_id = uuid.uuid4()
        video_ids = [uuid.uuid4(), uuid.uuid4()]
        sorted_video_ids = sorted(video_ids, key=lambda v: str(v))

        existing = MagicMock(spec=CollectionInsight)
        existing.video_ids = sorted_video_ids
        existing.extraction_prompt_version = 4  # Matches current
        existing.graph_data = {
            "nodes": [{"id": "root", "type": "root"}],
            "edges": [],
        }

        # Mock query chain
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = existing
        mock_db.query.return_value = query_mock

        with patch.object(
            CollectionInsightsService,
            "_get_collection_video_ids",
            return_value=sorted_video_ids,
        ):
            result, was_cached = service.get_or_generate_insights(
                db=mock_db,
                collection_id=collection_id,
                user_id=user_id,
            )
            assert was_cached is True
            assert result == existing

    def test_force_regenerate_skips_cache(self, service, mock_db):
        """Should regenerate even when cache exists if force_regenerate=True."""
        collection_id = uuid.uuid4()
        user_id = uuid.uuid4()
        video_ids = [uuid.uuid4()]

        existing = MagicMock(spec=CollectionInsight)
        existing.video_ids = video_ids
        existing.extraction_prompt_version = 4

        # Mock query chain for existing lookup
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = existing
        mock_db.query.return_value = query_mock

        # Mock the extraction pipeline
        mock_insight_graph = MagicMock()
        mock_insight_graph.graph_dict.return_value = {"nodes": [], "edges": []}
        mock_insight_graph.topic_chunks_dict.return_value = {}
        mock_insight_graph.metadata = {
            "llm_provider": "deepseek",
            "llm_model": "deepseek-chat",
            "topics_count": 5,
            "total_chunks_analyzed": 20,
            "generation_time_seconds": 3.5,
        }

        # Mock collection lookup
        collection_mock = MagicMock()
        collection_mock.name = "Test Collection"

        with patch.object(
            CollectionInsightsService,
            "_get_collection_video_ids",
            return_value=video_ids,
        ), patch.object(
            service._insights_service,
            "extract_topics_from_videos",
            return_value=mock_insight_graph,
        ):
            # Override the db.query for collection lookup
            def query_side_effect(model):
                q = MagicMock()
                q.filter.return_value = q
                q.order_by.return_value = q
                if model == CollectionInsight:
                    q.first.return_value = existing
                else:
                    q.first.return_value = collection_mock
                return q

            mock_db.query.side_effect = query_side_effect

            result, was_cached = service.get_or_generate_insights(
                db=mock_db,
                collection_id=collection_id,
                user_id=user_id,
                force_regenerate=True,
            )
            assert was_cached is False

    def test_get_collection_video_ids_static_method(self):
        """Test the static helper returns video IDs from join."""
        mock_db = Mock(spec=Session)
        collection_id = uuid.uuid4()
        user_id = uuid.uuid4()

        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        # Build mock query chain
        query_mock = MagicMock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = [(vid1,), (vid2,)]
        mock_db.query.return_value = query_mock

        result = CollectionInsightsService._get_collection_video_ids(
            mock_db, collection_id, user_id
        )
        assert len(result) == 2
        assert vid1 in result
        assert vid2 in result
