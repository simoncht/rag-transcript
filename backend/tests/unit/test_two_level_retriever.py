"""
Unit tests for the TwoLevelRetriever.

Tests intent routing, pipeline stage toggling, diversity/chunk limits,
deduplication, context building, and config from settings.
"""
import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.two_level_retriever import (
    RetrievalConfig,
    RetrievalResult,
    TwoLevelRetriever,
    VideoSummary,
)
from app.services.intent_classifier import IntentClassification, QueryIntent
from app.services.vector_store import ScoredChunk


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_scored_chunk(
    video_id=None,
    chunk_id=None,
    score=0.85,
    text="Test chunk text",
    start_timestamp=10.0,
    end_timestamp=40.0,
    speakers=None,
    chapter_title=None,
    title=None,
    chunk_index=0,
    content_type="youtube",
    page_number=None,
) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        video_id=video_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        text=text,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        score=score,
        chunk_index=chunk_index,
        content_type=content_type,
        page_number=page_number,
        title=title or "Chunk Title",
        speakers=speakers or ["Speaker A"],
        chapter_title=chapter_title,
    )


def _make_intent(intent: QueryIntent, confidence: float = 0.9) -> IntentClassification:
    return IntentClassification(
        intent=intent,
        confidence=confidence,
        reasoning="test",
    )


def _make_video(video_id=None, summary=None, key_topics=None, content_type="youtube"):
    video = MagicMock()
    video.id = video_id or uuid.uuid4()
    video.title = "Test Video"
    video.channel_name = "Test Channel"
    video.summary = summary
    video.key_topics = key_topics or []
    video.duration_seconds = 600
    video.created_at = None
    video.youtube_id = "abc123"
    video.youtube_url = "https://youtu.be/abc123"
    video.content_type = content_type
    video.page_count = None
    video.source_url = None
    return video


@pytest.fixture
def retriever():
    return TwoLevelRetriever()


@pytest.fixture
def config():
    return RetrievalConfig(
        enable_query_expansion=False,
        enable_bm25=False,
        enable_hyde=False,
        enable_reranking=False,
        enable_relevance_grading=False,
    )


# ── RetrievalConfig Tests ────────────────────────────────────────────────


class TestRetrievalConfig:
    def test_defaults(self):
        cfg = RetrievalConfig()
        assert cfg.enable_query_expansion is True
        assert cfg.enable_bm25 is True
        assert cfg.enable_hyde is False
        assert cfg.enable_reranking is True
        assert cfg.enable_relevance_grading is False
        assert cfg.retrieval_top_k == 20
        assert cfg.min_relevance_score == 0.50

    @patch("app.services.two_level_retriever.settings")
    def test_from_settings(self, mock_settings):
        mock_settings.enable_query_expansion = True
        mock_settings.enable_bm25_search = False
        mock_settings.enable_hyde = True
        mock_settings.enable_reranking = False
        mock_settings.enable_relevance_grading = True
        mock_settings.retrieval_top_k = 15
        mock_settings.reranking_top_k = 5
        mock_settings.min_relevance_score = 0.6
        mock_settings.fallback_relevance_score = 0.2
        mock_settings.weak_context_threshold = 0.45
        mock_settings.bm25_top_k = 25
        mock_settings.bm25_max_unique_chunks = 4
        mock_settings.rrf_k = 55
        mock_settings.rrf_vector_weight = 0.9
        mock_settings.rrf_bm25_weight = 0.4

        cfg = RetrievalConfig.from_settings()
        assert cfg.enable_query_expansion is True
        assert cfg.enable_bm25 is False
        assert cfg.enable_hyde is True
        assert cfg.retrieval_top_k == 15
        assert cfg.min_relevance_score == 0.6


# ── Diversity & Chunk Limit Tests ────────────────────────────────────────


