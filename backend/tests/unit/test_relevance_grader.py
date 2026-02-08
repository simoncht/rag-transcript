"""Unit tests for Self-RAG relevance grader service."""
import json
import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from app.services.relevance_grader import (
    RelevanceGraderService,
    RelevanceGrade,
    CorrectiveAction,
    GradedChunk,
    GradingResult,
)


@dataclass
class FakeChunk:
    text: str
    score: float = 0.8


@pytest.fixture
def disabled_grader():
    """Grader with relevance grading disabled."""
    with patch("app.services.relevance_grader.settings") as mock_settings:
        mock_settings.enable_relevance_grading = False
        return RelevanceGraderService()


@pytest.fixture
def enabled_grader():
    """Grader with relevance grading enabled and mocked LLM."""
    with patch("app.services.relevance_grader.settings") as mock_settings:
        mock_settings.enable_relevance_grading = True
        grader = RelevanceGraderService()
        grader.enabled = True
        return grader


class TestDisabledGrader:
    def test_passthrough_when_disabled(self, disabled_grader):
        chunks = [FakeChunk("hello"), FakeChunk("world")]
        result = disabled_grader.grade_chunks("test query", chunks)
        assert result.relevant_count == 2
        assert result.relevance_ratio == 1.0
        assert result.corrective_action == CorrectiveAction.NONE

    def test_empty_chunks(self, disabled_grader):
        result = disabled_grader.grade_chunks("test", [])
        assert result.relevant_count == 0
        assert result.corrective_action == CorrectiveAction.NONE


class TestEnabledGrader:
    def test_all_relevant(self, enabled_grader):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"grade": "RELEVANT"},
            {"grade": "RELEVANT"},
            {"grade": "RELEVANT"},
        ])
        mock_llm.complete.return_value = mock_response
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a"), FakeChunk("b"), FakeChunk("c")]
        result = enabled_grader.grade_chunks("test query", chunks)

        assert result.relevant_count == 3
        assert result.relevance_ratio == 1.0
        assert result.corrective_action == CorrectiveAction.NONE

    def test_mixed_grades(self, enabled_grader):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"grade": "RELEVANT"},
            {"grade": "IRRELEVANT"},
            {"grade": "PARTIALLY_RELEVANT"},
            {"grade": "IRRELEVANT"},
        ])
        mock_llm.complete.return_value = mock_response
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a"), FakeChunk("b"), FakeChunk("c"), FakeChunk("d")]
        result = enabled_grader.grade_chunks("test query", chunks)

        assert result.relevant_count == 1
        assert result.partial_count == 1
        assert result.irrelevant_count == 2
        assert result.relevance_ratio == 0.25  # 1/4

    def test_reformulate_action(self, enabled_grader):
        """When 25-50% relevant, should try reformulation."""
        mock_llm = MagicMock()

        # First call: grading (1 relevant out of 4 = 25%)
        grade_response = MagicMock()
        grade_response.content = json.dumps([
            {"grade": "RELEVANT"},
            {"grade": "IRRELEVANT"},
            {"grade": "IRRELEVANT"},
            {"grade": "IRRELEVANT"},
        ])

        # Second call: reformulation
        reform_response = MagicMock()
        reform_response.content = "What specific aspects of machine learning were discussed?"

        mock_llm.complete.side_effect = [grade_response, reform_response]
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a"), FakeChunk("b"), FakeChunk("c"), FakeChunk("d")]
        result = enabled_grader.grade_chunks("test query", chunks)

        assert result.corrective_action == CorrectiveAction.REFORMULATE
        assert result.reformulated_query is not None

    def test_insufficient_action(self, enabled_grader):
        """When 0% relevant, should flag as insufficient."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"grade": "IRRELEVANT"},
            {"grade": "IRRELEVANT"},
        ])
        mock_llm.complete.return_value = mock_response
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a"), FakeChunk("b")]
        result = enabled_grader.grade_chunks("test", chunks)

        assert result.corrective_action == CorrectiveAction.INSUFFICIENT
        assert result.relevance_ratio == 0.0

    def test_llm_failure_treated_as_all_relevant(self, enabled_grader):
        """When LLM fails, should gracefully degrade."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = RuntimeError("LLM unavailable")
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a"), FakeChunk("b")]
        result = enabled_grader.grade_chunks("test", chunks)

        assert result.relevant_count == 2
        assert result.corrective_action == CorrectiveAction.NONE

    def test_malformed_json_treated_as_relevant(self, enabled_grader):
        """When LLM returns bad JSON, should gracefully degrade."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "not valid json"
        mock_llm.complete.return_value = mock_response
        enabled_grader.llm_service = mock_llm

        chunks = [FakeChunk("a")]
        result = enabled_grader.grade_chunks("test", chunks)

        assert result.relevant_count == 1


class TestFilterRelevant:
    def test_filters_irrelevant(self):
        grader = RelevanceGraderService()
        result = GradingResult(
            graded_chunks=[
                GradedChunk(chunk=FakeChunk("keep"), grade=RelevanceGrade.RELEVANT),
                GradedChunk(chunk=FakeChunk("drop"), grade=RelevanceGrade.IRRELEVANT),
                GradedChunk(chunk=FakeChunk("keep2"), grade=RelevanceGrade.PARTIALLY_RELEVANT),
            ],
            relevant_count=1,
            partial_count=1,
            irrelevant_count=1,
            relevance_ratio=0.33,
            corrective_action=CorrectiveAction.NONE,
        )
        filtered = grader.filter_relevant(result)
        assert len(filtered) == 2
        assert filtered[0].text == "keep"
        assert filtered[1].text == "keep2"


class TestGradingResult:
    def test_has_sufficient_context(self):
        result = GradingResult(
            graded_chunks=[],
            relevant_count=3,
            partial_count=0,
            irrelevant_count=2,
            relevance_ratio=0.6,
            corrective_action=CorrectiveAction.NONE,
        )
        assert result.has_sufficient_context is True

    def test_insufficient_context(self):
        result = GradingResult(
            graded_chunks=[],
            relevant_count=1,
            partial_count=0,
            irrelevant_count=4,
            relevance_ratio=0.2,
            corrective_action=CorrectiveAction.EXPAND_SCOPE,
        )
        assert result.has_sufficient_context is False
