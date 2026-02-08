"""
Unit tests for BM25 hybrid search service.

Tests BM25SearchService, rrf_fuse(), _should_skip_bm25(),
and reranker score propagation (S4).
"""

import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.bm25_search import (
    BM25Result,
    BM25SearchService,
    _should_skip_bm25,
    _content_tokens,
    _tokenize,
    rrf_fuse,
)
from app.services.vector_store import ScoredChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scored_chunk(chunk_id=None, video_id=None, score=0.8, text="sample text"):
    return ScoredChunk(
        chunk_id=chunk_id or uuid4(),
        video_id=video_id or uuid4(),
        user_id=uuid4(),
        text=text,
        start_timestamp=0.0,
        end_timestamp=10.0,
        score=score,
    )


def _make_bm25_result(chunk_id=None, video_id=None, bm25_score=5.0, normalized_score=0.8):
    return BM25Result(
        chunk_id=chunk_id or uuid4(),
        video_id=video_id or uuid4(),
        user_id=uuid4(),
        text="bm25 text",
        embedding_text="bm25 embedding text",
        start_timestamp=0.0,
        end_timestamp=10.0,
        chunk_index=0,
        bm25_score=bm25_score,
        normalized_score=normalized_score,
    )


def _make_mock_chunk(
    chunk_id=None,
    video_id=None,
    user_id=None,
    text="sample text about kubernetes deployment",
    embedding_text=None,
):
    """Create a mock SQLAlchemy Chunk object."""
    mock = MagicMock()
    mock.id = chunk_id or uuid4()
    mock.video_id = video_id or uuid4()
    mock.user_id = user_id or uuid4()
    mock.text = text
    mock.embedding_text = embedding_text or f"Kubernetes Guide. Deployment overview\n\n{text}"
    mock.start_timestamp = 0.0
    mock.end_timestamp = 10.0
    mock.chunk_index = 0
    mock.content_type = "youtube"
    mock.page_number = None
    mock.section_heading = None
    mock.chunk_title = "Kubernetes Guide"
    mock.chunk_summary = "Deployment overview"
    mock.keywords = ["kubernetes", "deployment"]
    mock.chapter_title = None
    mock.speakers = None
    mock.is_indexed = True
    return mock


# ---------------------------------------------------------------------------
# _should_skip_bm25 tests (S6)
# ---------------------------------------------------------------------------


class TestShouldSkipBm25:
    def test_short_query_skipped(self):
        assert _should_skip_bm25("what?") is True

    def test_stopword_only_query_skipped(self):
        assert _should_skip_bm25("what is the") is True

    def test_two_content_words_skipped(self):
        assert _should_skip_bm25("kubernetes cluster") is True

    def test_three_content_words_allowed(self):
        assert _should_skip_bm25("kubernetes cluster deployment") is False

    def test_mixed_stopwords_and_content(self):
        # "how does kubernetes handle deployment scaling" -> 4 content words
        assert _should_skip_bm25("how does kubernetes handle deployment scaling") is False

    def test_empty_query_skipped(self):
        assert _should_skip_bm25("") is True

    def test_single_word_skipped(self):
        assert _should_skip_bm25("CRISPR") is True