class TestDiversityAndChunkLimits:
    def test_diversity_default_mode(self, retriever):
        assert retriever._get_diversity_factor(1, "unknown_mode") == 0.4

    def test_diversity_summarize(self, retriever):
        assert retriever._get_diversity_factor(1, "summarize") == 0.5

    def test_diversity_scales_with_videos(self, retriever):
        d3 = retriever._get_diversity_factor(3, "deep_dive")
        d5 = retriever._get_diversity_factor(5, "deep_dive")
        assert d5 > d3

    def test_diversity_capped(self, retriever):
        d = retriever._get_diversity_factor(100, "compare_sources")
        assert d <= 0.7

    def test_chunk_limit_default(self, retriever):
        assert retriever._get_chunk_limit(1, "unknown_mode") == 4

    def test_chunk_limit_summarize(self, retriever):
        assert retriever._get_chunk_limit(1, "summarize") == 6

    def test_chunk_limit_scales(self, retriever):
        l3 = retriever._get_chunk_limit(3, "deep_dive")
        l5 = retriever._get_chunk_limit(5, "deep_dive")
        assert l5 > l3

    def test_chunk_limit_capped(self, retriever):
        lim = retriever._get_chunk_limit(100, "summarize")
        assert lim <= 12

    def test_coverage_chunk_limit_scales_to_video_count(self, retriever):
        """COVERAGE queries should get 1 chunk per video (up to max)."""
        lim = retriever._get_chunk_limit(40, "summarize", is_coverage=True)
        assert lim == 40

    def test_coverage_chunk_limit_capped_at_50(self, retriever):
        """COVERAGE chunk limit should cap at MAX_COVERAGE_CHUNK_LIMIT."""
        lim = retriever._get_chunk_limit(100, "summarize", is_coverage=True)
        assert lim == 50

    def test_coverage_chunk_limit_small_collection(self, retriever):
        """COVERAGE with few videos should use floor of 10."""
        lim = retriever._get_chunk_limit(5, "summarize", is_coverage=True)
        assert lim == 10

    def test_precision_chunk_limit_unchanged(self, retriever):
        """PRECISION queries should still use original capped behavior."""
        lim = retriever._get_chunk_limit(40, "summarize", is_coverage=False)
        assert lim <= 12


# ── Deduplication Tests ──────────────────────────────────────────────────


class TestDeduplication:
    def test_dedup_by_timestamp_bucket(self, retriever):
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(video_id=vid, start_timestamp=10.0, score=0.9),
            _make_scored_chunk(video_id=vid, start_timestamp=15.0, score=0.8),  # same bucket
            _make_scored_chunk(video_id=vid, start_timestamp=45.0, score=0.7),  # different bucket
        ]
        deduped = retriever._deduplicate_chunks(chunks, by_video_only=False, bucket_seconds=30)
        assert len(deduped) == 2

    def test_dedup_by_video_only(self, retriever):
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(video_id=vid, start_timestamp=10.0, score=0.9),
            _make_scored_chunk(video_id=vid, start_timestamp=45.0, score=0.8),
        ]
        deduped = retriever._deduplicate_chunks(chunks, by_video_only=True)
        assert len(deduped) == 1

    def test_dedup_different_videos(self, retriever):
        chunks = [
            _make_scored_chunk(start_timestamp=10.0, score=0.9),
            _make_scored_chunk(start_timestamp=10.0, score=0.8),
        ]
        deduped = retriever._deduplicate_chunks(chunks, by_video_only=False)
        assert len(deduped) == 2  # different video IDs

    def test_dedup_document_by_page(self, retriever):
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(video_id=vid, content_type="pdf", page_number=1, score=0.9),
            _make_scored_chunk(video_id=vid, content_type="pdf", page_number=1, score=0.8),
            _make_scored_chunk(video_id=vid, content_type="pdf", page_number=2, score=0.7),
        ]
        deduped = retriever._deduplicate_chunks(chunks, by_video_only=False)
        assert len(deduped) == 2


# ── Intent Routing Tests ─────────────────────────────────────────────────


class TestIntentRouting:
    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_precision_routes_to_chunks(self, mock_settings, mock_vs, retriever, config):
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        chunks = [_make_scored_chunk(score=0.9)]
        vid = chunks[0].video_id

        # Mock embedding_service via lazy import
        with patch("app.services.two_level_retriever.embedding_service", create=True):
            from app.services import embeddings
            mock_embed_service = MagicMock()
            mock_embed_service.embed_text.return_value = np.zeros(384)

            with patch.object(embeddings, "embedding_service", mock_embed_service):
                mock_vs.search_with_diversity.return_value = chunks

                video = _make_video(video_id=vid)
                db.query.return_value.filter.return_value.all.return_value = [video]

                result = retriever.retrieve(
                    db=db,
                    query="What did the speaker say about AI?",
                    video_ids=[vid],
                    user_id=uuid.uuid4(),
                    mode="deep_dive",
                    intent=_make_intent(QueryIntent.PRECISION),
                    config=config,
                )

                assert result.retrieval_type == "chunks"
                assert len(result.chunks) > 0
                assert result.video_map is not None

    def test_coverage_routes_to_summaries(self, retriever, config):
        db = MagicMock()
        vid = uuid.uuid4()

        video = _make_video(video_id=vid, summary="This is a summary", key_topics=["AI", "ML"])

        # Mock the summary count query
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 1  # 100% coverage
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [video]

        db.query.return_value = mock_query

        result = retriever.retrieve(
            db=db,
            query="Summarize everything",
            video_ids=[vid],
            user_id=uuid.uuid4(),
            mode="summarize",
            intent=_make_intent(QueryIntent.COVERAGE),
            config=config,
        )

        assert result.retrieval_type == "summaries"
        assert len(result.video_summaries) == 1
        assert result.video_summaries[0].title == "Test Video"
        assert "This is a summary" in result.context


