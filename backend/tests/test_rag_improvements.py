"""
Unit tests for RAG retrieval improvements.

Tests:
1. Reranker service functionality
2. Relevance threshold filtering
3. Improved context construction
4. Configuration settings
5. API endpoint integration
"""
import pytest
import sys
import uuid
from unittest.mock import patch
import numpy as np

sys.path.insert(0, "/app")

from app.core.config import settings
from app.services.reranker import reranker_service
from app.services.vector_store import ScoredChunk


class TestConfigurationSettings:
    """Test configuration settings for RAG improvements."""

    def test_min_relevance_score_exists(self):
        """Verify MIN_RELEVANCE_SCORE is configured."""
        assert hasattr(
            settings, "min_relevance_score"
        ), "min_relevance_score should be in settings"

    def test_min_relevance_score_value(self):
        """Verify MIN_RELEVANCE_SCORE has correct default value."""
        assert (
            settings.min_relevance_score == 0.50
        ), f"Expected min_relevance_score=0.50, got {settings.min_relevance_score}"

    def test_enable_reranking_exists(self):
        """Verify ENABLE_RERANKING is configured."""
        assert hasattr(
            settings, "enable_reranking"
        ), "enable_reranking should be in settings"

    def test_retrieval_top_k_value(self):
        """Verify RETRIEVAL_TOP_K has correct value."""
        assert (
            settings.retrieval_top_k == 20
        ), f"Expected retrieval_top_k=20, got {settings.retrieval_top_k}"

    def test_reranking_top_k_value(self):
        """Verify RERANKING_TOP_K has correct value."""
        assert (
            settings.reranking_top_k == 7
        ), f"Expected reranking_top_k=7, got {settings.reranking_top_k}"

    def test_reranking_model_exists(self):
        """Verify reranking model is configured."""
        assert hasattr(
            settings, "reranking_model"
        ), "reranking_model should be in settings"
        assert (
            "cross-encoder" in settings.reranking_model
        ), f"Expected cross-encoder model, got {settings.reranking_model}"


class TestRerankerService:
    """Test the reranker service functionality."""

    def test_reranker_service_exists(self):
        """Verify reranker service module exists."""
        assert reranker_service is not None, "reranker_service should exist"

    def test_reranker_has_rerank_method(self):
        """Verify reranker has rerank method."""
        assert hasattr(
            reranker_service, "rerank"
        ), "reranker_service should have rerank method"

    def test_rerank_empty_chunks(self):
        """Test reranking with empty chunk list."""
        result = reranker_service.rerank(query="test query", chunks=[], top_k=5)
        assert result == [], "Empty input should return empty list"

    def test_rerank_returns_list(self):
        """Test that rerank returns a list."""
        # Create mock chunks
        mock_chunk = ScoredChunk(
            chunk_id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            text="Test chunk content about machine learning",
            score=0.8,
            start_timestamp=0.0,
            end_timestamp=10.0,
            title="Test Title",
            keywords=["test"],
            chapter_title="Test Chapter",
            speakers=["Speaker 1"],
        )

        # Test with mocked model to avoid loading actual model
        with patch.object(reranker_service, "_model", None):
            with patch.object(reranker_service, "_ensure_model"):
                with patch.object(reranker_service, "_model") as mock_model:
                    mock_model.predict.return_value = [0.9]
                    reranker_service._model = mock_model

                    result = reranker_service.rerank(
                        query="machine learning", chunks=[mock_chunk], top_k=5
                    )

                    assert isinstance(result, list), "Result should be a list"


class TestRelevanceThresholdFiltering:
    """Test relevance threshold filtering logic."""

    def test_threshold_filtering_removes_low_scores(self):
        """Test that chunks below threshold are filtered out."""
        chunks = [
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                video_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                text="High relevance chunk",
                score=0.85,
                start_timestamp=0.0,
                end_timestamp=10.0,
            ),
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                video_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                text="Low relevance chunk",
                score=0.30,
                start_timestamp=10.0,
                end_timestamp=20.0,
            ),
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                video_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                text="Medium relevance chunk",
                score=0.55,
                start_timestamp=20.0,
                end_timestamp=30.0,
            ),
        ]

        # Apply threshold filtering (as done in conversations.py)
        min_threshold = settings.min_relevance_score
        filtered = [c for c in chunks if c.score >= min_threshold]

        assert (
            len(filtered) == 2
        ), f"Expected 2 chunks after filtering at {min_threshold}, got {len(filtered)}"
        assert all(
            c.score >= min_threshold for c in filtered
        ), "All filtered chunks should be above threshold"

    def test_threshold_filtering_preserves_high_scores(self):
        """Test that high-scoring chunks are preserved."""
        chunks = [
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                video_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                text="High score chunk 1",
                score=0.90,
                start_timestamp=0.0,
                end_timestamp=10.0,
            ),
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                video_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                text="High score chunk 2",
                score=0.75,
                start_timestamp=10.0,
                end_timestamp=20.0,
            ),
        ]

        min_threshold = settings.min_relevance_score
        filtered = [c for c in chunks if c.score >= min_threshold]

        assert len(filtered) == 2, "All high-scoring chunks should be preserved"