class TestTokenize:
    def test_basic_tokenization(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_punctuation_handling(self):
        tokens = _tokenize("What is CRISPR-Cas9?")
        assert "crispr" in tokens
        assert "cas9" in tokens

    def test_content_tokens_filters_stopwords(self):
        tokens = _content_tokens("what is the kubernetes deployment process")
        assert "what" not in tokens
        assert "kubernetes" in tokens
        assert "deployment" in tokens
        assert "process" in tokens


# ---------------------------------------------------------------------------
# BM25SearchService tests
# ---------------------------------------------------------------------------


class TestBM25SearchService:
    def test_disabled_returns_empty(self):
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = False
            service = BM25SearchService()
            service._bm25_available = None
            result = service.search(
                db=MagicMock(), query="test", user_id=uuid4(), video_ids=[uuid4()]
            )
            assert result == []

    def test_no_video_ids_returns_empty(self):
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = True
            service = BM25SearchService()
            service._bm25_available = True
            result = service.search(
                db=MagicMock(), query="test", user_id=uuid4(), video_ids=[]
            )
            assert result == []

    def test_no_chunks_returns_empty(self):
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = True
            mock_settings.bm25_min_normalized_score = 0.25
            mock_settings.bm25_min_term_overlap = 2

            service = BM25SearchService()
            service._bm25_available = True

            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []
            mock_db.query.return_value = mock_query

            result = service.search(
                db=mock_db, query="kubernetes deployment", user_id=uuid4(), video_ids=[uuid4()]
            )
            assert result == []

    def test_returns_ranked_results(self):
        """BM25 ranks matching chunks higher. Needs 3+ docs for non-zero IDF."""
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = True
            mock_settings.bm25_min_normalized_score = 0.25
            mock_settings.bm25_min_term_overlap = 2

            service = BM25SearchService()
            service._bm25_available = True

            user_id = uuid4()
            video_id = uuid4()

            chunk1 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="kubernetes deployment scaling pods replicas",
                embedding_text="kubernetes deployment scaling pods replicas cluster service",
            )
            chunk2 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="docker container image registry push pull",
                embedding_text="docker container image registry push pull build layer",
            )
            # Need 3+ docs for BM25Okapi IDF to produce non-zero scores
            chunk3 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="python programming language data science machine learning",
                embedding_text="python programming language data science machine learning",
            )

            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [chunk1, chunk2, chunk3]
            mock_db.query.return_value = mock_query

            result = service.search(
                db=mock_db,
                query="kubernetes deployment scaling strategy",
                user_id=user_id,
                video_ids=[video_id],
                top_k=10,
            )

            # chunk1 should match (has kubernetes, deployment, scaling)
            assert len(result) >= 1
            assert result[0].chunk_id == chunk1.id

    def test_quality_gate_filters_low_scores(self):
        """Results below normalized threshold are filtered out."""
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = True
            mock_settings.bm25_min_normalized_score = 0.5  # High threshold
            mock_settings.bm25_min_term_overlap = 1  # Low overlap req

            service = BM25SearchService()
            service._bm25_available = True

            user_id = uuid4()
            video_id = uuid4()

            # Strong match
            chunk1 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="kubernetes kubernetes kubernetes deployment deployment",
                embedding_text="kubernetes kubernetes kubernetes deployment deployment scaling",
            )
            # Weak match (no query terms at all)
            chunk2 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="weather forecast today sunny warm temperature humidity",
                embedding_text="weather forecast today sunny warm temperature humidity",
            )
            # Third doc needed for BM25 IDF
            chunk3 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="python programming language data science machine learning",
                embedding_text="python programming language data science machine learning",
            )

            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [chunk1, chunk2, chunk3]
            mock_db.query.return_value = mock_query

            result = service.search(
                db=mock_db,
                query="kubernetes deployment",
                user_id=user_id,
                video_ids=[video_id],
            )

            # chunk2 should be filtered (no query terms, fails term overlap)
            chunk_ids = {r.chunk_id for r in result}
            assert chunk1.id in chunk_ids
            assert chunk2.id not in chunk_ids

    def test_term_overlap_filter(self):
        """Chunks with insufficient term overlap are filtered."""
        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.enable_bm25_search = True
            mock_settings.bm25_min_normalized_score = 0.0  # No score filter
            mock_settings.bm25_min_term_overlap = 3  # Need 3 term matches

            service = BM25SearchService()
            service._bm25_available = True

            user_id = uuid4()
            video_id = uuid4()

            # Only matches 1 query content term ("kubernetes")
            chunk1 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="kubernetes is a container orchestration platform",
                embedding_text="kubernetes container orchestration platform tools",
            )
            # Filler docs for BM25 IDF to work (need 3+)
            chunk2 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="weather forecast sunny warm rain",
                embedding_text="weather forecast sunny warm rain temperature",
            )
            chunk3 = _make_mock_chunk(
                user_id=user_id,
                video_id=video_id,
                text="cooking recipes pasta sauce ingredients",
                embedding_text="cooking recipes pasta sauce ingredients garlic",
            )

            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [chunk1, chunk2, chunk3]
            mock_db.query.return_value = mock_query

            result = service.search(
                db=mock_db,
                query="kubernetes deployment scaling strategy",
                user_id=user_id,
                video_ids=[video_id],
            )

            # Only "kubernetes" matches — need 3 content terms, so filtered
            assert len(result) == 0

    def test_bm25_not_installed(self):
        service = BM25SearchService()
        service._bm25_available = None

        with patch.dict("sys.modules", {"rank_bm25": None}):
            with patch("app.services.bm25_search.settings") as mock_settings:
                mock_settings.enable_bm25_search = True
                service._bm25_available = False  # Simulate failed import
                result = service.search(
                    db=MagicMock(), query="test", user_id=uuid4(), video_ids=[uuid4()]
                )
                assert result == []