# ── Context Building Tests ───────────────────────────────────────────────


class TestContextBuilding:
    def test_chunk_context_includes_metadata(self, retriever):
        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(
                video_id=vid,
                text="Important AI insight",
                speakers=["Dr. Smith"],
                chapter_title="AI Chapter",
                start_timestamp=120.0,
                end_timestamp=150.0,
                score=0.92,
            )
        ]

        video = _make_video(video_id=vid)
        db.query.return_value.filter.return_value.all.return_value = [video]

        context, video_map = retriever._build_chunk_context(db, chunks)

        assert "[Source 1]" in context
        assert "Dr. Smith" in context
        assert "AI Chapter" in context
        assert "92%" in context
        assert vid in video_map

    def test_empty_chunks_returns_no_content(self, retriever):
        db = MagicMock()
        context, video_map = retriever._build_chunk_context(db, [])
        assert "No relevant content" in context
        assert video_map == {}

    def test_document_context_format(self, retriever):
        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(
                video_id=vid,
                content_type="pdf",
                page_number=5,
                text="Document content",
                score=0.85,
            )
        ]
        video = _make_video(video_id=vid, content_type="pdf")
        db.query.return_value.filter.return_value.all.return_value = [video]

        context, _ = retriever._build_chunk_context(db, chunks)
        assert "Section:" in context
        assert "Location:" in context


# ── Timestamp Formatting Tests ───────────────────────────────────────────


class TestTimestampFormatting:
    def test_short_timestamp(self):
        ts = TwoLevelRetriever._format_timestamp(65.0, 125.0)
        assert ts == "01:05 - 02:05"

    def test_long_timestamp(self):
        ts = TwoLevelRetriever._format_timestamp(3665.0, 7325.0)
        assert ts == "01:01:05 - 02:02:05"


# ── Pipeline Stage Toggle Tests ──────────────────────────────────────────


class TestPipelineStageToggles:
    def test_query_expansion_disabled(self, retriever):
        config = RetrievalConfig(enable_query_expansion=False)
        variants = retriever._run_query_expansion("test query", config)
        assert variants == ["test query"]

    @patch("app.services.query_expansion.get_query_expansion_service")
    def test_query_expansion_enabled(self, mock_get_svc, retriever):
        config = RetrievalConfig(enable_query_expansion=True)
        mock_svc = MagicMock()
        mock_svc.expand_query.return_value = ["variant 1", "variant 2", "variant 3"]
        mock_get_svc.return_value = mock_svc

        variants = retriever._run_query_expansion("test query", config)
        assert len(variants) == 3
        mock_svc.expand_query.assert_called_once_with("test query")

    def test_bm25_skips_short_query(self, retriever):
        config = RetrievalConfig(enable_bm25=True)
        chunks = [_make_scored_chunk(score=0.9)]
        db = MagicMock()

        with patch("app.services.bm25_search._should_skip_bm25", return_value=True):
            result = retriever._run_bm25_fusion(
                db, "hi", chunks, uuid.uuid4(), [uuid.uuid4()], config,
            )
            assert result == chunks  # Unchanged


# ── Location Display Tests ───────────────────────────────────────────────


class TestLocationDisplay:
    def test_video_location(self):
        chunk = _make_scored_chunk(start_timestamp=65.0, end_timestamp=125.0)
        display = TwoLevelRetriever._format_location_display(chunk)
        assert "01:05" in display

    def test_document_page_location(self):
        chunk = _make_scored_chunk(content_type="pdf", page_number=3)
        display = TwoLevelRetriever._format_location_display(chunk)
        assert display == "Page 3"

    def test_document_no_page(self):
        chunk = _make_scored_chunk(content_type="pdf", page_number=None)
        display = TwoLevelRetriever._format_location_display(chunk)
        assert display == "Document"


