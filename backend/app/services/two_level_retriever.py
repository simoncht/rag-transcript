"""
Two-level retriever for intent-based retrieval.

Routes retrieval based on classified intent:
- COVERAGE: Video summaries for overview queries
- PRECISION: Chunk retrieval for specific queries
- HYBRID: Both summaries and targeted chunks

This implements the NotebookLM-style approach where high-level queries
use pre-computed source summaries and detail queries use chunk retrieval.
"""
import logging
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
class VideoSummary:
    """Video-level summary for coverage queries."""

    video_id: UUID
    title: str
    channel_name: Optional[str]
    summary: str
    key_topics: list[str] = field(default_factory=list)
    duration_seconds: Optional[int] = None


@dataclass
class RetrievalResult:
    """Result of two-level retrieval."""

    chunks: list[ScoredChunk] = field(default_factory=list)
    video_summaries: list[VideoSummary] = field(default_factory=list)
    retrieval_type: str = "chunks"  # "chunks" | "summaries" | "hybrid"
    context: str = ""  # Pre-built context string for LLM
    videos_missing_summaries: int = 0
    retrieval_stats: dict[str, Any] = field(default_factory=dict)


class TwoLevelRetriever:
    """
    Two-level retrieval system based on intent classification.

    Routes to appropriate retrieval strategy:
    - COVERAGE: Get video summaries from database
    - PRECISION: Get relevant chunks via vector search
    - HYBRID: Get both summaries and targeted chunks

    The existing vector_store methods (search_with_diversity, search_with_video_guarantee)
    are already well-implemented. This class provides a unified interface that
    selects the appropriate method based on intent.
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
        query: str,  # noqa: ARG002
        query_embedding: np.ndarray,
        intent: IntentClassification,
        video_ids: list[UUID],
        user_id: UUID,
        mode: str,
    ) -> RetrievalResult:
        """
        Retrieve based on intent classification.

        Args:
            db: Database session
            query: User's query text
            query_embedding: Query embedding vector
            intent: Classified intent (COVERAGE, PRECISION, HYBRID)
            video_ids: List of selected video IDs
            user_id: User ID for filtering
            mode: Conversation mode for formatting

        Returns:
            RetrievalResult with chunks, summaries, and context
        """
        num_videos = len(video_ids)

        logger.info(
            f"[Two-Level Retrieval] Intent={intent.intent.value} "
            f"(confidence={intent.confidence:.2f}), videos={num_videos}, mode={mode}"
        )

        if intent.intent == QueryIntent.COVERAGE:
            return self._retrieve_coverage(db, video_ids, num_videos, mode)

        elif intent.intent == QueryIntent.PRECISION:
            return self._retrieve_precision(
                db, query_embedding, video_ids, user_id, num_videos, mode
            )

        else:  # HYBRID
            return self._retrieve_hybrid(
                db, query_embedding, video_ids, user_id, num_videos, mode
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
            .limit(50)  # Cap at 50 video summaries
            .all()
        )

        video_summaries = []
        context_parts = []
        missing_summaries = 0

        for i, video in enumerate(videos, 1):
            if video.summary:
                summary = VideoSummary(
                    video_id=video.id,
                    title=video.title,
                    channel_name=video.channel_name,
                    summary=video.summary,
                    key_topics=video.key_topics or [],
                    duration_seconds=video.duration_seconds,
                )
                video_summaries.append(summary)

                # Build context entry
                topics_str = ""
                if video.key_topics:
                    topics_str = f"\nKey Topics: {', '.join(video.key_topics[:5])}"

                context_parts.append(
                    f'[Source {i}] "{video.title}"\n'
                    f"Channel: {video.channel_name or 'Unknown'}{topics_str}\n"
                    f"---\n{video.summary}\n"
                )
            else:
                missing_summaries += 1

        # Build context string
        if not context_parts:
            context = "No video summaries available. Please process videos first."
        else:
            context = "\n---\n".join(context_parts)
            if missing_summaries > 0:
                context = (
                    f"NOTE: {missing_summaries} video(s) don't have summaries yet.\n\n"
                    + context
                )

        logger.info(
            f"[Coverage Retrieval] Built context from {len(video_summaries)} summaries "
            f"({missing_summaries} missing)"
        )

        return RetrievalResult(
            chunks=[],
            video_summaries=video_summaries,
            retrieval_type="summaries",
            context=context,
            videos_missing_summaries=missing_summaries,
            retrieval_stats={
                "videos_requested": num_videos,
                "summaries_found": len(video_summaries),
                "summaries_missing": missing_summaries,
            },
        )

    def _retrieve_precision(
        self,
        db: Session,
        query_embedding: np.ndarray,
        video_ids: list[UUID],
        user_id: UUID,
        num_videos: int,
        mode: str,
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks for precision queries.

        For "what did X say", "find the part", "why" type queries.
        Uses standard diversity-aware search (NOT video guarantee).
        """
        diversity = self._get_diversity_factor(num_videos, mode)
        chunk_limit = self._get_chunk_limit(num_videos, mode)

        # Use standard diversity search - let relevance determine sources
        scored_chunks = vector_store_service.search_with_diversity(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=settings.retrieval_top_k,
            diversity=diversity,
            prefetch_limit=self.MMR_PREFETCH_LIMIT,
        )

        # Apply relevance filtering
        high_quality_chunks = [
            c for c in scored_chunks if c.score >= settings.min_relevance_score
        ]

        if not high_quality_chunks:
            # Fallback to lower threshold
            high_quality_chunks = [
                c for c in scored_chunks if c.score >= settings.fallback_relevance_score
            ]
            logger.warning(
                f"[Precision Retrieval] Using fallback threshold, "
                f"found {len(high_quality_chunks)} chunks"
            )

        # Deduplicate nearby chunks (30s buckets)
        deduped_chunks = self._deduplicate_chunks(
            high_quality_chunks, by_video_only=False
        )

        # Take top chunks up to limit
        top_chunks = deduped_chunks[:chunk_limit]

        # Build context
        context, video_map = self._build_chunk_context(db, top_chunks)

        logger.info(
            f"[Precision Retrieval] Found {len(scored_chunks)} → "
            f"{len(high_quality_chunks)} filtered → {len(deduped_chunks)} deduped → "
            f"{len(top_chunks)} used (limit={chunk_limit})"
        )

        return RetrievalResult(
            chunks=top_chunks,
            video_summaries=[],
            retrieval_type="chunks",
            context=context,
            retrieval_stats={
                "candidates": len(scored_chunks),
                "filtered": len(high_quality_chunks),
                "deduped": len(deduped_chunks),
                "used": len(top_chunks),
                "diversity": diversity,
                "chunk_limit": chunk_limit,
                "unique_videos": len({c.video_id for c in top_chunks}),
            },
        )

    def _retrieve_hybrid(
        self,
        db: Session,
        query_embedding: np.ndarray,
        video_ids: list[UUID],
        user_id: UUID,
        num_videos: int,
        mode: str,
    ) -> RetrievalResult:
        """
        Retrieve both summaries and targeted chunks for hybrid queries.

        For "summarize with quotes", "compare with examples" type queries.
        """
        # Get video summaries (for overview)
        coverage_result = self._retrieve_coverage(db, video_ids, num_videos, mode)

        # Get targeted chunks (for evidence) - use fewer chunks in hybrid mode
        diversity = self._get_diversity_factor(num_videos, mode)
        chunk_limit = max(
            3, self._get_chunk_limit(num_videos, mode) // 2
        )  # Fewer chunks for hybrid

        scored_chunks = vector_store_service.search_with_diversity(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=settings.retrieval_top_k,
            diversity=diversity,
            prefetch_limit=self.MMR_PREFETCH_LIMIT,
        )

        high_quality_chunks = [
            c for c in scored_chunks if c.score >= settings.min_relevance_score
        ]
        deduped_chunks = self._deduplicate_chunks(
            high_quality_chunks, by_video_only=False
        )
        top_chunks = deduped_chunks[:chunk_limit]

        # Build combined context
        chunk_context, video_map = self._build_chunk_context(db, top_chunks)

        combined_context = (
            "## Video Summaries (Overview)\n\n"
            f"{coverage_result.context}\n\n"
            "## Supporting Evidence (Specific Quotes)\n\n"
            f"{chunk_context}"
        )

        logger.info(
            f"[Hybrid Retrieval] {len(coverage_result.video_summaries)} summaries + "
            f"{len(top_chunks)} chunks"
        )

        return RetrievalResult(
            chunks=top_chunks,
            video_summaries=coverage_result.video_summaries,
            retrieval_type="hybrid",
            context=combined_context,
            videos_missing_summaries=coverage_result.videos_missing_summaries,
            retrieval_stats={
                "summaries_found": len(coverage_result.video_summaries),
                "chunks_found": len(top_chunks),
                "hybrid_mode": True,
            },
        )

    def _get_diversity_factor(self, num_videos: int, mode: str) -> float:
        """Calculate diversity factor based on video count and mode."""
        base = self.MODE_DIVERSITY.get(mode, self.DEFAULT_DIVERSITY)

        # Scale up for multi-video (add 0.05 per video beyond 3)
        if num_videos > 3:
            base = min(base + (num_videos - 3) * 0.05, self.MAX_DIVERSITY)

        return base

    def _get_chunk_limit(self, num_videos: int, mode: str) -> int:
        """Calculate chunk limit based on video count and mode."""
        base = self.BASE_CHUNK_LIMITS.get(mode, self.DEFAULT_CHUNK_LIMIT)

        # Scale up for multi-video
        if num_videos > 3:
            return min(base + (num_videos - 3), self.MAX_CHUNK_LIMIT)

        return base

    def _deduplicate_chunks(
        self,
        chunks: list[ScoredChunk],
        by_video_only: bool = False,
        bucket_seconds: int = 30,
    ) -> list[ScoredChunk]:
        """
        Deduplicate chunks to avoid redundant citations.

        Args:
            chunks: List of scored chunks
            by_video_only: If True, keep only 1 chunk per video
            bucket_seconds: Time bucket for timestamp-based deduplication

        Returns:
            Deduplicated chunks
        """
        seen_keys = set()
        deduped = []

        for chunk in chunks:
            if by_video_only:
                key = chunk.video_id
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
        """
        Build context string from chunks with video metadata.

        Returns:
            Tuple of (context_string, video_map)
        """
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

            # Format timestamps
            start_h, start_rem = divmod(int(chunk.start_timestamp), 3600)
            start_m, start_s = divmod(start_rem, 60)
            end_h, end_rem = divmod(int(chunk.end_timestamp), 3600)
            end_m, end_s = divmod(end_rem, 60)

            if start_h or end_h:
                timestamp = f"{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}"
            else:
                timestamp = f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

            speaker = chunk.speakers[0] if chunk.speakers else "Unknown"
            topic = chunk.chapter_title or chunk.title or "General"

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

        # Add weak context warning if needed
        max_score = max(c.score for c in chunks) if chunks else 0.0
        if max_score < settings.weak_context_threshold:
            context = (
                f"NOTE: Retrieved context has low relevance (max {(max_score * 100):.0f}%). "
                f"The response may be speculative.\n\n{context}"
            )

        return context, video_map


# Global service instance
two_level_retriever = TwoLevelRetriever()


def get_two_level_retriever() -> TwoLevelRetriever:
    """Get two-level retriever instance."""
    return two_level_retriever
