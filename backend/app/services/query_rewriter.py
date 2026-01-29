"""
Query Rewriter Service - History-Aware Query Transformation

This service transforms follow-up queries into standalone questions by resolving
anaphoric references ("this", "it", "that", etc.) using conversation history.

Strategy:
- Detect if query contains anaphoric references that need resolution
- Load recent conversation history (configurable limit)
- Use LLM to rewrite query as a standalone question
- Return original query if rewriting not needed or fails

Based on:
- Anthropic's Contextual Retrieval patterns
- LangChain Query Transformations best practices
"""
import logging
import re
from typing import List, Optional

from app.services.llm_providers import LLMService, Message
from app.core.config import settings

logger = logging.getLogger(__name__)


# Patterns that suggest the query references prior context
ANAPHORA_PATTERNS = [
    r"\bthis\b",
    r"\bthat\b",
    r"\bit\b",
    r"\bthese\b",
    r"\bthose\b",
    r"\babove\b",
    r"\bagain\b",
    r"\bsame\b",
    r"\bprevious\b",
    r"\bearlier\b",
    r"\bmentioned\b",
    r"\bdiscussed\b",
    r"\bthe topic\b",
    r"\bthe point\b",
    r"\bthe information\b",
]

# Compiled regex for efficiency
_ANAPHORA_REGEX = re.compile("|".join(ANAPHORA_PATTERNS), re.IGNORECASE)


def needs_rewriting(query: str) -> bool:
    """
    Detect if a query likely contains anaphoric references that need resolution.

    Args:
        query: User query string

    Returns:
        True if query contains patterns suggesting it references prior context
    """
    return bool(_ANAPHORA_REGEX.search(query))


class QueryRewriterService:
    """
    Transforms follow-up queries into standalone questions.

    Uses conversation history to resolve anaphoric references like
    "this", "it", "that" into specific topics from prior messages.
    """

    def __init__(self, llm_service: LLMService | None = None):
        """
        Initialize query rewriter service.

        Args:
            llm_service: Optional LLM service. If None, creates new instance.
        """
        self.llm_service = llm_service or LLMService()
        self.enabled = settings.enable_query_rewriting
        self.history_limit = settings.query_rewrite_history_limit
        self.model = settings.query_rewrite_model

    def rewrite_query(
        self,
        query: str,
        conversation_history: List[dict],
    ) -> str:
        """
        Transform a follow-up query into a standalone question.

        Args:
            query: User's current query
            conversation_history: List of prior messages [{role, content}, ...]
                                  Should be ordered oldest to newest

        Returns:
            Rewritten standalone query, or original if rewriting not needed/fails
        """
        # Fast path: if disabled, return original
        if not self.enabled:
            logger.debug("[Query Rewriter] Disabled, returning original query")
            return query

        # Fast path: if no anaphora detected, skip LLM call
        if not needs_rewriting(query):
            logger.debug(
                f"[Query Rewriter] No anaphora detected in query, skipping rewrite: "
                f"'{query[:60]}...'"
            )
            return query

        # Fast path: if no history, can't resolve references
        if not conversation_history:
            logger.debug(
                "[Query Rewriter] No conversation history available, returning original"
            )
            return query

        try:
            logger.info(
                f"[Query Rewriter] Rewriting query with {len(conversation_history)} "
                f"history messages: '{query[:60]}...'"
            )

            rewritten = self._rewrite_with_llm(query, conversation_history)

            if rewritten and rewritten != query:
                logger.info(
                    f"[Query Rewriter] Rewrote: '{query[:50]}...' -> '{rewritten[:50]}...'"
                )
                return rewritten
            else:
                logger.debug("[Query Rewriter] LLM returned same or empty query")
                return query

        except Exception as e:
            logger.warning(
                f"[Query Rewriter] Failed to rewrite query: {e}. Using original."
            )
            return query

    def _rewrite_with_llm(
        self,
        query: str,
        conversation_history: List[dict],
    ) -> Optional[str]:
        """
        Use LLM to rewrite query into standalone form.

        Args:
            query: Current user query
            conversation_history: Prior messages

        Returns:
            Rewritten query or None if failed
        """
        # Format conversation history for prompt
        history_text = self._format_history(conversation_history)

        prompt = f"""Given the conversation history below, rewrite the user's latest question as a standalone question that can be understood without the conversation context.

Resolve any pronouns or references like "this", "it", "that", "the above", "again", "same" to their actual referents from the conversation.

If the question is already standalone and needs no rewriting, return it unchanged.
Return ONLY the rewritten question, nothing else.

Conversation History:
{history_text}

Latest Question: {query}

Standalone Question:"""

        messages = [Message(role="user", content=prompt)]

        response = self.llm_service.complete(
            messages=messages,
            model=self.model,
            max_tokens=200,  # Short response expected
            temperature=0.1,  # Very low temp for consistent, focused output
        )

        # Extract and clean the response
        rewritten = response.content.strip()

        # Remove any quotes that might wrap the response
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        if rewritten.startswith("'") and rewritten.endswith("'"):
            rewritten = rewritten[1:-1]

        # Basic validation
        if len(rewritten) < 5:
            return None

        return rewritten

    def _format_history(self, conversation_history: List[dict]) -> str:
        """
        Format conversation history for the prompt.

        Args:
            conversation_history: List of {role, content} dicts

        Returns:
            Formatted string for prompt
        """
        # Limit to configured history size
        recent_history = conversation_history[-self.history_limit :]

        lines = []
        for msg in recent_history:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")

            # Truncate very long messages to save tokens
            if len(content) > 500:
                content = content[:500] + "..."

            lines.append(f"{role}: {content}")

        return "\n".join(lines)


# Global instance
_query_rewriter_service: QueryRewriterService | None = None


def get_query_rewriter_service() -> QueryRewriterService:
    """Get or create global query rewriter service instance."""
    global _query_rewriter_service
    if _query_rewriter_service is None:
        _query_rewriter_service = QueryRewriterService()
    return _query_rewriter_service