class TestContextConstruction:
    """Test improved context construction."""

    def test_format_timestamp_display_function_exists(self):
        """Verify timestamp formatting function exists in conversations module."""
        from app.api.routes.conversations import _format_timestamp_display

        assert callable(
            _format_timestamp_display
        ), "_format_timestamp_display should be callable"

    def test_format_timestamp_minutes_seconds(self):
        """Test timestamp formatting for MM:SS format."""
        from app.api.routes.conversations import _format_timestamp_display

        result = _format_timestamp_display(65.0, 125.0)
        # Should be in format "01:05 - 02:05"
        assert "01:05" in result, f"Expected 01:05 in result, got {result}"
        assert "02:05" in result, f"Expected 02:05 in result, got {result}"

    def test_format_timestamp_hours(self):
        """Test timestamp formatting for HH:MM:SS format."""
        from app.api.routes.conversations import _format_timestamp_display

        result = _format_timestamp_display(3665.0, 3725.0)  # ~1h:01m:05s to ~1h:02m:05s
        # Should include hours
        assert "01:" in result, f"Expected hours in result, got {result}"

    def test_scored_chunk_has_required_attributes(self):
        """Test that ScoredChunk has all required attributes for context building."""
        chunk = ScoredChunk(
            chunk_id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            text="Test content",
            score=0.8,
            start_timestamp=0.0,
            end_timestamp=10.0,
            title="Test Title",
            keywords=["test"],
            chapter_title="Chapter 1",
            speakers=["Speaker 1"],
        )

        # Check required attributes for improved context
        assert hasattr(chunk, "video_id"), "chunk should have video_id"
        assert hasattr(chunk, "speakers"), "chunk should have speakers"
        assert hasattr(chunk, "chapter_title"), "chunk should have chapter_title"
        assert hasattr(chunk, "title"), "chunk should have title"
        assert hasattr(chunk, "start_timestamp"), "chunk should have start_timestamp"
        assert hasattr(chunk, "end_timestamp"), "chunk should have end_timestamp"
        assert hasattr(chunk, "score"), "chunk should have score"


class TestEmbeddingService:
    """Test embedding service functionality."""

    def test_embedding_service_exists(self):
        """Verify embedding service is properly initialized."""
        from app.services.embeddings import embedding_service

        assert embedding_service is not None, "embedding_service should exist"

    def test_embedding_dimensions(self):
        """Test that embeddings have correct dimensions."""
        from app.services.embeddings import embedding_service

        text = "Test embedding text"
        embedding = embedding_service.embed_text(text)

        # Convert tuple to array if needed
        if isinstance(embedding, tuple):
            embedding = np.array(embedding)

        expected_dimensions = embedding_service.get_dimensions()
        assert (
            len(embedding) == expected_dimensions
        ), f"Expected {expected_dimensions} dimensions, got {len(embedding)}"

    def test_embedding_normalization(self):
        """Test that embeddings are normalized to unit vectors."""
        from app.services.embeddings import embedding_service

        text = "Test normalization"
        embedding = embedding_service.embed_text(text)

        if isinstance(embedding, tuple):
            embedding = np.array(embedding)

        # Check if normalized (magnitude should be ~1.0)
        magnitude = np.linalg.norm(embedding)
        assert (
            abs(magnitude - 1.0) < 0.01
        ), f"Embedding should be normalized, got magnitude {magnitude}"


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    def test_conversations_module_imports(self):
        """Test that conversations module imports successfully."""
        try:
            from app.api.routes import conversations

            assert conversations is not None
        except ImportError as e:
            pytest.fail(f"Failed to import conversations module: {e}")

    def test_reranker_imported_in_conversations(self):
        """Verify reranker is imported in conversations module."""
        from app.api.routes import conversations

        # Check if reranker_service is used in module
        source_file = conversations.__file__
        with open(source_file, "r") as f:
            source_code = f.read()

        assert (
            "reranker_service" in source_code
        ), "reranker_service should be imported in conversations"

    def test_min_relevance_score_used_in_conversations(self):
        """Verify min_relevance_score is used in conversations module."""
        from app.api.routes import conversations

        source_file = conversations.__file__
        with open(source_file, "r") as f:
            source_code = f.read()

        assert (
            "min_relevance_score" in source_code
        ), "min_relevance_score should be used in conversations"


class TestVectorStore:
    """Test vector store functionality."""

    def test_vector_store_service_exists(self):
        """Verify vector store service exists."""
        from app.services.vector_store import vector_store_service

        assert vector_store_service is not None, "vector_store_service should exist"

    def test_search_chunks_method_exists(self):
        """Verify search_chunks method exists."""
        from app.services.vector_store import vector_store_service

        assert hasattr(
            vector_store_service, "search_chunks"
        ), "vector_store_service should have search_chunks method"


class TestNoContextWarning:
    """Test no-context warning functionality."""

    def test_warning_message_in_code(self):
        """Verify warning message is in conversations code."""
        from app.api.routes import conversations

        source_file = conversations.__file__
        with open(source_file, "r") as f:
            source_code = f.read()

        assert (
            "WARNING" in source_code
        ), "No-context WARNING should be in conversations code"
        assert (
            "No relevant content found" in source_code
        ), "No relevant content message should be in code"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
