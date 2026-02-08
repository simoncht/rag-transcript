"""Unit tests for the evaluation service — metric math correctness."""
import json
import math
import pytest
from unittest.mock import MagicMock, patch

from app.services.evaluation import (
    EvaluationService,
    GoldenDataset,
    GoldenQuery,
    AnswerQuality,
    compare_reports,
)


@pytest.fixture
def svc():
    return EvaluationService()


# ── Recall@K ──────────────────────────────────────────────────────────

class TestRecallAtK:
    def test_perfect_recall(self, svc):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b", "c"]
        assert svc.compute_recall_at_k(retrieved, relevant, k=10) == 1.0

    def test_zero_recall(self, svc):
        retrieved = ["x", "y", "z"]
        relevant = ["a", "b", "c"]
        assert svc.compute_recall_at_k(retrieved, relevant, k=10) == 0.0

    def test_partial_recall(self, svc):
        retrieved = ["a", "x", "b", "y"]
        relevant = ["a", "b", "c"]
        assert svc.compute_recall_at_k(retrieved, relevant, k=10) == pytest.approx(
            2 / 3
        )

    def test_k_cutoff(self, svc):
        retrieved = ["x", "y", "a", "b"]
        relevant = ["a", "b"]
        # Only look at top 2 → neither a nor b is there
        assert svc.compute_recall_at_k(retrieved, relevant, k=2) == 0.0
        # Top 4 → both found
        assert svc.compute_recall_at_k(retrieved, relevant, k=4) == 1.0

    def test_empty_relevant(self, svc):
        assert svc.compute_recall_at_k(["a"], [], k=10) == 0.0

    def test_empty_retrieved(self, svc):
        assert svc.compute_recall_at_k([], ["a"], k=10) == 0.0

    def test_both_empty(self, svc):
        assert svc.compute_recall_at_k([], [], k=10) == 1.0


# ── NDCG@K ────────────────────────────────────────────────────────────

class TestNDCGAtK:
    def test_perfect_order(self, svc):
        """All relevant items at the top → NDCG = 1.0"""
        retrieved = ["a", "b", "c", "x"]
        relevant = ["a", "b", "c"]
        assert svc.compute_ndcg_at_k(retrieved, relevant, k=10) == pytest.approx(1.0)

    def test_reversed_order(self, svc):
        """Relevant items at the end → NDCG < 1.0"""
        retrieved = ["x", "y", "z", "a"]
        relevant = ["a"]
        ndcg = svc.compute_ndcg_at_k(retrieved, relevant, k=10)
        # a is at rank 4 → DCG = 1/log2(5), IDCG = 1/log2(2) = 1.0
        expected = (1 / math.log2(5)) / (1 / math.log2(2))
        assert ndcg == pytest.approx(expected, abs=0.001)

    def test_zero_ndcg(self, svc):
        retrieved = ["x", "y", "z"]
        relevant = ["a", "b"]
        assert svc.compute_ndcg_at_k(retrieved, relevant, k=3) == 0.0

    def test_single_relevant(self, svc):
        retrieved = ["a"]
        relevant = ["a"]
        assert svc.compute_ndcg_at_k(retrieved, relevant, k=1) == pytest.approx(1.0)

    def test_empty_relevant(self, svc):
        assert svc.compute_ndcg_at_k(["a"], [], k=10) == 0.0


# ── MRR ───────────────────────────────────────────────────────────────

class TestMRR:
    def test_first_position(self, svc):
        assert svc.compute_mrr(["a", "b"], ["a"]) == 1.0

    def test_second_position(self, svc):
        assert svc.compute_mrr(["x", "a"], ["a"]) == pytest.approx(0.5)

    def test_third_position(self, svc):
        assert svc.compute_mrr(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)

    def test_not_found(self, svc):
        assert svc.compute_mrr(["x", "y", "z"], ["a"]) == 0.0

    def test_multiple_relevant_first_matters(self, svc):
        assert svc.compute_mrr(["x", "a", "b"], ["a", "b"]) == pytest.approx(0.5)

    def test_empty_retrieved(self, svc):
        assert svc.compute_mrr([], ["a"]) == 0.0


# ── evaluate_retrieval ────────────────────────────────────────────────

