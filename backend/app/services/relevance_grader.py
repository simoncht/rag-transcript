"""
Self-RAG Relevance Grader — LLM-based chunk relevance grading.

After retrieval + reranking, grades each chunk as:
  RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT

When context is weak (< 50% RELEVANT), applies corrective strategies:
  - REFORMULATE: re-run retrieval with LLM-reformulated query
  - EXPAND_SCOPE: increase top_k, relax diversity
  - INSUFFICIENT: honest "not enough context" response
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)


class RelevanceGrade(str, Enum):
    RELEVANT = "RELEVANT"
    PARTIALLY_RELEVANT = "PARTIALLY_RELEVANT"
    IRRELEVANT = "IRRELEVANT"


class CorrectiveAction(str, Enum):
    NONE = "NONE"
    REFORMULATE = "REFORMULATE"
    EXPAND_SCOPE = "EXPAND_SCOPE"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass
class GradedChunk:
    """A chunk with its relevance grade."""

    chunk: Any  # ScoredChunk
    grade: RelevanceGrade
    reason: str = ""


@dataclass
class GradingResult:
    """Result of grading a set of retrieved chunks."""

    graded_chunks: List[GradedChunk]
    relevant_count: int
    partial_count: int
    irrelevant_count: int
    relevance_ratio: float  # fraction of RELEVANT chunks
    corrective_action: CorrectiveAction
    reformulated_query: Optional[str] = None

    @property
    def has_sufficient_context(self) -> bool:
        return self.relevance_ratio >= 0.5


class RelevanceGraderService:
    """
    Grades retrieved chunks for relevance using an LLM.

    Sends all chunks in a single LLM call for efficiency (~0.5-1s).
    """

    def __init__(self, llm_service: Optional[Any] = None, usage_collector=None):
        self.llm_service = llm_service
        self.enabled = getattr(settings, "enable_relevance_grading", False)
        self.usage_collector = usage_collector

    def _ensure_llm(self):
        if self.llm_service is None:
            from app.services.llm_providers import llm_service

            self.llm_service = llm_service

    def grade_chunks(
        self,
        query: str,
        chunks: Sequence[Any],
    ) -> GradingResult:
        """
        Grade each chunk's relevance to the query.

        Args:
            query: user query
            chunks: retrieved chunks (ScoredChunk objects with .text)

        Returns:
            GradingResult with grades and corrective action
        """
        if not self.enabled or not chunks:
            # Passthrough: treat all as relevant
            graded = [
                GradedChunk(chunk=c, grade=RelevanceGrade.RELEVANT)
                for c in chunks
            ]
            return GradingResult(
                graded_chunks=graded,
                relevant_count=len(graded),
                partial_count=0,
                irrelevant_count=0,
                relevance_ratio=1.0,
                corrective_action=CorrectiveAction.NONE,
            )

        self._ensure_llm()

        try:
            grades = self._grade_via_llm(query, chunks)
        except Exception as e:
            logger.warning(f"[Self-RAG] Grading failed: {e}, treating all as relevant")
            grades = [
                GradedChunk(chunk=c, grade=RelevanceGrade.RELEVANT)
                for c in chunks
            ]

        relevant = sum(1 for g in grades if g.grade == RelevanceGrade.RELEVANT)
        partial = sum(1 for g in grades if g.grade == RelevanceGrade.PARTIALLY_RELEVANT)
        irrelevant = sum(1 for g in grades if g.grade == RelevanceGrade.IRRELEVANT)
        total = len(grades)
        ratio = relevant / total if total > 0 else 0.0

        # Determine corrective action
        action = CorrectiveAction.NONE
        reformulated = None

        if ratio < 0.5:
            if ratio >= 0.25:
                action = CorrectiveAction.REFORMULATE
                reformulated = self._reformulate_query(query)
            elif ratio > 0:
                action = CorrectiveAction.EXPAND_SCOPE
            else:
                action = CorrectiveAction.INSUFFICIENT

        logger.info(
            f"[Self-RAG] Graded {total} chunks: {relevant} relevant, "
            f"{partial} partial, {irrelevant} irrelevant "
            f"(ratio={ratio:.2f}, action={action.value})"
        )

        return GradingResult(
            graded_chunks=grades,
            relevant_count=relevant,
            partial_count=partial,
            irrelevant_count=irrelevant,
            relevance_ratio=ratio,
            corrective_action=action,
            reformulated_query=reformulated,
        )

    def _grade_via_llm(
        self, query: str, chunks: Sequence[Any]
    ) -> List[GradedChunk]:
        """Grade chunks using a single LLM call."""
        from app.services.llm_providers import Message

        # Build chunk descriptions
        chunk_texts = []
        for i, chunk in enumerate(chunks):
            text = getattr(chunk, "text", "")[:300]
            chunk_texts.append(f"[{i}] {text}")

        chunks_block = "\n\n".join(chunk_texts)

        prompt = (
            "You are a retrieval quality judge. For each chunk, grade its relevance "
            "to the user's query as one of: RELEVANT, PARTIALLY_RELEVANT, IRRELEVANT.\n\n"
            f"User query: {query}\n\n"
            f"Retrieved chunks:\n{chunks_block}\n\n"
            "Return ONLY a JSON array of grades, one per chunk, in order:\n"
            '[{"grade": "RELEVANT"}, {"grade": "PARTIALLY_RELEVANT"}, ...]'
        )

        messages = [Message(role="user", content=prompt)]
        response = self.llm_service.complete(
            messages=messages, temperature=0.1, max_tokens=200
        )

        if self.usage_collector and response.usage:
            self.usage_collector.record(response, "relevance_grading")

        # Parse response
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            grade_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[Self-RAG] Failed to parse grades JSON: {raw[:200]}")
            return [
                GradedChunk(chunk=c, grade=RelevanceGrade.RELEVANT)
                for c in chunks
            ]

        graded = []
        for i, chunk in enumerate(chunks):
            if i < len(grade_list):
                grade_str = grade_list[i].get("grade", "RELEVANT").upper()
                try:
                    grade = RelevanceGrade(grade_str)
                except ValueError:
                    grade = RelevanceGrade.RELEVANT
            else:
                grade = RelevanceGrade.RELEVANT

            graded.append(GradedChunk(chunk=chunk, grade=grade))

        return graded

    def _reformulate_query(self, query: str) -> Optional[str]:
        """Use LLM to reformulate the query for better retrieval."""
        try:
            from app.services.llm_providers import Message

            prompt = (
                "The following query did not retrieve good results. "
                "Reformulate it to be more specific and searchable. "
                "Return ONLY the reformulated query, nothing else.\n\n"
                f"Original query: {query}\n\n"
                "Reformulated query:"
            )

            messages = [Message(role="user", content=prompt)]
            response = self.llm_service.complete(
                messages=messages, temperature=0.3, max_tokens=100
            )

            if self.usage_collector and response.usage:
                self.usage_collector.record(response, "relevance_grading")

            reformulated = response.content.strip().strip('"').strip("'")
            if reformulated and len(reformulated) > 5:
                logger.info(f"[Self-RAG] Reformulated query: '{reformulated[:100]}'")
                return reformulated
        except Exception as e:
            logger.warning(f"[Self-RAG] Query reformulation failed: {e}")

        return None

    def filter_relevant(self, grading_result: GradingResult) -> List[Any]:
        """Return only RELEVANT and PARTIALLY_RELEVANT chunks."""
        return [
            g.chunk
            for g in grading_result.graded_chunks
            if g.grade in (RelevanceGrade.RELEVANT, RelevanceGrade.PARTIALLY_RELEVANT)
        ]
