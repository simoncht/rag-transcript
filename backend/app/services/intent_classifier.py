"""
Intent classifier for query routing.

Uses regex patterns to classify query intent as COVERAGE, PRECISION, or HYBRID,
with conversation context awareness for follow-up queries.

Based on the observation that mode (summarize/deep_dive) should affect
response formatting, not retrieval strategy. Query intent determines retrieval:
- COVERAGE: Get video summaries for "summarize all", "key themes" queries
- PRECISION: Get relevant chunks for "what did X say", "find the part" queries
- HYBRID: Get both for "summarize with examples", "compare with quotes" queries
"""
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Query intent types for retrieval routing."""

    COVERAGE = "coverage"  # "summarize all", "key themes across videos"
    PRECISION = "precision"  # "why X?", "what did Y say about Z?"
    HYBRID = "hybrid"  # "summarize and give examples", needs both


@dataclass
class IntentClassification:
    """Result of intent classification."""

    intent: QueryIntent
    confidence: float  # 0.0-1.0
    reasoning: str  # Brief explanation

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class IntentClassifier:
    """
    Regex-based intent classifier for query routing.

    Classifies queries into COVERAGE, PRECISION, or HYBRID intents using
    pattern matching and heuristics, with conversation context awareness
    for follow-up queries.
    """

    # Regex patterns for classification
    COVERAGE_PATTERNS = [
        r"\bsummar(y|ize|ise|izing|ising)\b",
        r"\boverview\b",
        r"\bmain points?\b",
        r"\bkey (points?|takeaways?|themes?|topics?|ideas?)\b",
        r"\bwhat (is|are) (this|these|it|the)( \w+)? (all )?about\b",
        r"\bgist\b",
        r"\bhighlights?\b",
        r"\btl;?dr\b",
        r"\bin (short|brief|summary)\b",
        r"\ball (the )?(videos?|sources?|transcripts?|documents?|files?)\b",
        r"\bacross (all|the|these)\b",
        r"\beach (video|source|transcript|document|file|podcast|recording)\b",
        r"\bevery (video|source|transcript|document|file|podcast|recording)\b",
        r"\bcompare\b.*\b(videos?|sources?|speakers?)\b",
        # Cross-source synthesis patterns
        r"\b(relationship|connection|relate|connect|common|shared|overlap|link|tie)\b.*\b(between|across|among)\b",
        r"\b(between|across|among)\b.*\b(sources?|videos?|documents?|transcripts?)\b",
        r"\b(common|shared|overlapping|similar)\b.*\b(themes?|topics?|ideas?|points?|messages?)\b",
        r"\bhow (do|does|are)\b.*\b(relate|connect|overlap|tie together|intersect)\b",
        r"\b(similarities?|differences?|contrasts?|parallels?)\b.*\b(between|across|among)\b",
        r"\bwhat do .+ have in common\b",
        # Broad categorization/grouping patterns
        r"\b(different|various|main|major)\s+(themes?|topics?|categories)\b",
        r"\bgrouped?\b.*\b(by|into)\b",
        r"\bcategoriz(e|ed?|ing)\b",
        r"\bclassif(y|ied|ying)\b",
        r"\borganiz(e|ed?|ing)\b.*\b(by|into)\b",
        r"\bwhat (themes?|topics?|kind)\b.*\b(do|does|can|are)\b",
        r"\beach of (these|the|those|my)\b",
        r"\bwhat (topics?|subjects?)\b.*\bcover\b",
        r"\bbreak\s*down\b.*\b(content|all|these|the)\b",
        r"\bwhat can I learn\b",
        r"\bhow would you (organize|group|categorize|classify)\b",
        # "all N videos" pattern (handles numbers between "all" and "videos")
        r"\ball\s+\d+\s+(videos?|sources?|transcripts?|documents?|files?|podcasts?|recordings?)\b",
    ]

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
        r"\bwhy (do|did|does|is|are|was|were)\b",
    ]

    HYBRID_PATTERNS = [
        r"\bsummar(y|ize|ise)\b.*\b(quote|example|evidence)\b",
        r"\b(quote|example|evidence)\b.*\bsummar(y|ize|ise)\b",
        r"\boverview\b.*\b(with|including)\b.*\b(example|quote|evidence)\b",
        r"\bcompare\b.*\b(with|and)\b.*\b(example|quote|evidence)\b",
    ]

    # Follow-up patterns that inherit previous intent
    FOLLOW_UP_PATTERNS = [
        r"^tell me more\b",
        r"^expand on that\b",
        r"^go on\b",
        r"^continue\b",
        r"^more detail\b",
        r"^elaborate\b",
        r"^what else\b",
    ]

    # Intent-switch patterns (explicit change from previous)
    SWITCH_TO_COVERAGE_PATTERNS = [
        r"\bnow (give me|provide) (an )?overview\b",
        r"\bnow summarize\b",
        r"\bswitch to summary\b",
        r"\bgive me the (big picture|overview)\b",
    ]

    SWITCH_TO_PRECISION_PATTERNS = [
        r"\bnow (find|show) (me )?(the )?specific\b",
        r"\bnow tell me exactly\b",
        r"\bget specific\b",
        r"\bwhat specifically\b",
    ]

    def __init__(self):
        """Initialize intent classifier."""
        # Compile regex patterns for efficiency
        self._coverage_regex = [
            re.compile(p, re.IGNORECASE) for p in self.COVERAGE_PATTERNS
        ]
        self._precision_regex = [
            re.compile(p, re.IGNORECASE) for p in self.PRECISION_PATTERNS
        ]
        self._hybrid_regex = [
            re.compile(p, re.IGNORECASE) for p in self.HYBRID_PATTERNS
        ]
        self._follow_up_regex = [
            re.compile(p, re.IGNORECASE) for p in self.FOLLOW_UP_PATTERNS
        ]
        self._switch_coverage_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SWITCH_TO_COVERAGE_PATTERNS
        ]
        self._switch_precision_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SWITCH_TO_PRECISION_PATTERNS
        ]

    def classify_sync(
        self,
        query: str,
        mode: str,
        num_videos: int,
        recent_messages: Optional[list[dict[str, str]]] = None,
        conversation_facts: Optional[list[str]] = None,  # noqa: ARG002
    ) -> IntentClassification:
        """
        Classify query intent using regex patterns and heuristics.

        Uses regex-based classification with conversation context awareness.
        """
        # Check for follow-up patterns first
        if recent_messages and self._is_follow_up_query(query):
            previous_intent = self._infer_previous_intent(recent_messages)
            if previous_intent:
                return IntentClassification(
                    intent=previous_intent,
                    confidence=0.75,
                    reasoning="Follow-up query, continuing previous intent",
                )

        # Check for explicit intent-switch patterns
        switch_result = self._check_intent_switch(query)
        if switch_result:
            return switch_result

        # Use regex-based classification
        return self._classify_with_regex(query, mode, num_videos)

    def _is_follow_up_query(self, query: str) -> bool:
        """Check if query is a follow-up to previous conversation."""
        query_lower = query.lower().strip()
        return any(pattern.match(query_lower) for pattern in self._follow_up_regex)

    def _infer_previous_intent(
        self, recent_messages: list[dict[str, str]]
    ) -> Optional[QueryIntent]:
        """Infer intent from previous user query in conversation."""
        # Look at the last user message before current
        for msg in reversed(recent_messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Use regex to classify the previous query
                result = self._classify_with_regex(content, "default", 1)
                if result.confidence >= 0.6:
                    return result.intent
        return None

    def _check_intent_switch(self, query: str) -> Optional[IntentClassification]:
        """Check for explicit intent-switching patterns."""
        query_lower = query.lower()

        # Check for switch to coverage
        if any(pattern.search(query_lower) for pattern in self._switch_coverage_regex):
            return IntentClassification(
                intent=QueryIntent.COVERAGE,
                confidence=0.85,
                reasoning="Explicit switch to coverage/overview mode",
            )

        # Check for switch to precision
        if any(pattern.search(query_lower) for pattern in self._switch_precision_regex):
            return IntentClassification(
                intent=QueryIntent.PRECISION,
                confidence=0.85,
                reasoning="Explicit switch to precision/specific mode",
            )

        return None

    def _classify_with_regex(
        self,
        query: str,
        mode: str,
        num_videos: int,
    ) -> IntentClassification:
        """Classify intent using regex patterns and mode heuristics."""
        query_lower = query.lower()

        # Count pattern matches
        coverage_matches = sum(1 for p in self._coverage_regex if p.search(query_lower))
        precision_matches = sum(
            1 for p in self._precision_regex if p.search(query_lower)
        )
        hybrid_matches = sum(1 for p in self._hybrid_regex if p.search(query_lower))

        # Check for hybrid first (has both coverage and precision signals)
        if hybrid_matches > 0:
            return IntentClassification(
                intent=QueryIntent.HYBRID,
                confidence=min(0.85, 0.6 + hybrid_matches * 0.15),
                reasoning=f"Hybrid patterns matched ({hybrid_matches})",
            )

        # Clear coverage intent
        if coverage_matches > 0 and precision_matches == 0:
            return IntentClassification(
                intent=QueryIntent.COVERAGE,
                confidence=min(0.85, 0.5 + coverage_matches * 0.15),
                reasoning=f"Coverage patterns matched ({coverage_matches})",
            )

        # Clear precision intent
        if precision_matches > 0 and coverage_matches == 0:
            return IntentClassification(
                intent=QueryIntent.PRECISION,
                confidence=min(0.85, 0.5 + precision_matches * 0.15),
                reasoning=f"Precision patterns matched ({precision_matches})",
            )

        # Mixed signals - could be hybrid or use mode as tiebreaker
        if coverage_matches > 0 and precision_matches > 0:
            return IntentClassification(
                intent=QueryIntent.HYBRID,
                confidence=0.6,
                reasoning=f"Mixed signals (coverage={coverage_matches}, precision={precision_matches})",
            )

        # Multi-source safety net: if multiple sources and query contains
        # cross-source keywords, route to COVERAGE regardless of mode
        if num_videos > 1:
            cross_source_keywords = [
                "relationship", "connection", "relate", "connect", "common",
                "shared", "overlap", "between", "across", "among",
                "similarities", "differences", "compare", "contrast",
                "parallel", "theme", "link", "tie",
                "group", "categorize", "organize", "classify", "topics",
                "different", "various", "content", "learn", "cover",
            ]
            keyword_hits = sum(
                1 for kw in cross_source_keywords if kw in query_lower
            )
            # Lower threshold for many-video collections: 1 keyword is enough
            # when there are >5 videos since the user likely wants broad coverage
            min_hits = 1 if num_videos > 5 else 2
            if keyword_hits >= min_hits:
                return IntentClassification(
                    intent=QueryIntent.COVERAGE,
                    confidence=min(0.7, 0.5 + keyword_hits * 0.1),
                    reasoning=f"Cross-source keywords detected ({keyword_hits}) with {num_videos} sources",
                )

        # No clear patterns - use mode as fallback
        mode_prefers_coverage = mode in ("summarize", "compare_sources")
        mode_prefers_precision = mode in ("deep_dive", "extract_actions")

        if mode_prefers_coverage:
            return IntentClassification(
                intent=QueryIntent.COVERAGE,
                confidence=0.5,
                reasoning=f"Mode fallback ({mode} with {num_videos} videos)",
            )
        elif mode_prefers_precision:
            return IntentClassification(
                intent=QueryIntent.PRECISION,
                confidence=0.5,
                reasoning=f"Mode fallback ({mode})",
            )

        # Default to precision (more conservative - fewer chunks, more relevant)
        return IntentClassification(
            intent=QueryIntent.PRECISION,
            confidence=0.4,
            reasoning="Default to precision (no clear signals)",
        )
