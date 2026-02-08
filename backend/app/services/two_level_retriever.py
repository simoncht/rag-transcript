"""
Two-level retriever for intent-based retrieval.

Routes retrieval based on classified intent:
- COVERAGE: Video summaries for overview queries
- PRECISION: Chunk retrieval for specific queries (full pipeline)
- HYBRID: Both summaries and targeted chunks

Full pipeline includes: query expansion, multi-query search, BM25 fusion,
HyDE, reranking, relevance grading, filtering, and deduplication.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Video
from app.services.intent_classifier import IntentClassification, QueryIntent
from app.services.vector_store import ScoredChunk, vector_store_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    """Configuration for the retrieval pipeline, read from settings."""

    enable_query_expansion: bool = True
    enable_bm25: bool = True
    enable_hyde: bool = False
    enable_reranking: bool = True
    enable_relevance_grading: bool = False
    retrieval_top_k: int = 20
    reranking_top_k: int = 7
    min_relevance_score: float = 0.50
    fallback_relevance_score: float = 0.15
    weak_context_threshold: float = 0.40
    # BM25 settings
    bm25_top_k: int = 20
    bm25_max_unique_chunks: int = 3
    rrf_k: int = 60
    rrf_vector_weight: float = 1.0
    rrf_bm25_weight: float = 0.3

    @classmethod
    def from_settings(cls) -> "RetrievalConfig":
        """Create config from application settings."""
        return cls(
            enable_query_expansion=settings.enable_query_expansion,
            enable_bm25=settings.enable_bm25_search,
            enable_hyde=settings.enable_hyde,
            enable_reranking=settings.enable_reranking,
            enable_relevance_grading=settings.enable_relevance_grading,
            retrieval_top_k=settings.retrieval_top_k,
            reranking_top_k=settings.reranking_top_k,
            min_relevance_score=settings.min_relevance_score,
            fallback_relevance_score=settings.fallback_relevance_score,
            weak_context_threshold=settings.weak_context_threshold,
            bm25_top_k=settings.bm25_top_k,
            bm25_max_unique_chunks=settings.bm25_max_unique_chunks,
            rrf_k=settings.rrf_k,
            rrf_vector_weight=settings.rrf_vector_weight,
            rrf_bm25_weight=settings.rrf_bm25_weight,
        )


@dataclass
class VideoSummary:
    """Video-level summary for coverage queries."""

    video_id: UUID
    title: str
    channel_name: Optional[str]
    summary: str
    key_topics: list[str] = field(default_factory=list)
    duration_seconds: Optional[int] = None
    content_type: str = "youtube"
    page_count: Optional[int] = None


@dataclass
class RetrievalResult:
    """Result of two-level retrieval."""

    chunks: list[ScoredChunk] = field(default_factory=list)
    video_summaries: list[VideoSummary] = field(default_factory=list)
    retrieval_type: str = "chunks"  # "chunks" | "summaries" | "hybrid"
    context: str = ""  # Pre-built context string for LLM
    context_is_weak: bool = False
    video_map: dict[UUID, Any] = field(default_factory=dict)
    videos_missing_summaries: int = 0
    retrieval_stats: dict[str, Any] = field(default_factory=dict)


class TwoLevelRetriever:
    """
    Two-level retrieval system with full RAG pipeline.

    Routes to appropriate retrieval strategy based on intent:
    - COVERAGE: Get video summaries from database
    - PRECISION: Full pipeline (expansion → search → BM25 → HyDE → rerank → grade → filter → dedup)
    - HYBRID: Summaries + targeted chunks

    For COVERAGE with <50% summary coverage, falls back to chunk retrieval
    with video-guarantee search.
    """

    # Chunk limits by mode
    BASE_CHUNK_LIMITS = {
        "summarize": 6,
        "compare_sources": 8,
        "deep_dive": 4,
        "timeline": 6,
        "extract_actions": 5,
        "quiz_me": 6,
    }

    # Diversity factors by mode
    MODE_DIVERSITY = {
        "summarize": 0.5,
        "compare_sources": 0.6,
        "deep_dive": 0.3,
        "timeline": 0.5,
        "extract_actions": 0.4,
        "quiz_me": 0.5,
    }

    DEFAULT_DIVERSITY = 0.4
    MAX_DIVERSITY = 0.7
    DEFAULT_CHUNK_LIMIT = 4
    MAX_CHUNK_LIMIT = 12
    MMR_PREFETCH_LIMIT = 100

    def retrieve(
        self,
        db: Session,
        query: str,
        video_ids: list[UUID],
        user_id: UUID,
        mode: str,
        intent: IntentClassification,
        config: Optional[RetrievalConfig] = None,
    ) -> RetrievalResult:
        """
        Retrieve based on intent classification with full RAG pipeline.

        Args:
            db: Database session
            query: User's query text (should be the effective/rewritten query)
            video_ids: List of selected video IDs
            user_id: User ID for filtering
            mode: Conversation mode for formatting
            intent: Classified intent (COVERAGE, PRECISION, HYBRID)
            config: Optional retrieval config (defaults to settings)

        Returns:
            RetrievalResult with chunks, summaries, context, and video_map
        """
        if config is None:
            config = RetrievalConfig.from_settings()

        num_videos = len(video_ids)

        logger.info(
            f"[Two-Level Retrieval] Intent={intent.intent.value} "
            f"(confidence={intent.confidence:.2f}), videos={num_videos}, mode={mode}"
        )

        # Check summary coverage for COVERAGE queries
        if intent.intent == QueryIntent.COVERAGE:
            videos_with_summaries = (
                db.query(Video)
                .filter(Video.id.in_(video_ids), Video.summary.isnot(None))
                .count()
            )
            summary_coverage = videos_with_summaries / num_videos if num_videos > 0 else 0

            if summary_coverage >= 0.5:
                return self._retrieve_coverage(db, video_ids, num_videos, mode)
            else:
                logger.info(
                    f"[Two-Level Retrieval] Coverage query but only {summary_coverage:.0%} "
                    f"summary coverage — falling back to chunk retrieval with video guarantee"
                )
                return self._retrieve_chunks(
                    db, query, video_ids, user_id, num_videos, mode, config,
                    use_video_guarantee=True, is_coverage_fallback=True,
                )

        elif intent.intent == QueryIntent.PRECISION:
            return self._retrieve_chunks(
                db, query, video_ids, user_id, num_videos, mode, config,
                use_video_guarantee=False, is_coverage_fallback=False,
            )

        else:  # HYBRID
            return self._retrieve_hybrid(
                db, query, video_ids, user_id, num_videos, mode, config
            )

    def _retrieve_coverage(
        self,
        db: Session,
        video_ids: list[UUID],
        num_videos: int,
        mode: str,  # noqa: ARG002
    ) -> RetrievalResult:
        """
        Retrieve video summaries for coverage queries.

        For "summarize all", "main themes", "compare speakers" type queries.
        """
        # Fetch videos with summaries
        videos = (
            db.query(Video)
            .filter(Video.id.in_(video_ids))
            .order_by(Video.created_at.desc())
            .limit(50)
            .all()
        )

        video_summaries = []
        context_parts = []
        missing_summaries = 0
        videos_used = []

        for i, video in enumerate(videos, 1):
            if video.summary:
                content_type = getattr(video, "content_type", "youtube")
                summary = VideoSummary(
                    video_id=video.id,
                    title=video.title,
                    channel_name=video.channel_name,
                    summary=video.summary,
                    key_topics=video.key_topics or [],
                    duration_seconds=video.duration_seconds,
                    content_type=content_type,
                    page_count=getattr(video, "page_count", None),
                )
                video_summaries.append(summary)
                videos_used.append(video)

                # Build context entry adapted to content type
                topics_str = ""
                if video.key_topics:
                    topics_str = f"\nKey Topics: {', '.join(video.key_topics[:5])}"

                if content_type == "youtube":
                    meta_line = f"Channel: {video.channel_name or 'Unknown'}{topics_str}"
                else:
                    type_label = content_type.upper()
                    page_info = f" ({video.page_count} pages)" if getattr(video, "page_count", None) else ""
                    meta_line = f"Type: {type_label}{page_info}{topics_str}"

                context_parts.append(
                    f'[Source {i}] "{video.title}"\n'
                    f"{meta_line}\n"
                    f"---\n{video.summary}\n"
                )
            else:
                missing_summaries += 1

        # Build context string
        if not context_parts:
            context = "No source summaries available."
        else:
            context = "\n---\n".join(context_parts)
            if missing_summaries > 0:
                context = (
                    f"NOTE: {missing_summaries} source(s) don't have summaries yet and are not included.\n\n"
                    + context
                )

        # Build video_map for citation building
        video_map = {v.id: v for v in videos_used}

        logger.info(
            f"[Coverage Retrieval] Built context from {len(video_summaries)} summaries "
            f"({missing_summaries} missing)"
        )

        return RetrievalResult(
            chunks=[],
            video_summaries=video_summaries,
            retrieval_type="summaries",
            context=context,
            context_is_weak=len(videos_used) == 0,
            video_map=video_map,
            videos_missing_summaries=missing_summaries,
            retrieval_stats={
                "videos_requested": num_videos,
                "summaries_found": len(video_summaries),
                "summaries_missing": missing_summaries,
            },
        )

    def _retrieve_chunks(
        self,
        db: Session,
        query: str,
        video_ids: list[UUID],
        user_id: UUID,
        num_videos: int,
        mode: str,
        config: RetrievalConfig,
        use_video_guarantee: bool = False,
        is_coverage_fallback: bool = False,
    ) -> RetrievalResult:
        """
        Full chunk retrieval pipeline.

        Pipeline stages:
        1. Query Expansion (multi-query variants)
        2. Multi-query embedding + vector search
        3. HyDE (hypothetical document embedding) for coverage
        4. BM25 keyword search + RRF fusion
        5. Reranking (cross-encoder)
        6. Relevance Grading (Self-RAG / Corrective RAG)
        7. Relevance threshold filtering
        8. Deduplication
        9. Context building
        """
        from app.services.embeddings import embedding_service

        diversity = self._get_diversity_factor(num_videos, mode)
        chunk_limit = self._get_chunk_limit(num_videos, mode)

        if is_coverage_fallback:
            path_reason = "coverage query with video guarantee (summaries unavailable)"
        elif use_video_guarantee:
            path_reason = "video guarantee search"
        else:
            path_reason = "precision query"
        logger.info(f"[Chunk Retrieval] Starting full pipeline for {path_reason}")

        # Stage 1: Query Expansion
        query_variants = self._run_query_expansion(query, config)

        # Stage 2: Multi-query embedding + vector search
        all_scored_chunks, embedding_time = self._run_multi_query_search(
            query_variants, user_id, video_ids, num_videos,
            diversity, chunk_limit, config,
            use_video_guarantee=use_video_guarantee,
            is_coverage_query=is_coverage_fallback,
        )

        # Sort by score
        scored_chunks = sorted(
            all_scored_chunks.values(), key=lambda c: c.score, reverse=True
        )

        logger.info(
            f"[Multi-Query Retrieval] Merged results: {len(scored_chunks)} unique chunks "
            f"from {len(query_variants)} queries in {embedding_time:.3f}s"
        )

        # Stage 3: HyDE for coverage queries
        if config.enable_hyde and is_coverage_fallback:
            scored_chunks = self._run_hyde(
                query, scored_chunks, all_scored_chunks,
                user_id, video_ids, diversity, config,
            )

        # Stage 4: BM25 keyword search + RRF fusion
        if config.enable_bm25:
            scored_chunks = self._run_bm25_fusion(
                db, query, scored_chunks, user_id, video_ids, config,
            )

        # Stage 5: Reranking
        if config.enable_reranking and scored_chunks:
            scored_chunks = self._run_reranking(query, scored_chunks, config)

        # Stage 6: Relevance Grading (Self-RAG)
        context_is_weak = False
        if config.enable_relevance_grading and scored_chunks and not is_coverage_fallback:
            scored_chunks, context_is_weak = self._run_relevance_grading(
                query, scored_chunks, embedding_service,
                user_id, video_ids, diversity, config,
            )

        # Stage 7: Relevance threshold filtering
        if is_coverage_fallback:
            high_quality_chunks = scored_chunks
            logger.info(
                f"[Relevance Filter] Coverage query - skipping threshold, "
                f"keeping all {len(scored_chunks)} chunks"
            )
        else:
            high_quality_chunks = [
                c for c in scored_chunks if c.score >= config.min_relevance_score
            ]
            if not high_quality_chunks:
                high_quality_chunks = [
                    c for c in scored_chunks if c.score >= config.fallback_relevance_score
                ]
                logger.warning(
                    f"[Relevance Filter] Using fallback threshold: {len(high_quality_chunks)} chunks"
                )

        # Determine context quality
        max_score = max((c.score for c in high_quality_chunks), default=0.0)
        if not context_is_weak:
            context_is_weak = max_score < config.weak_context_threshold

        # Stage 8: Deduplication
        if is_coverage_fallback:
            deduped_chunks = self._deduplicate_chunks(high_quality_chunks, by_video_only=True)
        else:
            deduped_chunks = self._deduplicate_chunks(high_quality_chunks, by_video_only=False)

        top_chunks = deduped_chunks[:chunk_limit]

        # Stage 9: Build context
        context, video_map = self._build_chunk_context(db, top_chunks)

        if context_is_weak and top_chunks:
            context = (
                f"NOTE: Retrieved context has low relevance (max {(max_score * 100):.0f}%). "
                f"The response may be speculative.\n\n{context}"
            )

        logger.info(
            f"[Chunk Retrieval] Pipeline complete: {len(scored_chunks)} candidates → "
            f"{len(high_quality_chunks)} filtered → {len(deduped_chunks)} deduped → "
            f"{len(top_chunks)} used (limit={chunk_limit})"
        )

        return RetrievalResult(
            chunks=top_chunks,
            video_summaries=[],
            retrieval_type="chunks",
            context=context,
            context_is_weak=context_is_weak,
            video_map=video_map,
            retrieval_stats={
                "candidates": len(scored_chunks),
                "filtered": len(high_quality_chunks),
                "deduped": len(deduped_chunks),
                "used": len(top_chunks),
                "diversity": diversity,
                "chunk_limit": chunk_limit,
                "unique_videos": len({c.video_id for c in top_chunks}),
                "pipeline": {
                    "query_expansion": config.enable_query_expansion,
                    "bm25": config.enable_bm25,
                    "hyde": config.enable_hyde and is_coverage_fallback,
                    "reranking": config.enable_reranking,
                    "relevance_grading": config.enable_relevance_grading,
                },
            },
        )

    def _retrieve_hybrid(
        self,
        db: Session,
        query: str,
        video_ids: list[UUID],
        user_id: UUID,
        num_videos: int,
        mode: str,
        config: RetrievalConfig,
    ) -> RetrievalResult:
        """
        Retrieve both summaries and targeted chunks for hybrid queries.

        For "summarize with quotes", "compare with examples" type queries.
        """
        # Get video summaries (for overview)
        coverage_result = self._retrieve_coverage(db, video_ids, num_videos, mode)

        # Get targeted chunks via full pipeline - use fewer chunks in hybrid mode
        chunk_result = self._retrieve_chunks(
            db, query, video_ids, user_id, num_videos, mode, config,
            use_video_guarantee=False, is_coverage_fallback=False,
        )

        # Merge video maps
        merged_video_map = {**coverage_result.video_map, **chunk_result.video_map}

        # Build combined context
        combined_context = (
            "## Video Summaries (Overview)\n\n"
            f"{coverage_result.context}\n\n"
            "## Supporting Evidence (Specific Quotes)\n\n"
            f"{chunk_result.context}"
        )

        logger.info(
            f"[Hybrid Retrieval] {len(coverage_result.video_summaries)} summaries + "
            f"{len(chunk_result.chunks)} chunks"
        )

        return RetrievalResult(
            chunks=chunk_result.chunks,
            video_summaries=coverage_result.video_summaries,
            retrieval_type="hybrid",
            context=combined_context,
            context_is_weak=chunk_result.context_is_weak and len(coverage_result.video_summaries) == 0,
            video_map=merged_video_map,
            videos_missing_summaries=coverage_result.videos_missing_summaries,
            retrieval_stats={
                "summaries_found": len(coverage_result.video_summaries),
                "chunks_found": len(chunk_result.chunks),
                "hybrid_mode": True,
                **{f"chunk_{k}": v for k, v in chunk_result.retrieval_stats.items()},
            },
        )

    # ── Pipeline Stage Methods ──────────────────────────────────────────

    def _run_query_expansion(
        self, query: str, config: RetrievalConfig,
    ) -> list[str]:
        """Stage 1: Generate query variants for multi-query retrieval."""
        if not config.enable_query_expansion:
            return [query]

        from app.services.query_expansion import get_query_expansion_service

        expansion_start = time.time()
        service = get_query_expansion_service()
        variants = service.expand_query(query)
        expansion_time = time.time() - expansion_start

        logger.info(
            f"[Query Expansion] Generated {len(variants)} variants in {expansion_time:.3f}s"
        )
        return variants

    def _run_multi_query_search(
        self,
        query_variants: list[str],
        user_id: UUID,
        video_ids: list[UUID],
        num_videos: int,
        diversity: float,
        chunk_limit: int,
        config: RetrievalConfig,
        use_video_guarantee: bool = False,
        is_coverage_query: bool = False,
    ) -> tuple[dict[UUID, ScoredChunk], float]:
        """Stage 2: Embed each query variant and search, merging by max score."""
        from app.services.embeddings import embedding_service

        embedding_start = time.time()
        all_scored_chunks: dict[UUID, ScoredChunk] = {}

        for idx, query_text in enumerate(query_variants):
            query_embedding = embedding_service.embed_text(query_text, is_query=True)
            if isinstance(query_embedding, tuple):
                query_embedding = np.array(query_embedding, dtype=np.float32)

            if use_video_guarantee and is_coverage_query and num_videos > 1:
                variant_chunks = vector_store_service.search_with_video_guarantee(
                    query_embedding=query_embedding,
                    video_ids=video_ids,
                    user_id=user_id,
                    top_k=chunk_limit,
                    prefetch_limit=self.MMR_PREFETCH_LIMIT,
                )
            else:
                variant_chunks = vector_store_service.search_with_diversity(
                    query_embedding=query_embedding,
                    user_id=user_id,
                    video_ids=video_ids,
                    top_k=config.retrieval_top_k,
                    diversity=diversity,
                    prefetch_limit=self.MMR_PREFETCH_LIMIT,
                )

            logger.info(
                f"[Vector Search] Variant {idx} retrieved {len(variant_chunks)} chunks"
            )

            for chunk in variant_chunks:
                chunk_id = chunk.chunk_id
                if chunk_id is None:
                    continue
                if chunk_id not in all_scored_chunks or chunk.score > all_scored_chunks[chunk_id].score:
                    all_scored_chunks[chunk_id] = chunk

        embedding_time = time.time() - embedding_start
        return all_scored_chunks, embedding_time

    def _run_hyde(
        self,
        query: str,
        scored_chunks: list[ScoredChunk],
        all_scored_chunks: dict[UUID, ScoredChunk],
        user_id: UUID,
        video_ids: list[UUID],
        diversity: float,
        config: RetrievalConfig,
    ) -> list[ScoredChunk]:
        """Stage 3: HyDE - generate hypothetical passage and search with it."""
        from app.services.hyde import get_hyde_service

        hyde_service = get_hyde_service()
        hyde_start = time.time()
        hyde_embedding = hyde_service.generate_hyde_embedding(query)

        if hyde_embedding is not None:
            hyde_chunks = vector_store_service.search_with_diversity(
                query_embedding=hyde_embedding,
                user_id=user_id,
                video_ids=video_ids,
                top_k=config.retrieval_top_k,
                diversity=diversity,
            )
            hyde_added = 0
            for chunk in hyde_chunks:
                chunk_id = chunk.chunk_id
                if chunk_id is None:
                    continue
                if chunk_id not in all_scored_chunks or chunk.score > all_scored_chunks[chunk_id].score:
                    all_scored_chunks[chunk_id] = chunk
                    hyde_added += 1

            scored_chunks = sorted(
                all_scored_chunks.values(), key=lambda c: c.score, reverse=True
            )
            hyde_time = time.time() - hyde_start
            logger.info(
                f"[HyDE] Added {hyde_added} chunks in {hyde_time:.3f}s"
            )
        else:
            logger.debug("[HyDE] No hypothetical embedding generated")

        return scored_chunks

    def _run_bm25_fusion(
        self,
        db: Session,
        query: str,
        scored_chunks: list[ScoredChunk],
        user_id: UUID,
        video_ids: list[UUID],
        config: RetrievalConfig,
    ) -> list[ScoredChunk]:
        """Stage 4: BM25 keyword search + RRF fusion."""
        from app.services.bm25_search import (
            _should_skip_bm25,
            get_bm25_search_service,
            rrf_fuse,
        )

        if _should_skip_bm25(query):
            logger.debug("[BM25 Search] Skipped: query too short")
            return scored_chunks

        bm25_service = get_bm25_search_service()
        if not bm25_service.enabled:
            return scored_chunks

        bm25_start = time.time()
        try:
            bm25_results = bm25_service.search(
                db=db,
                query=query,
                user_id=user_id,
                video_ids=video_ids,
                top_k=config.bm25_top_k,
            )
            if bm25_results:
                vector_ids = {c.chunk_id for c in scored_chunks}
                bm25_only = [r for r in bm25_results if r.chunk_id not in vector_ids]
                logger.info(
                    f"[BM25 Search] {len(bm25_results)} results "
                    f"({len(bm25_only)} unique to BM25) in "
                    f"{time.time() - bm25_start:.2f}s"
                )
                scored_chunks = rrf_fuse(
                    vector_chunks=scored_chunks,
                    bm25_results=bm25_results,
                    k=config.rrf_k,
                    vector_weight=config.rrf_vector_weight,
                    bm25_weight=config.rrf_bm25_weight,
                    max_bm25_unique=config.bm25_max_unique_chunks,
                )
            else:
                logger.info(
                    f"[BM25 Search] No results in {time.time() - bm25_start:.2f}s"
                )
        except Exception as e:
            logger.warning(f"[BM25 Search] Failed ({e}), using vector-only")

        return scored_chunks

    def _run_reranking(
        self,
        query: str,
        scored_chunks: list[ScoredChunk],
        config: RetrievalConfig,
    ) -> list[ScoredChunk]:
        """Stage 5: Cross-encoder reranking."""
        from app.services.reranker import reranker_service

        rerank_start = time.time()
        logger.info(
            f"[Reranking] Starting reranking of {len(scored_chunks)} chunks "
            f"(top_k={config.reranking_top_k})"
        )

        reranked = reranker_service.rerank_chunks(
            query=query,
            chunks=scored_chunks,
            top_k=config.reranking_top_k,
        )
        rerank_time = time.time() - rerank_start
        logger.info(
            f"[Reranking] Completed in {rerank_time:.3f}s, returned {len(reranked)} chunks"
        )
        return reranked

    def _run_relevance_grading(
        self,
        query: str,
        scored_chunks: list[ScoredChunk],
        embedding_service,
        user_id: UUID,
        video_ids: list[UUID],
        diversity: float,
        config: RetrievalConfig,
    ) -> tuple[list[ScoredChunk], bool]:
        """Stage 6: LLM-based relevance grading (Self-RAG / Corrective RAG)."""
        from app.services.relevance_grader import get_relevance_grader, CorrectiveAction

        grader = get_relevance_grader()
        grading_result = grader.grade_chunks(query, scored_chunks)
        context_is_weak = False

        if grading_result.corrective_action == CorrectiveAction.REFORMULATE and grading_result.reformulated_query:
            logger.info(f"[Self-RAG] Reformulating query: '{grading_result.reformulated_query[:80]}'")
            reform_embedding = embedding_service.embed_text(
                grading_result.reformulated_query, is_query=True
            )
            if isinstance(reform_embedding, tuple):
                reform_embedding = np.array(reform_embedding, dtype=np.float32)
            reform_chunks = vector_store_service.search_with_diversity(
                query_embedding=reform_embedding,
                user_id=user_id,
                video_ids=video_ids,
                top_k=config.retrieval_top_k,
                diversity=diversity,
            )
            if reform_chunks:
                scored_chunks = reform_chunks
                logger.info(f"[Self-RAG] Reformulation returned {len(reform_chunks)} chunks")

        elif grading_result.corrective_action == CorrectiveAction.EXPAND_SCOPE:
            logger.info("[Self-RAG] Expanding scope: increasing top_k")
            expand_embedding = embedding_service.embed_text(query, is_query=True)
            if isinstance(expand_embedding, tuple):
                expand_embedding = np.array(expand_embedding, dtype=np.float32)
            expand_chunks = vector_store_service.search_with_diversity(
                query_embedding=expand_embedding,
                user_id=user_id,
                video_ids=video_ids,
                top_k=config.retrieval_top_k * 2,
                diversity=max(0.3, diversity - 0.2),
            )
            if expand_chunks:
                scored_chunks = expand_chunks
                logger.info(f"[Self-RAG] Expanded scope returned {len(expand_chunks)} chunks")

        elif grading_result.corrective_action == CorrectiveAction.INSUFFICIENT:
            logger.warning("[Self-RAG] Insufficient context — no relevant chunks found")
            context_is_weak = True

        else:
            # Filter to only relevant/partial chunks
            scored_chunks = grader.filter_relevant(grading_result)
            logger.info(f"[Self-RAG] Kept {len(scored_chunks)} relevant chunks")

        return scored_chunks, context_is_weak

    # ── Helper Methods ──────────────────────────────────────────────────

    def _get_diversity_factor(self, num_videos: int, mode: str) -> float:
        """Calculate diversity factor based on video count and mode."""
        base = self.MODE_DIVERSITY.get(mode, self.DEFAULT_DIVERSITY)
        if num_videos > 3:
            base = min(base + (num_videos - 3) * 0.05, self.MAX_DIVERSITY)
        return base

    def _get_chunk_limit(self, num_videos: int, mode: str) -> int:
        """Calculate chunk limit based on video count and mode."""
        base = self.BASE_CHUNK_LIMITS.get(mode, self.DEFAULT_CHUNK_LIMIT)
        if num_videos > 3:
            return min(base + (num_videos - 3), self.MAX_CHUNK_LIMIT)
        return base

    def _deduplicate_chunks(
        self,
        chunks: list[ScoredChunk],
        by_video_only: bool = False,
        bucket_seconds: int = 30,
    ) -> list[ScoredChunk]:
        """Deduplicate chunks to avoid redundant citations."""
        seen_keys = set()
        deduped = []

        for chunk in chunks:
            if by_video_only:
                key = chunk.video_id
            else:
                content_type = getattr(chunk, "content_type", "youtube")
                if content_type != "youtube":
                    page = getattr(chunk, "page_number", 0) or 0
                    key = (chunk.video_id, page)
                else:
                    bucket = int(chunk.start_timestamp // bucket_seconds)
                    key = (chunk.video_id, bucket)

            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(chunk)

        return deduped

    def _build_chunk_context(
        self,
        db: Session,
        chunks: list[ScoredChunk],
    ) -> tuple[str, dict[UUID, Video]]:
        """Build context string from chunks with video metadata."""
        if not chunks:
            return "No relevant content found in the selected transcripts.", {}

        # Fetch video metadata
        video_ids = list({c.video_id for c in chunks})
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        video_map = {v.id: v for v in videos}

        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            video = video_map.get(chunk.video_id)
            video_title = video.title if video else "Unknown Video"
            content_type = getattr(chunk, "content_type", "youtube")
            topic = chunk.chapter_title or getattr(chunk, "section_heading", None) or chunk.title or "General"

            if content_type != "youtube":
                # Document context entry
                location_display = self._format_location_display(chunk)
                context_parts.append(
                    f'[Source {i}] from "{video_title}"\n'
                    f"Section: {topic}\n"
                    f"Location: {location_display}\n"
                    f"Relevance: {(chunk.score * 100):.0f}%\n"
                    f"---\n"
                    f"{chunk.text}\n"
                )
            else:
                # Video transcript context entry
                timestamp = self._format_timestamp(chunk.start_timestamp, chunk.end_timestamp)
                speaker = chunk.speakers[0] if chunk.speakers else "Unknown"

                context_parts.append(
                    f'[Source {i}] from "{video_title}"\n'
                    f"Speaker: {speaker}\n"
                    f"Topic: {topic}\n"
                    f"Time: {timestamp}\n"
                    f"Relevance: {(chunk.score * 100):.0f}%\n"
                    f"---\n"
                    f"{chunk.text}\n"
                )

        context = "\n---\n".join(context_parts)
        return context, video_map

    @staticmethod
    def _format_timestamp(start: float, end: float) -> str:
        """Format seconds into MM:SS or HH:MM:SS range."""
        start_h, start_rem = divmod(int(start), 3600)
        start_m, start_s = divmod(start_rem, 60)
        end_h, end_rem = divmod(int(end), 3600)
        end_m, end_s = divmod(end_rem, 60)

        if start_h or end_h:
            return f"{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}"
        return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

    @staticmethod
    def _format_location_display(chunk) -> str:
        """Format location display based on content type."""
        content_type = getattr(chunk, "content_type", "youtube")
        if content_type != "youtube":
            page = getattr(chunk, "page_number", None)
            if page:
                end_page = getattr(chunk, "end_page_number", None)
                if end_page and end_page != page:
                    return f"Pages {page}-{end_page}"
                return f"Page {page}"
            return "Document"
        start = getattr(chunk, "start_timestamp", 0)
        end = getattr(chunk, "end_timestamp", 0)
        return TwoLevelRetriever._format_timestamp(start, end)


# Global service instance
two_level_retriever = TwoLevelRetriever()


def get_two_level_retriever() -> TwoLevelRetriever:
    """Get two-level retriever instance."""
    return two_level_retriever
