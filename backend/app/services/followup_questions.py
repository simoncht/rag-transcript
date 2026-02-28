"""
Follow-up question suggestion service.

Generates 2-3 follow-up questions grounded in retrieved chunks after each response.
Questions are filtered to only suggest things that can be answered from existing sources.

Based on:
- FollowGPT (CIKM 2024): Questions grounded in retrieved chunks
- Proactive Agents (CHI 2025): Filtered by answerability
"""

import json
import logging
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_followup_questions(
    query: str,
    response: str,
    chunks: list,
    mode: str = "summarize",
    num_videos: int = 1,
    usage_collector=None,
) -> List[str]:
    """
    Generate 2-3 follow-up questions grounded in available chunks.

    Args:
        query: The original user question
        response: The assistant's response
        chunks: List of scored chunks used in the response
        mode: Current conversation mode
        num_videos: Number of videos in the conversation scope

    Returns:
        List of 2-3 follow-up question strings, or empty list on failure
    """
    if not settings.enable_followup_questions:
        return []

    if not chunks:
        return []

    try:
        from app.services.llm_providers import llm_service, Message as LLMMessage

        # Build a summary of available chunk topics for grounding
        chunk_summaries = []
        for i, chunk in enumerate(chunks[:5], 1):
            text_preview = chunk.text[:200] if hasattr(chunk, "text") else str(chunk)[:200]
            chunk_summaries.append(f"[Source {i}]: {text_preview}")

        chunks_context = "\n".join(chunk_summaries)

        prompt = f"""Given this Q&A exchange and the source material available, suggest 2-3 follow-up questions.

User question: {query}
Assistant response (first 500 chars): {response[:500]}

Available source material:
{chunks_context}

Rules:
1. Each question MUST be answerable from the source material shown above
2. Questions should explore a DIFFERENT angle than what was already asked
3. Be specific - no generic "tell me more" questions
4. If {num_videos} > 1 videos, consider cross-video comparison questions
5. Adapt to mode "{mode}": summarize=breadth, deep_dive=specificity, compare_sources=contrast

Return ONLY a JSON array of 2-3 question strings, nothing else.
Example: ["How does X compare to Y?", "What specific steps are recommended for Z?"]"""

        llm_messages = [
            LLMMessage(role="system", content="You generate follow-up questions. Return only a JSON array."),
            LLMMessage(role="user", content=prompt),
        ]

        llm_response = llm_service.complete(
            llm_messages,
            temperature=0.3,
            max_tokens=300,
            model="deepseek-chat",  # Always use fast model for this
        )

        if usage_collector and llm_response.usage:
            usage_collector.record(llm_response, "followup")

        # Parse JSON response
        content = llm_response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            content = content.rsplit("```", 1)[0].strip()

        questions = json.loads(content)
        if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
            return questions[:3]

        logger.warning(f"[Follow-up Questions] Unexpected format: {type(questions)}")
        return []

    except json.JSONDecodeError as e:
        logger.warning(f"[Follow-up Questions] JSON parse error: {e}")
        return []
    except Exception as e:
        logger.warning(f"[Follow-up Questions] Generation failed: {e}")
        return []
