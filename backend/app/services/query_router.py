"""
Query router for two-level retrieval (LEGACY - use intent_classifier.py instead).

This module is retained for backward compatibility and provides regex-based
fallback routing when the LLM-based intent classifier is unavailable.

The primary intent classification is now done by intent_classifier.py which
uses LLM to classify queries as COVERAGE, PRECISION, or HYBRID with
conversation context awareness.

Routes queries to the appropriate retrieval strategy:
- Video summaries: For coverage queries (summarize all, compare sources)
- Chunk retrieval: For precision queries (specific details, facts)

Based on Google NotebookLM's approach of using source summaries for
high-level questions and chunk retrieval for specific questions.
"""
import logging
import re
from typing import List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RetrievalStrategy(Enum):
    """Retrieval strategy types."""
    VIDEO_SUMMARIES = "video_summaries"  # Use video-level summaries
    CHUNK_RETRIEVAL = "chunk_retrieval"  # Use chunk-level retrieval
    HYBRID = "hybrid"  # Use both (video summaries + targeted chunks)


@dataclass
class RoutingDecision:
    """Result of query routing decision."""
    strategy: RetrievalStrategy
    reason: str
    confidence: float  # 0.0 to 1.0
    use_diversity: bool  # Whether to apply MMR diversity
    chunk_limit: int  # How many chunks/summaries to retrieve
    has_coverage_intent: bool = False  # True if query has coverage/summarize intent (regardless of strategy)


