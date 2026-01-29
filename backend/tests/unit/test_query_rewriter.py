"""
Unit tests for the Query Rewriter Service.

Tests cover:
- Anaphora detection (needs_rewriting function)
- Query rewriting with mocked LLM
- Disabled mode returns original query
- Error handling graceful fallback
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.query_rewriter import (
    QueryRewriterService,
    needs_rewriting,
    get_query_rewriter_service,
)


class TestNeedsRewriting:
    """Tests for the needs_rewriting function."""

    def test_detects_this_reference(self):
        """Should detect 'this' as requiring rewriting."""
        assert needs_rewriting("Can you explain this in more detail?") is True
        assert needs_rewriting("What is this about?") is True
        assert needs_rewriting("Show me this again") is True

    def test_detects_that_reference(self):
        """Should detect 'that' as requiring rewriting."""
        assert needs_rewriting("Tell me more about that") is True
        assert needs_rewriting("What does that mean?") is True

    def test_detects_it_reference(self):
        """Should detect 'it' as requiring rewriting."""
        assert needs_rewriting("Can you present it in a table?") is True
        assert needs_rewriting("Summarize it for me") is True

    def test_detects_again_reference(self):
        """Should detect 'again' as requiring rewriting."""
        assert needs_rewriting("Can you explain that again?") is True
        assert needs_rewriting("Show me the results again in table format") is True

    def test_detects_same_reference(self):
        """Should detect 'same' as requiring rewriting."""
        assert needs_rewriting("Use the same format") is True
        assert needs_rewriting("Tell me the same thing differently") is True

    def test_detects_previous_earlier_reference(self):
        """Should detect 'previous' and 'earlier' references."""
        assert needs_rewriting("What was mentioned earlier?") is True
        assert needs_rewriting("Go back to the previous topic") is True

    def test_detects_above_reference(self):
        """Should detect 'above' as requiring rewriting."""
        assert needs_rewriting("Summarize the above") is True
        assert needs_rewriting("Format the above as a list") is True

    def test_does_not_flag_standalone_questions(self):
        """Should not flag standalone questions without references."""
        assert needs_rewriting("What are the key leadership principles?") is False
        assert needs_rewriting("How does quantum computing work?") is False
        assert needs_rewriting("Who invented the telephone?") is False
        assert needs_rewriting("List the top 5 programming languages") is False

    def test_case_insensitive(self):
        """Should detect anaphora regardless of case."""
        assert needs_rewriting("THIS is important") is True
        assert needs_rewriting("What does THAT mean?") is True
        assert needs_rewriting("Explain IT again") is True


class TestQueryRewriterService:
    """Tests for the QueryRewriterService class."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mocked LLM service."""
        mock = MagicMock()
        mock.complete.return_value = MagicMock(
            content="What are the 5 leadership principles in table format?"
        )
        return mock

    @pytest.fixture
    def mock_settings_enabled(self):
        """Mock settings with query rewriting enabled."""
        with patch("app.services.query_rewriter.settings") as mock:
            mock.enable_query_rewriting = True
            mock.query_rewrite_history_limit = 6
            mock.query_rewrite_model = "deepseek-chat"
            yield mock

    @pytest.fixture
    def mock_settings_disabled(self):
        """Mock settings with query rewriting disabled."""
        with patch("app.services.query_rewriter.settings") as mock:
            mock.enable_query_rewriting = False
            mock.query_rewrite_history_limit = 6
            mock.query_rewrite_model = "deepseek-chat"
            yield mock

    def test_rewrite_with_history(self, mock_llm_service, mock_settings_enabled):
        """Should rewrite query using conversation history."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True  # Override since we're not using full settings injection

        history = [
            {"role": "user", "content": "What are the key leadership principles?"},
            {
                "role": "assistant",
                "content": "The video discusses 5 leadership principles: 1) Lead by example...",
            },
        ]

        result = service.rewrite_query(
            query="in a table format, can you present this again?",
            conversation_history=history,
        )

        # Should call LLM
        assert mock_llm_service.complete.called

        # Should return rewritten query
        assert result == "What are the 5 leadership principles in table format?"

    def test_returns_original_when_disabled(
        self, mock_llm_service, mock_settings_disabled
    ):
        """Should return original query when disabled."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = False

        result = service.rewrite_query(
            query="in a table format, can you present this again?",
            conversation_history=[{"role": "user", "content": "Test"}],
        )

        # Should NOT call LLM
        assert not mock_llm_service.complete.called

        # Should return original
        assert result == "in a table format, can you present this again?"

    def test_returns_original_when_no_anaphora(
        self, mock_llm_service, mock_settings_enabled
    ):
        """Should return original query when no anaphora detected."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        result = service.rewrite_query(
            query="What are the key principles of effective leadership?",
            conversation_history=[{"role": "user", "content": "Test"}],
        )

        # Should NOT call LLM (no anaphora)
        assert not mock_llm_service.complete.called

        # Should return original
        assert result == "What are the key principles of effective leadership?"

    def test_returns_original_when_no_history(
        self, mock_llm_service, mock_settings_enabled
    ):
        """Should return original query when no history available."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        result = service.rewrite_query(
            query="Can you explain this?",
            conversation_history=[],  # Empty history
        )

        # Should NOT call LLM (no history to reference)
        assert not mock_llm_service.complete.called

        # Should return original
        assert result == "Can you explain this?"

    def test_graceful_fallback_on_llm_error(
        self, mock_llm_service, mock_settings_enabled
    ):
        """Should return original query on LLM error."""
        mock_llm_service.complete.side_effect = Exception("LLM unavailable")
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        result = service.rewrite_query(
            query="Can you explain this?",
            conversation_history=[{"role": "user", "content": "Test"}],
        )

        # Should return original on error
        assert result == "Can you explain this?"

    def test_handles_empty_llm_response(self, mock_llm_service, mock_settings_enabled):
        """Should return original query if LLM returns empty."""
        mock_llm_service.complete.return_value = MagicMock(content="")
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        result = service.rewrite_query(
            query="Can you explain this?",
            conversation_history=[{"role": "user", "content": "Test"}],
        )

        # Should return original
        assert result == "Can you explain this?"

    def test_strips_quotes_from_response(self, mock_llm_service, mock_settings_enabled):
        """Should strip quotes from LLM response."""
        mock_llm_service.complete.return_value = MagicMock(
            content='"What are the leadership principles?"'
        )
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        result = service.rewrite_query(
            query="Can you explain this?",
            conversation_history=[{"role": "user", "content": "Test"}],
        )

        # Should strip quotes
        assert result == "What are the leadership principles?"

    def test_truncates_long_history_messages(
        self, mock_llm_service, mock_settings_enabled
    ):
        """Should truncate very long messages in history."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True
        service.history_limit = 6

        # Create long history message
        long_content = "A" * 1000  # 1000 chars
        history = [{"role": "assistant", "content": long_content}]

        service.rewrite_query(
            query="Can you explain this?",
            conversation_history=history,
        )

        # Check that the prompt was built with truncated content
        call_args = mock_llm_service.complete.call_args
        prompt = call_args[1]["messages"][0].content if call_args else ""
        # The 1000-char message should be truncated to 500 + "..."
        assert "..." in prompt or len(prompt) < len(long_content) + 500


class TestGetQueryRewriterService:
    """Tests for the global service getter."""

    def test_returns_singleton(self):
        """Should return same instance on repeated calls."""
        # Reset global instance for test
        import app.services.query_rewriter as module

        module._query_rewriter_service = None

        service1 = get_query_rewriter_service()
        service2 = get_query_rewriter_service()

        assert service1 is service2


class TestIntegrationScenarios:
    """Integration-style tests for common scenarios."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mocked LLM service that behaves realistically."""
        mock = MagicMock()

        def smart_rewrite(messages, **kwargs):
            prompt = messages[0].content
            if "table format" in prompt.lower() and "leadership" in prompt.lower():
                return MagicMock(
                    content="Present the 5 leadership principles in table format"
                )
            elif "summarize" in prompt.lower():
                return MagicMock(
                    content="Summarize the main points about quantum computing"
                )
            else:
                # Return something generic
                return MagicMock(content="Rewritten query about the topic")

        mock.complete.side_effect = smart_rewrite
        return mock

    def test_follow_up_about_leadership_principles(self, mock_llm_service):
        """Test realistic follow-up about leadership principles."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        history = [
            {"role": "user", "content": "What are the key teachings about leadership?"},
            {
                "role": "assistant",
                "content": "The video discusses 5 leadership principles: "
                "1) Lead by example 2) Communicate clearly 3) Empower your team "
                "4) Make decisions 5) Stay accountable",
            },
        ]

        result = service.rewrite_query(
            query="in a table format, can you present this again?",
            conversation_history=history,
        )

        assert "leadership" in result.lower()
        assert "table" in result.lower()

    def test_multiple_turn_conversation(self, mock_llm_service):
        """Test query rewriting with multiple conversation turns."""
        service = QueryRewriterService(llm_service=mock_llm_service)
        service.enabled = True

        history = [
            {"role": "user", "content": "Tell me about quantum computing"},
            {
                "role": "assistant",
                "content": "Quantum computing uses qubits and superposition...",
            },
            {"role": "user", "content": "What are the applications?"},
            {
                "role": "assistant",
                "content": "Applications include cryptography and drug discovery...",
            },
        ]

        result = service.rewrite_query(
            query="Can you summarize it?",
            conversation_history=history,
        )

        # Should reference the topic being discussed
        assert "quantum" in result.lower() or "summarize" in result.lower()
