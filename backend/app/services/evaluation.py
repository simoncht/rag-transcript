"""
RAG Evaluation Service — retrieval and answer quality metrics.

Provides:
- Recall@K, NDCG@K, MRR for retrieval quality
- LLM-as-judge for answer faithfulness, relevance, completeness
- Golden dataset loading and evaluation runner
"""
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GoldenQuery:
    """A single evaluation query with expected results."""

    id: str
    query: str
    intent: str  # precision, coverage, hybrid, conceptual
    expected_chunk_ids: List[str]
    expected_video_ids: List[str]
    expected_answer_contains: List[str] = field(default_factory=list)
    difficulty: str = "medium"
    tags: List[str] = field(default_factory=list)


@dataclass
class GoldenDataset:
    """Collection of golden queries for evaluation."""

    version: str
    queries: List[GoldenQuery]

    @classmethod
    def from_file(cls, path: str) -> "GoldenDataset":
        with open(path, "r") as f:
            data = json.load(f)
        queries = [GoldenQuery(**q) for q in data["queries"]]
        return cls(version=data.get("version", "1.0"), queries=queries)

    def filter_by_tags(self, tags: List[str]) -> "GoldenDataset":
        filtered = [q for q in self.queries if any(t in q.tags for t in tags)]
        return GoldenDataset(version=self.version, queries=filtered)

    def filter_by_difficulty(self, difficulty: str) -> "GoldenDataset":
        filtered = [q for q in self.queries if q.difficulty == difficulty]
        return GoldenDataset(version=self.version, queries=filtered)


@dataclass
class RetrievalMetrics:
    """Metrics for a single query's retrieval results."""

    query_id: str
    recall_at_k: float
    ndcg_at_k: float
    mrr: float
    retrieved_count: int
    relevant_found: int
    k: int


@dataclass
class AnswerQuality:
    """LLM-judged answer quality scores."""

    faithfulness: float  # 0-1: does answer stay faithful to context?
    relevance: float  # 0-1: does answer address the query?
    completeness: float  # 0-1: does answer cover all expected points?
    overall: float  # average of above


@dataclass
class QueryResult:
    """Full evaluation result for a single query."""

    query_id: str
    query: str
    retrieval: RetrievalMetrics
    answer_quality: Optional[AnswerQuality] = None
    retrieved_ids: List[str] = field(default_factory=list)
    answer: str = ""
    error: Optional[str] = None