class QueryRouter:
    """
    Routes queries to appropriate retrieval strategy.

    Decision factors:
    1. Query intent (summarize vs specific question)
    2. Number of videos selected
    3. Conversation mode
    4. Presence of summary-related keywords
    """

    # Patterns indicating coverage/summary intent
    COVERAGE_PATTERNS = [
        r"\bsummar(y|ize|ise|izing|ising)\b",
        r"\boverview\b",
        r"\bmain points?\b",
        r"\bkey (points?|takeaways?|themes?|topics?|ideas?)\b",
        r"\bwhat (are|is) (this|these|the) (videos?|transcripts?) about\b",
        r"\bgist\b",
        r"\bhighlights?\b",
        r"\bbrief(ly)?\b",
        r"\btl;?dr\b",
        r"\bin (short|brief|summary)\b",
        r"\ball (the )?(videos?|sources?|transcripts?)\b",
        r"\bacross (all|the|these)\b",
        r"\beach (video|source|transcript)\b",
        r"\bevery (video|source|transcript)\b",
        r"\bcompare\b.*\b(videos?|sources?|speakers?)\b",
        r"\bdifferences?\b.*\b(between|across)\b",
    ]

    # Patterns indicating precision/specific intent
    PRECISION_PATTERNS = [
        r"\bwhat did .+ say about\b",
        r"\bwhen did\b",
        r"\bwhere did\b",
        r"\bwho said\b",
        r"\bhow (does|did|do)\b",
        r"\bfind (the|a)?\b",
        r"\bspecific(ally)?\b",
        r"\bexact(ly)?\b",
        r"\bquote\b",
        r"\bclip\b",
        r"\bmoment\b",
        r"\btimestamp\b",
        r"\bpart where\b",
        r"\bsection (about|on|where)\b",
    ]

    # Video count thresholds
    MULTI_VIDEO_THRESHOLD = 5  # Above this, prefer summaries for coverage queries
    LARGE_COLLECTION_THRESHOLD = 20  # Above this, strongly prefer summaries

    def __init__(self):
        """Initialize query router."""
        # Compile regex patterns for efficiency
        self.coverage_regex = [re.compile(p, re.IGNORECASE) for p in self.COVERAGE_PATTERNS]
        self.precision_regex = [re.compile(p, re.IGNORECASE) for p in self.PRECISION_PATTERNS]

    def _detect_coverage_intent(self, query: str) -> Tuple[bool, float]:
        """
        Detect if query has coverage/summary intent.

        Returns:
            Tuple of (is_coverage, confidence)
        """
        matches = sum(1 for pattern in self.coverage_regex if pattern.search(query))
        if matches > 0:
            confidence = min(0.9, 0.5 + matches * 0.15)
            return True, confidence
        return False, 0.0

    def _detect_precision_intent(self, query: str) -> Tuple[bool, float]:
        """
        Detect if query has precision/specific intent.

        Returns:
            Tuple of (is_precision, confidence)
        """
        matches = sum(1 for pattern in self.precision_regex if pattern.search(query))
        if matches > 0:
            confidence = min(0.9, 0.5 + matches * 0.15)
            return True, confidence
        return False, 0.0

    def route_query(
        self,
        query: str,
        num_videos: int,
        mode: str,
        videos_have_summaries: bool = True,
    ) -> RoutingDecision:
        """
        Route query to appropriate retrieval strategy.

        Args:
            query: User's query text
            num_videos: Number of videos selected in conversation
            mode: Conversation mode (summarize, deep_dive, etc.)
            videos_have_summaries: Whether selected videos have summaries

        Returns:
            RoutingDecision with strategy and parameters
        """
        # Detect query intent FIRST (needed for has_coverage_intent flag)
        is_coverage, coverage_confidence = self._detect_coverage_intent(query)
        is_precision, precision_confidence = self._detect_precision_intent(query)

        # Mode-based bias
        mode_prefers_coverage = mode in ("summarize", "compare_sources")
        mode_prefers_precision = mode in ("deep_dive", "extract_actions")

        # Video count factor
        large_collection = num_videos >= self.LARGE_COLLECTION_THRESHOLD
        multi_video = num_videos >= self.MULTI_VIDEO_THRESHOLD

        # Determine if this has coverage intent (for video guarantee search)
        # True if: query has coverage patterns OR (mode prefers coverage AND multi-video)
        has_coverage_intent = (
            is_coverage or
            (mode_prefers_coverage and multi_video)
        )

        logger.info(
            f"[Query Router] Query analysis: coverage={is_coverage} ({coverage_confidence:.2f}), "
            f"precision={is_precision} ({precision_confidence:.2f}), "
            f"num_videos={num_videos}, mode={mode}, has_coverage_intent={has_coverage_intent}"
        )

        # If no summaries available, fall back to chunk retrieval
        # But still pass through has_coverage_intent for video guarantee search
        if not videos_have_summaries:
            return RoutingDecision(
                strategy=RetrievalStrategy.CHUNK_RETRIEVAL,
                reason="Video summaries not available",
                confidence=1.0,
                use_diversity=num_videos > 3,
                chunk_limit=self._calculate_chunk_limit(num_videos, mode),
                has_coverage_intent=has_coverage_intent,
            )

        # Decision logic
        if is_coverage and not is_precision:
            # Clear coverage intent
            if multi_video or mode_prefers_coverage:
                return RoutingDecision(
                    strategy=RetrievalStrategy.VIDEO_SUMMARIES,
                    reason=f"Coverage query with {num_videos} videos",
                    confidence=coverage_confidence,
                    use_diversity=False,  # Summaries are already per-video
                    chunk_limit=min(num_videos, 50),  # Cap at 50 summaries
                    has_coverage_intent=True,
                )

        if is_precision and not is_coverage:
            # Clear precision intent
            return RoutingDecision(
                strategy=RetrievalStrategy.CHUNK_RETRIEVAL,
                reason="Precision query seeking specific details",
                confidence=precision_confidence,
                use_diversity=num_videos > 3,
                chunk_limit=self._calculate_chunk_limit(num_videos, mode),
                has_coverage_intent=False,
            )

        if is_coverage and is_precision:
            # Mixed intent - use hybrid approach
            return RoutingDecision(
                strategy=RetrievalStrategy.HYBRID,
                reason="Mixed intent query (coverage + precision)",
                confidence=min(coverage_confidence, precision_confidence),
                use_diversity=True,
                chunk_limit=self._calculate_chunk_limit(num_videos, mode),
                has_coverage_intent=True,  # Has some coverage intent
            )

        # No clear intent detected - use heuristics
        if large_collection and mode_prefers_coverage:
            return RoutingDecision(
                strategy=RetrievalStrategy.VIDEO_SUMMARIES,
                reason=f"Large collection ({num_videos} videos) with {mode} mode",
                confidence=0.6,
                use_diversity=False,
                chunk_limit=min(num_videos, 50),
                has_coverage_intent=True,
            )

        if mode_prefers_precision or num_videos <= 3:
            return RoutingDecision(
                strategy=RetrievalStrategy.CHUNK_RETRIEVAL,
                reason=f"Default to chunks for {mode} mode with {num_videos} videos",
                confidence=0.5,
                use_diversity=num_videos > 1,
                chunk_limit=self._calculate_chunk_limit(num_videos, mode),
                has_coverage_intent=False,
            )

        # Default: chunk retrieval with diversity for multi-video
        return RoutingDecision(
            strategy=RetrievalStrategy.CHUNK_RETRIEVAL,
            reason="Default strategy",
            confidence=0.4,
            use_diversity=multi_video,
            chunk_limit=self._calculate_chunk_limit(num_videos, mode),
            has_coverage_intent=has_coverage_intent,
        )

    def _calculate_chunk_limit(self, num_videos: int, mode: str) -> int:
        """Calculate appropriate chunk limit based on context."""
        base_limits = {
            "summarize": 6,
            "compare_sources": 8,
            "deep_dive": 4,
            "timeline": 6,
            "extract_actions": 5,
            "quiz_me": 6,
        }
        base = base_limits.get(mode, 4)

        # Scale up for multi-video
        if num_videos > 3:
            return min(base + (num_videos - 3), 12)
        return base


# Global service instance
query_router_service = QueryRouter()


def get_query_router_service() -> QueryRouter:
    """Get query router service instance."""
    return query_router_service