class TestEvaluateRetrieval:
    def test_full_pipeline(self, svc):
        dataset = GoldenDataset(
            version="test",
            queries=[
                GoldenQuery(
                    id="q1",
                    query="test query",
                    intent="precision",
                    expected_chunk_ids=["a", "b"],
                    expected_video_ids=["v1"],
                ),
            ],
        )

        def mock_pipeline(query: str):
            return ["a", "x", "b"]

        report = svc.evaluate_retrieval(dataset, mock_pipeline, k=10)
        assert report.total_queries == 1
        assert len(report.results) == 1
        assert report.avg_recall_at_k == 1.0
        assert report.avg_mrr == 1.0

    def test_pipeline_error_handled(self, svc):
        dataset = GoldenDataset(
            version="test",
            queries=[
                GoldenQuery(
                    id="q1",
                    query="bad query",
                    intent="precision",
                    expected_chunk_ids=["a"],
                    expected_video_ids=["v1"],
                ),
            ],
        )

        def failing_pipeline(query: str):
            raise RuntimeError("boom")

        report = svc.evaluate_retrieval(dataset, failing_pipeline, k=10)
        assert report.results[0].error == "boom"
        assert report.results[0].retrieval.recall_at_k == 0.0


# ── Answer Quality ────────────────────────────────────────────────────

class TestAnswerQuality:
    def test_keyword_fallback(self, svc):
        quality = svc.evaluate_answer_quality(
            query="What is ML?",
            answer="Machine learning is a subset of AI",
            context="Machine learning uses data to learn patterns",
            reference_keywords=["machine learning", "AI", "missing"],
        )
        assert quality.completeness == pytest.approx(2 / 3)
        assert quality.faithfulness == 0.5  # can't judge without LLM
        assert 0.0 <= quality.overall <= 1.0

    def test_empty_answer(self, svc):
        quality = svc.evaluate_answer_quality(
            query="test",
            answer="",
            context="ctx",
            reference_keywords=["kw"],
        )
        assert quality.overall == 0.0


# ── compare_reports ───────────────────────────────────────────────────

class TestCompareReports:
    def test_improvement_detected(self):
        baseline = {
            "retrieval": {"avg_recall_at_k": 0.5, "avg_ndcg_at_k": 0.4, "avg_mrr": 0.3},
            "answer_quality": {"avg_faithfulness": 0.6, "avg_relevance": 0.5, "avg_completeness": 0.4},
        }
        current = {
            "retrieval": {"avg_recall_at_k": 0.7, "avg_ndcg_at_k": 0.6, "avg_mrr": 0.5},
            "answer_quality": {"avg_faithfulness": 0.8, "avg_relevance": 0.7, "avg_completeness": 0.6},
        }
        deltas = compare_reports(baseline, current)
        assert deltas["retrieval"]["avg_recall_at_k"]["improved"] is True
        assert deltas["retrieval"]["avg_recall_at_k"]["delta"] == pytest.approx(0.2)

    def test_regression_detected(self):
        baseline = {
            "retrieval": {"avg_recall_at_k": 0.8},
            "answer_quality": {},
        }
        current = {
            "retrieval": {"avg_recall_at_k": 0.5},
            "answer_quality": {},
        }
        deltas = compare_reports(baseline, current)
        assert deltas["retrieval"]["avg_recall_at_k"]["regressed"] is True


# ── GoldenDataset ─────────────────────────────────────────────────────

class TestGoldenDataset:
    def test_filter_by_tags(self):
        ds = GoldenDataset(
            version="1.0",
            queries=[
                GoldenQuery(id="q1", query="q", intent="p", expected_chunk_ids=[], expected_video_ids=[], tags=["single-video"]),
                GoldenQuery(id="q2", query="q", intent="c", expected_chunk_ids=[], expected_video_ids=[], tags=["multi-video"]),
            ],
        )
        filtered = ds.filter_by_tags(["single-video"])
        assert len(filtered.queries) == 1
        assert filtered.queries[0].id == "q1"

    def test_filter_by_difficulty(self):
        ds = GoldenDataset(
            version="1.0",
            queries=[
                GoldenQuery(id="q1", query="q", intent="p", expected_chunk_ids=[], expected_video_ids=[], difficulty="easy"),
                GoldenQuery(id="q2", query="q", intent="c", expected_chunk_ids=[], expected_video_ids=[], difficulty="hard"),
            ],
        )
        filtered = ds.filter_by_difficulty("easy")
        assert len(filtered.queries) == 1