# ---------------------------------------------------------------------------
# rrf_fuse tests
# ---------------------------------------------------------------------------


class TestRRFFuse:
    def test_empty_inputs(self):
        result = rrf_fuse(vector_chunks=[], bm25_results=[])
        assert result == []

    def test_vector_only_passthrough(self):
        chunks = [_make_scored_chunk(score=0.9), _make_scored_chunk(score=0.7)]
        result = rrf_fuse(vector_chunks=chunks, bm25_results=[])
        assert len(result) == 2
        assert result[0].score == 0.9
        assert result[1].score == 0.7

    def test_bm25_only_capped_at_max(self):
        """BM25-only chunks are capped at max_bm25_unique (S2)."""
        bm25_results = [_make_bm25_result() for _ in range(5)]
        result = rrf_fuse(
            vector_chunks=[], bm25_results=bm25_results, max_bm25_unique=3
        )
        assert len(result) == 3

    def test_bm25_only_get_default_score(self):
        """BM25-only chunks get score=0.45 (S8)."""
        bm25_results = [_make_bm25_result()]

        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.bm25_default_score = 0.45
            result = rrf_fuse(vector_chunks=[], bm25_results=bm25_results, max_bm25_unique=3)

        assert len(result) == 1
        assert result[0].score == 0.45

    def test_overlapping_chunks_boosted(self):
        """Chunks in both vector and BM25 results get higher RRF rank."""
        shared_id = uuid4()
        video_id = uuid4()

        vector_chunks = [
            _make_scored_chunk(chunk_id=shared_id, video_id=video_id, score=0.7),
            _make_scored_chunk(score=0.9),  # Higher score but not in BM25
        ]
        bm25_results = [
            _make_bm25_result(chunk_id=shared_id, video_id=video_id),
        ]

        result = rrf_fuse(
            vector_chunks=vector_chunks,
            bm25_results=bm25_results,
            k=60,
            vector_weight=1.0,
            bm25_weight=0.3,
        )

        # The shared chunk should be first (boosted by both signals)
        assert result[0].chunk_id == shared_id

    def test_preserves_vector_scores(self):
        """Vector chunks keep their original cosine scores."""
        chunk = _make_scored_chunk(score=0.85)
        bm25_result = _make_bm25_result()

        result = rrf_fuse(
            vector_chunks=[chunk],
            bm25_results=[bm25_result],
            max_bm25_unique=3,
        )

        # Find the vector chunk in results
        vector_in_result = [c for c in result if c.chunk_id == chunk.chunk_id]
        assert len(vector_in_result) == 1
        assert vector_in_result[0].score == 0.85

    def test_bm25_only_below_primary_threshold(self):
        """BM25-only chunks have score below 0.50 primary threshold (S8)."""
        bm25_result = _make_bm25_result()

        with patch("app.services.bm25_search.settings") as mock_settings:
            mock_settings.bm25_default_score = 0.45
            result = rrf_fuse(
                vector_chunks=[], bm25_results=[bm25_result], max_bm25_unique=3
            )

        assert result[0].score < 0.50


