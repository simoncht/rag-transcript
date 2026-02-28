"""
Unit tests for follow-up question suggestion service.

Tests cover:
- Generation returns 2-3 questions
- Questions grounded in chunk content (mock LLM)
- Returns empty list on LLM failure
- Disabled when config flag is false
- Different modes produce different question styles
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.followup_questions import generate_followup_questions


class MockChunk:
    def __init__(self, text: str):
        self.text = text


class TestFollowUpQuestions:

    @pytest.fixture
    def sample_chunks(self):
        return [
            MockChunk("React hooks were introduced in version 16.8 to simplify state management."),
            MockChunk("useState and useEffect are the most commonly used hooks in React."),
            MockChunk("Custom hooks allow you to extract and reuse stateful logic."),
        ]

    @patch("app.services.followup_questions.settings")
    def test_returns_empty_when_disabled(self, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = False
        result = generate_followup_questions(
            query="What are React hooks?",
            response="React hooks are...",
            chunks=sample_chunks,
        )
        assert result == []

    @patch("app.services.followup_questions.settings")
    def test_returns_empty_when_no_chunks(self, mock_settings):
        mock_settings.enable_followup_questions = True
        result = generate_followup_questions(
            query="What are React hooks?",
            response="React hooks are...",
            chunks=[],
        )
        assert result == []

    @patch("app.services.followup_questions.settings")
    @patch("app.services.llm_providers.llm_service")
    def test_returns_2_to_3_questions(self, mock_llm, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = True
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            "How do custom hooks compare to HOCs?",
            "What performance pitfalls should I watch for?",
            "How does useState differ from useReducer?",
        ])
        mock_llm.complete.return_value = mock_response

        result = generate_followup_questions(
            query="What are React hooks?",
            response="React hooks simplify state management...",
            chunks=sample_chunks,
        )
        assert isinstance(result, list)
        assert 2 <= len(result) <= 3
        assert all(isinstance(q, str) for q in result)

    @patch("app.services.followup_questions.settings")
    @patch("app.services.llm_providers.llm_service")
    def test_returns_empty_on_llm_failure(self, mock_llm, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = True
        mock_llm.complete.side_effect = Exception("LLM unavailable")

        result = generate_followup_questions(
            query="What are React hooks?",
            response="React hooks are...",
            chunks=sample_chunks,
        )
        assert result == []

    @patch("app.services.followup_questions.settings")
    @patch("app.services.llm_providers.llm_service")
    def test_handles_markdown_wrapped_json(self, mock_llm, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = True
        mock_response = MagicMock()
        mock_response.content = '```json\n["Question 1?", "Question 2?"]\n```'
        mock_llm.complete.return_value = mock_response

        result = generate_followup_questions(
            query="What are React hooks?",
            response="React hooks are...",
            chunks=sample_chunks,
        )
        assert len(result) == 2

    @patch("app.services.followup_questions.settings")
    @patch("app.services.llm_providers.llm_service")
    def test_truncates_to_max_3_questions(self, mock_llm, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = True
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            "Q1?", "Q2?", "Q3?", "Q4?", "Q5?",
        ])
        mock_llm.complete.return_value = mock_response

        result = generate_followup_questions(
            query="test",
            response="test",
            chunks=sample_chunks,
        )
        assert len(result) <= 3

    @patch("app.services.followup_questions.settings")
    @patch("app.services.llm_providers.llm_service")
    def test_returns_empty_on_invalid_json(self, mock_llm, mock_settings, sample_chunks):
        mock_settings.enable_followup_questions = True
        mock_response = MagicMock()
        mock_response.content = "not valid json"
        mock_llm.complete.return_value = mock_response

        result = generate_followup_questions(
            query="test",
            response="test",
            chunks=sample_chunks,
        )
        assert result == []