@dataclass
class EvaluationReport:
    """Aggregate evaluation report."""

    dataset_version: str
    total_queries: int
    results: List[QueryResult]
    avg_recall_at_k: float = 0.0
    avg_ndcg_at_k: float = 0.0
    avg_mrr: float = 0.0
    avg_faithfulness: float = 0.0
    avg_relevance: float = 0.0
    avg_completeness: float = 0.0
    k: int = 10

    def compute_aggregates(self) -> None:
        if not self.results:
            return
        n = len(self.results)
        self.avg_recall_at_k = sum(r.retrieval.recall_at_k for r in self.results) / n
        self.avg_ndcg_at_k = sum(r.retrieval.ndcg_at_k for r in self.results) / n
        self.avg_mrr = sum(r.retrieval.mrr for r in self.results) / n

        quality_results = [r for r in self.results if r.answer_quality]
        if quality_results:
            nq = len(quality_results)
            self.avg_faithfulness = (
                sum(r.answer_quality.faithfulness for r in quality_results) / nq
            )
            self.avg_relevance = (
                sum(r.answer_quality.relevance for r in quality_results) / nq
            )
            self.avg_completeness = (
                sum(r.answer_quality.completeness for r in quality_results) / nq
            )

    def to_dict(self) -> Dict[str, Any]:
        self.compute_aggregates()
        return {
            "dataset_version": self.dataset_version,
            "total_queries": self.total_queries,
            "k": self.k,
            "retrieval": {
                "avg_recall_at_k": round(self.avg_recall_at_k, 4),
                "avg_ndcg_at_k": round(self.avg_ndcg_at_k, 4),
                "avg_mrr": round(self.avg_mrr, 4),
            },
            "answer_quality": {
                "avg_faithfulness": round(self.avg_faithfulness, 4),
                "avg_relevance": round(self.avg_relevance, 4),
                "avg_completeness": round(self.avg_completeness, 4),
            },
            "per_query": [
                {
                    "id": r.query_id,
                    "query": r.query,
                    "recall": round(r.retrieval.recall_at_k, 4),
                    "ndcg": round(r.retrieval.ndcg_at_k, 4),
                    "mrr": round(r.retrieval.mrr, 4),
                    "retrieved": r.retrieval.retrieved_count,
                    "relevant_found": r.retrieval.relevant_found,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class EvaluationService:
    """
    Computes retrieval and answer quality metrics.

    Usage:
        svc = EvaluationService()
        recall = svc.compute_recall_at_k(retrieved, relevant, k=10)
        ndcg = svc.compute_ndcg_at_k(retrieved, relevant, k=10)
        mrr = svc.compute_mrr(retrieved, relevant)
    """

    def __init__(self, llm_service: Optional[Any] = None):
        self.llm_service = llm_service

    def compute_recall_at_k(
        self,
        retrieved_ids: Sequence[str],
        relevant_ids: Sequence[str],
        k: int = 10,
    ) -> float:
        """
        Recall@K: fraction of relevant items found in top-K retrieved.

        Args:
            retrieved_ids: ordered list of retrieved chunk IDs
            relevant_ids: set of ground-truth relevant chunk IDs
            k: cutoff

        Returns:
            float between 0.0 and 1.0
        """
        if not relevant_ids:
            return 1.0 if not retrieved_ids else 0.0

        relevant_set = set(relevant_ids)
        top_k = list(retrieved_ids)[:k]
        found = sum(1 for rid in top_k if rid in relevant_set)
        return found / len(relevant_set)

    def compute_ndcg_at_k(
        self,
        retrieved_ids: Sequence[str],
        relevant_ids: Sequence[str],
        k: int = 10,
    ) -> float:
        """
        Normalized Discounted Cumulative Gain at K.

        Binary relevance: 1 if in relevant set, 0 otherwise.
        """
        if not relevant_ids:
            return 1.0 if not retrieved_ids else 0.0

        relevant_set = set(relevant_ids)
        top_k = list(retrieved_ids)[:k]

        # DCG
        dcg = 0.0
        for i, rid in enumerate(top_k):
            if rid in relevant_set:
                dcg += 1.0 / math.log2(i + 2)  # i+2 because rank is 1-indexed

        # Ideal DCG: all relevant items at top positions
        ideal_k = min(len(relevant_set), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))

        if idcg == 0:
            return 0.0
        return dcg / idcg

    def compute_mrr(
        self,
        retrieved_ids: Sequence[str],
        relevant_ids: Sequence[str],
    ) -> float:
        """
        Mean Reciprocal Rank: 1/rank of first relevant result.

        Returns 0.0 if no relevant result found.
        """
        if not relevant_ids:
            return 1.0 if not retrieved_ids else 0.0

        relevant_set = set(relevant_ids)
        for i, rid in enumerate(retrieved_ids):
            if rid in relevant_set:
                return 1.0 / (i + 1)
        return 0.0

    def evaluate_retrieval(
        self,
        golden_dataset: GoldenDataset,
        pipeline_fn: Callable[[str], List[str]],
        k: int = 10,
    ) -> EvaluationReport:
        """
        Run retrieval evaluation across all golden queries.

        Args:
            golden_dataset: golden queries with expected results
            pipeline_fn: function(query) -> list of retrieved chunk IDs
            k: cutoff for metrics

        Returns:
            EvaluationReport with per-query and aggregate metrics
        """
        results: List[QueryResult] = []

        for gq in golden_dataset.queries:
            try:
                retrieved_ids = pipeline_fn(gq.query)
                retrieved_str = [str(rid) for rid in retrieved_ids]

                metrics = RetrievalMetrics(
                    query_id=gq.id,
                    recall_at_k=self.compute_recall_at_k(
                        retrieved_str, gq.expected_chunk_ids, k
                    ),
                    ndcg_at_k=self.compute_ndcg_at_k(
                        retrieved_str, gq.expected_chunk_ids, k
                    ),
                    mrr=self.compute_mrr(retrieved_str, gq.expected_chunk_ids),
                    retrieved_count=len(retrieved_str),
                    relevant_found=len(
                        set(retrieved_str[:k]) & set(gq.expected_chunk_ids)
                    ),
                    k=k,
                )

                results.append(
                    QueryResult(
                        query_id=gq.id,
                        query=gq.query,
                        retrieval=metrics,
                        retrieved_ids=retrieved_str[:k],
                    )
                )
            except Exception as e:
                logger.error(f"Evaluation failed for query {gq.id}: {e}")
                results.append(
                    QueryResult(
                        query_id=gq.id,
                        query=gq.query,
                        retrieval=RetrievalMetrics(
                            query_id=gq.id,
                            recall_at_k=0.0,
                            ndcg_at_k=0.0,
                            mrr=0.0,
                            retrieved_count=0,
                            relevant_found=0,
                            k=k,
                        ),
                        error=str(e),
                    )
                )

        report = EvaluationReport(
            dataset_version=golden_dataset.version,
            total_queries=len(golden_dataset.queries),
            results=results,
            k=k,
        )
        report.compute_aggregates()
        return report

    def evaluate_answer_quality(
        self,
        query: str,
        answer: str,
        context: str,
        reference_keywords: List[str],
    ) -> AnswerQuality:
        """
        LLM-as-judge: rate answer faithfulness, relevance, completeness.

        Args:
            query: the user query
            answer: the generated answer
            context: the retrieved context chunks
            reference_keywords: expected keywords/phrases in the answer

        Returns:
            AnswerQuality with scores 0-1
        """
        if not self.llm_service:
            # Keyword-based fallback when no LLM available
            return self._keyword_based_quality(answer, reference_keywords)

        try:
            from app.services.llm_providers import Message

            prompt = (
                "You are an expert evaluator of RAG system answers. "
                "Rate the following answer on three dimensions (0.0 to 1.0):\n\n"
                "1. **Faithfulness**: Does the answer only contain information supported by the context? "
                "(1.0 = fully faithful, 0.0 = hallucinated)\n"
                "2. **Relevance**: Does the answer address the query? "
                "(1.0 = directly answers, 0.0 = off-topic)\n"
                "3. **Completeness**: Does the answer cover the key points? "
                f"Expected keywords: {', '.join(reference_keywords)}\n"
                "(1.0 = all points covered, 0.0 = missing everything)\n\n"
                f"**Query:** {query}\n\n"
                f"**Context:**\n{context[:2000]}\n\n"
                f"**Answer:**\n{answer[:1000]}\n\n"
                "Return ONLY valid JSON: "
                '{"faithfulness": 0.X, "relevance": 0.X, "completeness": 0.X}'
            )

            messages = [Message(role="user", content=prompt)]
            response = self.llm_service.complete(
                messages=messages, temperature=0.1, max_tokens=100
            )

            scores = json.loads(response.content.strip())
            faithfulness = max(0.0, min(1.0, float(scores.get("faithfulness", 0))))
            relevance = max(0.0, min(1.0, float(scores.get("relevance", 0))))
            completeness = max(0.0, min(1.0, float(scores.get("completeness", 0))))

            return AnswerQuality(
                faithfulness=faithfulness,
                relevance=relevance,
                completeness=completeness,
                overall=(faithfulness + relevance + completeness) / 3,
            )
        except Exception as e:
            logger.warning(f"LLM-as-judge failed: {e}, falling back to keyword check")
            return self._keyword_based_quality(answer, reference_keywords)

    def _keyword_based_quality(
        self, answer: str, reference_keywords: List[str]
    ) -> AnswerQuality:
        """Fallback quality check using keyword matching."""
        if not reference_keywords:
            return AnswerQuality(
                faithfulness=0.5, relevance=0.5, completeness=0.5, overall=0.5
            )

        answer_lower = answer.lower()
        found = sum(1 for kw in reference_keywords if kw.lower() in answer_lower)
        completeness = found / len(reference_keywords)

        return AnswerQuality(
            faithfulness=0.5,  # can't judge without context
            relevance=0.5 if answer.strip() else 0.0,
            completeness=completeness,
            overall=(0.5 + 0.5 + completeness) / 3 if answer.strip() else 0.0,
        )


def compare_reports(
    baseline: Dict[str, Any], current: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare two evaluation reports and return deltas.

    Args:
        baseline: baseline report dict (from EvaluationReport.to_dict())
        current: current report dict

    Returns:
        Dict with metric deltas and improvement indicators
    """
    deltas = {}
    for section in ["retrieval", "answer_quality"]:
        base_section = baseline.get(section, {})
        curr_section = current.get(section, {})
        deltas[section] = {}
        for key in base_section:
            base_val = base_section.get(key, 0.0)
            curr_val = curr_section.get(key, 0.0)
            delta = curr_val - base_val
            deltas[section][key] = {
                "baseline": round(base_val, 4),
                "current": round(curr_val, 4),
                "delta": round(delta, 4),
                "improved": delta > 0.005,  # 0.5% threshold
                "regressed": delta < -0.005,
            }

    return deltas


# Global instance
_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    """Get or create global evaluation service instance."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