# ---------------------------------------------------------------------------
# Reranker score propagation tests (S4)
# ---------------------------------------------------------------------------


class TestRerankerScorePropagation:
    def test_scores_updated_after_reranking(self):
        """Reranker should update chunk.score with normalized cross-encoder score."""
        from app.services.reranker import RerankerService

        service = RerankerService()

        # Create chunks with original cosine scores
        chunks = [
            _make_scored_chunk(score=0.3),  # Low cosine but should score high in CE
            _make_scored_chunk(score=0.9),  # High cosine but should score low in CE
        ]

        # Mock the cross-encoder to reverse the ranking
        mock_model = MagicMock()
        mock_model.predict.return_value = [8.5, 2.0]
        service._model = mock_model
        service._load_error = None

        with patch("app.services.reranker.settings") as mock_settings:
            mock_settings.enable_reranking = True
            result = service.rerank(query="test query", chunks=chunks, top_k=2)

        # First chunk in result should be the one with CE score 8.5
        assert len(result) == 2
        # Score should be normalized 0-1 (8.5 -> 1.0, 2.0 -> 0.0)
        assert result[0].score == pytest.approx(1.0)
        assert result[1].score == pytest.approx(0.0)

    def test_scores_normalized_to_unit_range(self):
        """Normalized scores should be in [0.0, 1.0] range."""
        from app.services.reranker import RerankerService

        service = RerankerService()

        chunks = [
            _make_scored_chunk(score=0.5),
            _make_scored_chunk(score=0.6),
            _make_scored_chunk(score=0.7),
        ]

        mock_model = MagicMock()
        mock_model.predict.return_value = [3.0, 7.0, 5.0]
        service._model = mock_model
        service._load_error = None

        with patch("app.services.reranker.settings") as mock_settings:
            mock_settings.enable_reranking = True
            result = service.rerank(query="test", chunks=chunks)

        # All scores should be between 0 and 1
        for chunk in result:
            assert 0.0 <= chunk.score <= 1.0

        # 7.0 -> 1.0, 5.0 -> 0.5, 3.0 -> 0.0
        assert result[0].score == pytest.approx(1.0)
        assert result[1].score == pytest.approx(0.5)
        assert result[2].score == pytest.approx(0.0)

    def test_single_chunk_gets_score_zero(self):
        """Single chunk gets score 0.0 since min_ce == max_ce (no range)."""
        from app.services.reranker import RerankerService

        service = RerankerService()

        chunks = [_make_scored_chunk(score=0.5)]

        mock_model = MagicMock()
        mock_model.predict.return_value = [4.2]
        service._model = mock_model
        service._load_error = None

        with patch("app.services.reranker.settings") as mock_settings:
            mock_settings.enable_reranking = True
            result = service.rerank(query="test", chunks=chunks)

        assert len(result) == 1
        assert result[0].score == pytest.approx(0.0)

    def test_equal_ce_scores_all_zero(self):
        """When all CE scores are equal, all get score 0.0."""
        from app.services.reranker import RerankerService

        service = RerankerService()

        chunks = [
            _make_scored_chunk(score=0.5),
            _make_scored_chunk(score=0.6),
        ]

        mock_model = MagicMock()
        mock_model.predict.return_value = [5.0, 5.0]
        service._model = mock_model
        service._load_error = None

        with patch("app.services.reranker.settings") as mock_settings:
            mock_settings.enable_reranking = True
            result = service.rerank(query="test", chunks=chunks)

        # All same CE scores -> (5-5)/1.0 = 0.0
        for chunk in result:
            assert chunk.score == pytest.approx(0.0)