# ── Coverage Fallback Pipeline Tests ─────────────────────────────────


class TestCoverageFallbackPipeline:
    """Tests the is_coverage_fallback=True code path, verifying each
    pipeline stage is correctly skipped or modified."""

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_coverage_fallback_skips_query_expansion(
        self, mock_settings, mock_vs, retriever, config
    ):
        """Verify _run_query_expansion NOT called for coverage fallback."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [_make_scored_chunk(video_id=vid, score=0.9)]

        with patch.object(retriever, "_run_query_expansion") as mock_expand:
            with patch("app.services.two_level_retriever.embedding_service", create=True):
                from app.services import embeddings
                mock_embed_svc = MagicMock()
                mock_embed_svc.embed_text.return_value = np.zeros(384)
                mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
                mock_embed_svc._get_query_text.return_value = "test"

                with patch.object(embeddings, "embedding_service", mock_embed_svc):
                    mock_vs.search_with_video_guarantee.return_value = chunks
                    mock_vs.search_with_diversity.return_value = chunks

                    video = _make_video(video_id=vid)
                    db.query.return_value.filter.return_value.all.return_value = [video]

                    config.enable_query_expansion = True
                    result = retriever._retrieve_chunks(
                        db=db,
                        query="summarize all videos",
                        video_ids=[vid],
                        user_id=uuid.uuid4(),
                        num_videos=1,
                        mode="summarize",
                        config=config,
                        use_video_guarantee=True,
                        is_coverage_fallback=True,
                    )

                    mock_expand.assert_not_called()

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_coverage_fallback_skips_reranking(
        self, mock_settings, mock_vs, retriever, config
    ):
        """Verify _run_reranking NOT called for coverage fallback."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [_make_scored_chunk(video_id=vid, score=0.9)]

        with patch.object(retriever, "_run_reranking") as mock_rerank:
            with patch("app.services.two_level_retriever.embedding_service", create=True):
                from app.services import embeddings
                mock_embed_svc = MagicMock()
                mock_embed_svc.embed_text.return_value = np.zeros(384)
                mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
                mock_embed_svc._get_query_text.return_value = "test"

                with patch.object(embeddings, "embedding_service", mock_embed_svc):
                    mock_vs.search_with_video_guarantee.return_value = chunks
                    mock_vs.search_with_diversity.return_value = chunks

                    video = _make_video(video_id=vid)
                    db.query.return_value.filter.return_value.all.return_value = [video]

                    config.enable_reranking = True
                    result = retriever._retrieve_chunks(
                        db=db,
                        query="summarize all",
                        video_ids=[vid],
                        user_id=uuid.uuid4(),
                        num_videos=1,
                        mode="summarize",
                        config=config,
                        use_video_guarantee=True,
                        is_coverage_fallback=True,
                    )

                    mock_rerank.assert_not_called()

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_coverage_fallback_skips_relevance_grading(
        self, mock_settings, mock_vs, retriever, config
    ):
        """Verify _run_relevance_grading NOT called for coverage fallback."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [_make_scored_chunk(video_id=vid, score=0.9)]

        with patch.object(retriever, "_run_relevance_grading") as mock_grade:
            with patch("app.services.two_level_retriever.embedding_service", create=True):
                from app.services import embeddings
                mock_embed_svc = MagicMock()
                mock_embed_svc.embed_text.return_value = np.zeros(384)
                mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
                mock_embed_svc._get_query_text.return_value = "test"

                with patch.object(embeddings, "embedding_service", mock_embed_svc):
                    mock_vs.search_with_video_guarantee.return_value = chunks
                    mock_vs.search_with_diversity.return_value = chunks

                    video = _make_video(video_id=vid)
                    db.query.return_value.filter.return_value.all.return_value = [video]

                    config.enable_relevance_grading = True
                    result = retriever._retrieve_chunks(
                        db=db,
                        query="summarize all",
                        video_ids=[vid],
                        user_id=uuid.uuid4(),
                        num_videos=1,
                        mode="summarize",
                        config=config,
                        use_video_guarantee=True,
                        is_coverage_fallback=True,
                    )

                    mock_grade.assert_not_called()

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_coverage_fallback_skips_threshold_filter(
        self, mock_settings, mock_vs, retriever, config
    ):
        """All chunks kept (no min_relevance_score filter) for coverage fallback."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        # Low score chunk that would normally be filtered
        chunks = [
            _make_scored_chunk(video_id=vid1, score=0.1),
            _make_scored_chunk(video_id=vid2, score=0.05),
        ]

        with patch("app.services.two_level_retriever.embedding_service", create=True):
            from app.services import embeddings
            mock_embed_svc = MagicMock()
            mock_embed_svc.embed_text.return_value = np.zeros(384)
            mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
            mock_embed_svc._get_query_text.return_value = "test"

            with patch.object(embeddings, "embedding_service", mock_embed_svc):
                mock_vs.search_with_video_guarantee.return_value = chunks
                mock_vs.search_with_diversity.return_value = chunks

                video1 = _make_video(video_id=vid1)
                video2 = _make_video(video_id=vid2)
                db.query.return_value.filter.return_value.all.return_value = [video1, video2]

                config.min_relevance_score = 0.5
                result = retriever._retrieve_chunks(
                    db=db,
                    query="summarize all",
                    video_ids=[vid1, vid2],
                    user_id=uuid.uuid4(),
                    num_videos=2,
                    mode="summarize",
                    config=config,
                    use_video_guarantee=True,
                    is_coverage_fallback=True,
                )

                # Both low-score chunks should be kept (no threshold filtering)
                assert len(result.chunks) == 2

    def test_coverage_fallback_deduplicates_by_video(self, retriever):
        """by_video_only=True used for dedup: same video -> only 1 chunk."""
        vid = uuid.uuid4()
        chunks = [
            _make_scored_chunk(video_id=vid, start_timestamp=10.0, score=0.9),
            _make_scored_chunk(video_id=vid, start_timestamp=45.0, score=0.8),
        ]
        deduped = retriever._deduplicate_chunks(chunks, by_video_only=True)
        assert len(deduped) == 1

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_precision_still_runs_reranking(
        self, mock_settings, mock_vs, retriever, config
    ):
        """PRECISION queries should still run reranking normally."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [_make_scored_chunk(video_id=vid, score=0.9)]

        with patch.object(retriever, "_run_reranking", return_value=chunks) as mock_rerank:
            with patch("app.services.two_level_retriever.embedding_service", create=True):
                from app.services import embeddings
                mock_embed_svc = MagicMock()
                mock_embed_svc.embed_text.return_value = np.zeros(384)
                mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
                mock_embed_svc._get_query_text.return_value = "test"

                with patch.object(embeddings, "embedding_service", mock_embed_svc):
                    mock_vs.search_with_diversity.return_value = chunks

                    video = _make_video(video_id=vid)
                    db.query.return_value.filter.return_value.all.return_value = [video]

                    config.enable_reranking = True
                    result = retriever._retrieve_chunks(
                        db=db,
                        query="what did they say about AI?",
                        video_ids=[vid],
                        user_id=uuid.uuid4(),
                        num_videos=1,
                        mode="deep_dive",
                        config=config,
                        use_video_guarantee=False,
                        is_coverage_fallback=False,
                    )

                    mock_rerank.assert_called_once()

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_precision_still_runs_expansion(
        self, mock_settings, mock_vs, retriever, config
    ):
        """PRECISION queries should still expand normally."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        vid = uuid.uuid4()
        chunks = [_make_scored_chunk(video_id=vid, score=0.9)]

        with patch.object(
            retriever, "_run_query_expansion", return_value=["query"]
        ) as mock_expand:
            with patch("app.services.two_level_retriever.embedding_service", create=True):
                from app.services import embeddings
                mock_embed_svc = MagicMock()
                mock_embed_svc.embed_text.return_value = np.zeros(384)
                mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
                mock_embed_svc._get_query_text.return_value = "test"

                with patch.object(embeddings, "embedding_service", mock_embed_svc):
                    mock_vs.search_with_diversity.return_value = chunks

                    video = _make_video(video_id=vid)
                    db.query.return_value.filter.return_value.all.return_value = [video]

                    config.enable_query_expansion = True
                    result = retriever._retrieve_chunks(
                        db=db,
                        query="what did they say about AI?",
                        video_ids=[vid],
                        user_id=uuid.uuid4(),
                        num_videos=1,
                        mode="deep_dive",
                        config=config,
                        use_video_guarantee=False,
                        is_coverage_fallback=False,
                    )

                    mock_expand.assert_called_once()


