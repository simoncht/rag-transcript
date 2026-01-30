"""
Intent classifier for query routing.

Uses LLM to classify query intent as COVERAGE, PRECISION, or HYBRID,
with conversation context awareness for follow-up queries.

Based on the observation that mode (summarize/deep_dive) should affect
response formatting, not retrieval strategy. Query intent determines retrieval:
- COVERAGE: Get video summaries for "summarize all", "key themes" queries
- PRECISION: Get relevant chunks for "what did X say", "find the part" queries
- HYBRID: Get both for "summarize with examples", "compare with quotes" queries
"""
import json
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


@dataclass
class ConversationTurn:
    """A single turn in conversation history."""

    role: str  # "user" or "assistant"
    content: str
    intent: Optional[QueryIntent] = None  # Intent if this was a classified query


class IntentClassifier:
    """
    LLM-based intent classifier for query routing.

    Uses DeepSeek to classify queries into COVERAGE, PRECISION, or HYBRID
    intents, with conversation context awareness for follow-up queries.

    Fallback behavior:
    - If LLM fails or confidence < 0.7, falls back to mode-based heuristics
    - If regex patterns match, uses those with moderate confidence
    """

    # Confidence threshold for using LLM classification
    CONFIDENCE_THRESHOLD = 0.7

    # Regex patterns for fallback classification
    COVERAGE_PATTERNS = [
        r"\bsummar(y|ize|ise|izing|ising)\b",
        r"\boverview\b",
        r"\bmain points?\b",
        r"\bkey (points?|takeaways?|themes?|topics?|ideas?)\b",
        r"\bwhat (are|is) (this|these|the) (videos?|transcripts?) about\b",
        r"\bgist\b",
        r"\bhighlights?\b",
        r"\btl;?dr\b",
        r"\bin (short|brief|summary)\b",
        r"\ball (the )?(videos?|sources?|transcripts?)\b",
        r"\bacross (all|the|these)\b",
        r"\beach (video|source|transcript)\b",
        r"\bevery (video|source|transcript)\b",
        r"\bcompare\b.*\b(videos?|sources?|speakers?)\b",
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

    async def classify(
        self,
        query: str,
        mode: str,
        num_videos: int,
        recent_messages: Optional[list[dict[str, str]]] = None,
        conversation_facts: Optional[list[str]] = None,
    ) -> IntentClassification:
        """
        Classify query intent using LLM with conversation context.

        Args:
            query: User's query text
            mode: Conversation mode (summarize, deep_dive, etc.)
            num_videos: Number of videos selected
            recent_messages: Last 2-3 conversation turns for context
            conversation_facts: Extracted facts for long conversations

        Returns:
            IntentClassification with intent, confidence, and reasoning
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

        # Try LLM classification
        try:
            llm_result = await self._classify_with_llm(
                query=query,
                mode=mode,
                num_videos=num_videos,
                recent_messages=recent_messages,
                conversation_facts=conversation_facts,
            )

            if llm_result and llm_result.confidence >= self.CONFIDENCE_THRESHOLD:
                logger.info(
                    f"[Intent Classifier] LLM classification: {llm_result.intent.value} "
                    f"(confidence={llm_result.confidence:.2f})"
                )
                return llm_result

            # LLM returned low confidence, fall back to heuristics
            logger.info(
                f"[Intent Classifier] LLM confidence too low ({llm_result.confidence:.2f}), "
                f"falling back to heuristics"
            )

        except Exception as e:
            logger.warning(
                f"[Intent Classifier] LLM classification failed: {e}, using fallback"
            )

        # Fallback to regex-based classification
        return self._classify_with_regex(query, mode, num_videos)

    def classify_sync(
        self,
        query: str,
        mode: str,
        num_videos: int,
        recent_messages: Optional[list[dict[str, str]]] = None,
        conversation_facts: Optional[list[str]] = None,  # noqa: ARG002
    ) -> IntentClassification:
        """
        Synchronous version of classify for non-async contexts.

        Uses regex-based classification only (no LLM call).
        For async contexts, prefer classify() which uses LLM.
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

    async def _classify_with_llm(
        self,
        query: str,
        mode: str,
        num_videos: int,
        recent_messages: Optional[list[dict[str, str]]] = None,
        conversation_facts: Optional[list[str]] = None,
    ) -> IntentClassification:
        """Classify intent using LLM."""
        from app.services.llm_providers import Message as LLMMessage
        from app.services.llm_providers import llm_service

        # Build conversation context
        context_parts = []

        if recent_messages:
            context_parts.append("Recent conversation:")
            for msg in recent_messages[-3:]:  # Last 3 turns
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate for efficiency
                context_parts.append(f"- {role.title()}: {content}...")

        if conversation_facts:
            context_parts.append("\nExtracted facts (for long conversations):")
            for fact in conversation_facts[:5]:  # Top 5 facts
                context_parts.append(f"- {fact}")

        conversation_context = (
            "\n".join(context_parts) if context_parts else "No prior context."
        )

        # Build prompt
        prompt = f"""Classify the user's query as COVERAGE, PRECISION, or HYBRID.

COVERAGE: User wants an overview, summary, or comparison across ALL videos.
Examples: "summarize these videos", "what are the main themes?", "compare the speakers"

PRECISION: User wants specific information, quotes, or details from relevant videos only.
Examples: "why do schools kill creativity?", "what did Ken Robinson say about mistakes?"

HYBRID: User wants both overview AND specific evidence/examples.
Examples: "summarize and give me key quotes", "what themes are covered with examples?"

## Conversation Context
{conversation_context}

## Current Query
Query: "{query}"
Number of videos: {num_videos}
Mode: {mode}

## Instructions
- Consider the conversation context when classifying
- "Tell me more" or "expand on that" → Use previous query's intent
- "Now summarize" or "give me an overview" → COVERAGE (regardless of previous)
- "Why" questions seeking specific explanations → PRECISION (not COVERAGE)
- If query is ambiguous and no context helps, use lower confidence

Output JSON only:
{{"intent": "COVERAGE" or "PRECISION" or "HYBRID", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

        messages = [LLMMessage(role="user", content=prompt)]

        # Use low temperature for consistent classification
        response = llm_service.complete(
            messages,
            temperature=0.2,
            max_tokens=150,
            model="deepseek-chat",  # Use chat model for classification
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            content = response.content.strip()
            if content.startswith("```"):
                # Remove markdown code block
                content = re.sub(r"```(?:json)?\s*", "", content)
                content = content.rstrip("`")

            data = json.loads(content)

            intent_str = data.get("intent", "PRECISION").upper()
            intent = QueryIntent(intent_str.lower())
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "LLM classification")

            return IntentClassification(
                intent=intent,
                confidence=confidence,
                reasoning=reasoning,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[Intent Classifier] Failed to parse LLM response: {e}")
            # Return low-confidence result to trigger fallback
            return IntentClassification(
                intent=QueryIntent.PRECISION,
                confidence=0.3,
                reasoning="Failed to parse LLM response",
            )

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

        # No clear patterns - use mode as fallback
        mode_prefers_coverage = mode in ("summarize", "compare_sources")
        mode_prefers_precision = mode in ("deep_dive", "extract_actions")

        if mode_prefers_coverage and num_videos > 1:
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


# Global service instance
intent_classifier = IntentClassifier()


def get_intent_classifier() -> IntentClassifier:
    """Get intent classifier instance."""
    return intent_classifier