# ── Chunk Limit Edge Cases ──────────────────────────────────────────


class TestChunkLimitEdgeCases:
    """Tests boundary behavior of _get_chunk_limit."""

    def test_coverage_limit_exactly_50_videos(self, retriever):
        """50 videos, coverage -> returns 50."""
        lim = retriever._get_chunk_limit(50, "summarize", is_coverage=True)
        assert lim == 50

    def test_coverage_limit_51_videos_capped(self, retriever):
        """51 videos, coverage -> returns 50 (capped at MAX_COVERAGE_CHUNK_LIMIT)."""
        lim = retriever._get_chunk_limit(51, "summarize", is_coverage=True)
        assert lim == 50

    def test_coverage_chunk_limit_single_doc_returns_10(self, retriever):
        """1 video, coverage -> returns 10 (floor of 10, not 1)."""
        lim = retriever._get_chunk_limit(1, "summarize", is_coverage=True)
        assert lim == 10

    def test_coverage_chunk_limit_5_videos_returns_10(self, retriever):
        """5 videos, coverage -> returns 10 (floor of 10)."""
        lim = retriever._get_chunk_limit(5, "summarize", is_coverage=True)
        assert lim == 10

    def test_coverage_chunk_limit_many_docs_scales(self, retriever):
        """25 videos, coverage -> returns 25 (above floor)."""
        lim = retriever._get_chunk_limit(25, "summarize", is_coverage=True)
        assert lim == 25

    def test_coverage_limit_0_videos(self, retriever):
        """0 videos, coverage -> returns 10 (floor)."""
        lim = retriever._get_chunk_limit(0, "summarize", is_coverage=True)
        assert lim == 10

    def test_precision_limit_unchanged_for_40_videos(self, retriever):
        """40 videos, precision -> still uses MAX_CHUNK_LIMIT cap."""
        lim = retriever._get_chunk_limit(40, "summarize", is_coverage=False)
        assert lim <= 12  # MAX_CHUNK_LIMIT


# ── Prefetch Scaling Tests ──────────────────────────────────────────


class TestPrefetchScaling:
    """Tests the dynamic prefetch limit for coverage queries."""

    @patch("app.services.two_level_retriever.vector_store_service")
    def test_coverage_prefetch_scales_with_videos(self, mock_vs, retriever, config):
        """40 videos, coverage query -> prefetch_limit >= 120 (40*3)."""
        with patch("app.services.two_level_retriever.embedding_service", create=True):
            from app.services import embeddings
            mock_embed_svc = MagicMock()
            mock_embed_svc.embed_text.return_value = np.zeros(384)
            mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
            mock_embed_svc._get_query_text.return_value = "test"

            with patch.object(embeddings, "embedding_service", mock_embed_svc):
                mock_vs.search_with_video_guarantee.return_value = []
                mock_vs.search_with_diversity.return_value = []

                video_ids = [uuid.uuid4() for _ in range(40)]
                retriever._run_multi_query_search(
                    query_variants=["summarize all"],
                    user_id=uuid.uuid4(),
                    video_ids=video_ids,
                    num_videos=40,
                    diversity=0.5,
                    chunk_limit=40,
                    config=config,
                    use_video_guarantee=True,
                    is_coverage_query=True,
                )

                # Check prefetch_limit passed to search_with_video_guarantee
                call_args = mock_vs.search_with_video_guarantee.call_args
                assert call_args.kwargs.get("prefetch_limit", call_args[1].get("prefetch_limit", 0)) >= 120

    @patch("app.services.two_level_retriever.vector_store_service")
    def test_precision_prefetch_uses_default(self, mock_vs, retriever, config):
        """40 videos, precision query -> uses MMR_PREFETCH_LIMIT (100)."""
        with patch("app.services.two_level_retriever.embedding_service", create=True):
            from app.services import embeddings
            mock_embed_svc = MagicMock()
            mock_embed_svc.embed_text.return_value = np.zeros(384)
            mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
            mock_embed_svc._get_query_text.return_value = "test"

            with patch.object(embeddings, "embedding_service", mock_embed_svc):
                mock_vs.search_with_diversity.return_value = []

                video_ids = [uuid.uuid4() for _ in range(40)]
                retriever._run_multi_query_search(
                    query_variants=["what did they say?"],
                    user_id=uuid.uuid4(),
                    video_ids=video_ids,
                    num_videos=40,
                    diversity=0.4,
                    chunk_limit=12,
                    config=config,
                    use_video_guarantee=False,
                    is_coverage_query=False,
                )

                call_args = mock_vs.search_with_diversity.call_args
                prefetch = call_args.kwargs.get("prefetch_limit", call_args[1].get("prefetch_limit", 0))
                assert prefetch == retriever.MMR_PREFETCH_LIMIT

    @patch("app.services.two_level_retriever.vector_store_service")
    def test_coverage_prefetch_minimum_is_mmr_default(self, mock_vs, retriever, config):
        """10 videos, coverage -> prefetch at least MMR_PREFETCH_LIMIT (max(100, 30))."""
        with patch("app.services.two_level_retriever.embedding_service", create=True):
            from app.services import embeddings
            mock_embed_svc = MagicMock()
            mock_embed_svc.embed_text.return_value = np.zeros(384)
            mock_embed_svc.embed_batch.return_value = [np.zeros(384)]
            mock_embed_svc._get_query_text.return_value = "test"

            with patch.object(embeddings, "embedding_service", mock_embed_svc):
                mock_vs.search_with_video_guarantee.return_value = []

                video_ids = [uuid.uuid4() for _ in range(10)]
                retriever._run_multi_query_search(
                    query_variants=["summarize all"],
                    user_id=uuid.uuid4(),
                    video_ids=video_ids,
                    num_videos=10,
                    diversity=0.5,
                    chunk_limit=10,
                    config=config,
                    use_video_guarantee=True,
                    is_coverage_query=True,
                )

                call_args = mock_vs.search_with_video_guarantee.call_args
                prefetch = call_args.kwargs.get("prefetch_limit", call_args[1].get("prefetch_limit", 0))
                assert prefetch >= retriever.MMR_PREFETCH_LIMIT


# ── Coverage-to-Summary Routing Tests ───────────────────────────────


class TestCoverageToSummaryRouting:
    """Tests the summary coverage threshold at the retrieve() top level."""

    def test_50pct_summaries_routes_to_summaries(self, retriever, config):
        """5/10 videos have summaries (50%) -> retrieval_type == 'summaries'."""
        db = MagicMock()
        video_ids = [uuid.uuid4() for _ in range(10)]

        # Mock: 5/10 have summaries
        mock_count_query = MagicMock()
        mock_count_query.filter.return_value.count.return_value = 5

        videos = [
            _make_video(video_id=vid, summary=f"Summary {i}", key_topics=["AI"])
            for i, vid in enumerate(video_ids[:5])
        ]
        mock_all_query = MagicMock()
        mock_all_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = videos

        # First call is count query (summary check), second is fetch query
        db.query.return_value = mock_count_query

        with patch.object(retriever, "_retrieve_coverage") as mock_coverage:
            mock_coverage.return_value = RetrievalResult(
                retrieval_type="summaries",
                video_summaries=[MagicMock()],
                context="summary context",
            )

            result = retriever.retrieve(
                db=db,
                query="summarize everything",
                video_ids=video_ids,
                user_id=uuid.uuid4(),
                mode="summarize",
                intent=_make_intent(QueryIntent.COVERAGE),
                config=config,
            )

            mock_coverage.assert_called_once()

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_49pct_summaries_falls_back_to_chunks(
        self, mock_settings, mock_vs, retriever, config
    ):
        """4/10 videos have summaries (40%) -> falls back to chunk retrieval."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        video_ids = [uuid.uuid4() for _ in range(10)]

        # Mock: 4/10 have summaries (40% < 50% threshold)
        mock_count_query = MagicMock()
        mock_count_query.filter.return_value.count.return_value = 4

        db.query.return_value = mock_count_query

        with patch.object(retriever, "_retrieve_chunks") as mock_chunks:
            mock_chunks.return_value = RetrievalResult(
                retrieval_type="chunks",
                chunks=[MagicMock()],
                context="chunk context",
            )

            result = retriever.retrieve(
                db=db,
                query="summarize everything",
                video_ids=video_ids,
                user_id=uuid.uuid4(),
                mode="summarize",
                intent=_make_intent(QueryIntent.COVERAGE),
                config=config,
            )

            mock_chunks.assert_called_once()
            # Verify is_coverage_fallback=True was passed
            call_kwargs = mock_chunks.call_args.kwargs
            assert call_kwargs.get("is_coverage_fallback") is True

    @patch("app.services.two_level_retriever.vector_store_service")
    @patch("app.services.two_level_retriever.settings")
    def test_0_summaries_falls_back_to_chunks(
        self, mock_settings, mock_vs, retriever, config
    ):
        """0 summaries -> falls back to chunk retrieval with is_coverage_fallback."""
        mock_settings.min_relevance_score = 0.5
        mock_settings.fallback_relevance_score = 0.15
        mock_settings.weak_context_threshold = 0.4
        mock_settings.retrieval_top_k = 10

        db = MagicMock()
        video_ids = [uuid.uuid4() for _ in range(10)]

        mock_count_query = MagicMock()
        mock_count_query.filter.return_value.count.return_value = 0

        db.query.return_value = mock_count_query

        with patch.object(retriever, "_retrieve_chunks") as mock_chunks:
            mock_chunks.return_value = RetrievalResult(
                retrieval_type="chunks",
                chunks=[],
                context="no content",
            )

            result = retriever.retrieve(
                db=db,
                query="summarize everything",
                video_ids=video_ids,
                user_id=uuid.uuid4(),
                mode="summarize",
                intent=_make_intent(QueryIntent.COVERAGE),
                config=config,
            )

            mock_chunks.assert_called_once()
            call_kwargs = mock_chunks.call_args.kwargs
            assert call_kwargs.get("is_coverage_fallback") is True


# ── Extended Intent Routing Tests ───────────────────────────────────


class TestDocumentSummaryInjection:
    """Tests for _maybe_prepend_document_summary."""

    def test_prepends_summary_when_available(self, retriever):
        """Should prepend document summary to context."""
        db = MagicMock()
        vid = uuid.uuid4()
        video = _make_video(video_id=vid, summary="This document covers AI topics.")
        video_map = {vid: video}

        result = retriever._maybe_prepend_document_summary(
            db, vid, "chunk context here", video_map,
        )
        assert "Document Overview" in result
        assert "This document covers AI topics." in result
        assert "chunk context here" in result

    def test_no_summary_returns_original_context(self, retriever):
        """Should return original context when no summary exists."""
        db = MagicMock()
        vid = uuid.uuid4()
        video = _make_video(video_id=vid, summary=None)
        video_map = {vid: video}

        result = retriever._maybe_prepend_document_summary(
            db, vid, "chunk context here", video_map,
        )
        assert result == "chunk context here"

    def test_fetches_from_db_when_not_in_map(self, retriever):
        """Should query DB if video not in video_map."""
        db = MagicMock()
        vid = uuid.uuid4()
        video = _make_video(video_id=vid, summary="DB summary")
        db.query.return_value.filter.return_value.first.return_value = video

        result = retriever._maybe_prepend_document_summary(
            db, vid, "chunk context", {},
        )
        assert "DB summary" in result


class TestExtendedIntentRouting:
    """Extended intent routing tests for HYBRID and edge cases."""

    def test_hybrid_routes_to_both_paths(self, retriever, config):
        """HYBRID intent calls _retrieve_hybrid, gets summaries + chunks."""
        db = MagicMock()
        vid = uuid.uuid4()

        with patch.object(retriever, "_retrieve_hybrid") as mock_hybrid:
            mock_hybrid.return_value = RetrievalResult(
                retrieval_type="hybrid",
                video_summaries=[MagicMock()],
                chunks=[MagicMock()],
                context="hybrid context",
            )

            result = retriever.retrieve(
                db=db,
                query="summarize with examples",
                video_ids=[vid],
                user_id=uuid.uuid4(),
                mode="summarize",
                intent=_make_intent(QueryIntent.HYBRID),
                config=config,
            )

            mock_hybrid.assert_called_once()
            assert result.retrieval_type == "hybrid"

    def test_zero_videos_coverage_no_division_error(self, retriever, config):
        """video_ids=[], COVERAGE intent -> no ZeroDivisionError."""
        db = MagicMock()

        # Mock the count query to return 0
        mock_count_query = MagicMock()
        mock_count_query.filter.return_value.count.return_value = 0
        db.query.return_value = mock_count_query

        with patch.object(retriever, "_retrieve_chunks") as mock_chunks:
            mock_chunks.return_value = RetrievalResult(
                retrieval_type="chunks",
                chunks=[],
                context="no content",
            )

            # Should not raise ZeroDivisionError
            result = retriever.retrieve(
                db=db,
                query="summarize everything",
                video_ids=[],
                user_id=uuid.uuid4(),
                mode="summarize",
                intent=_make_intent(QueryIntent.COVERAGE),
                config=config,
            )
