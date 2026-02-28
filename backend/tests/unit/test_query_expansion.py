"""
Tests for query expansion gating — short queries skip the LLM call.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock external dependencies before any app imports
for _mod in ["openai", "openai.types", "openai.types.chat", "anthropic", "httpx"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Mock the llm_providers module to avoid DeepSeek API key validation
_mock_llm_module = MagicMock()
sys.modules["app.services.llm_providers"] = _mock_llm_module

from app.services.query_expansion import QueryExpansionService
import app.services.query_expansion as _qe_mod


class TestExpandQueryGating:
    """Tests that short/simple queries bypass the LLM expansion call."""

    def _make_service(self, enabled=True, min_words=6, variants=2):
        """Create a QueryExpansionService with mocked settings and LLM.

        Returns (service, llm, patcher) — caller must call patcher.stop() or
        use the returned service within the patched context.
        """
        mock_settings = MagicMock()
        mock_settings.enable_query_expansion = enabled
        mock_settings.query_expansion_min_words = min_words
        mock_settings.query_expansion_variants = variants

        patcher = patch.object(_qe_mod, "settings", mock_settings)
        patcher.start()

        llm = MagicMock()
        service = QueryExpansionService(llm_service=llm)
        service.enabled = enabled
        # Stop the patcher after the test method is done — rely on teardown
        self._patcher = patcher
        return service, llm

    def teardown_method(self):
        if hasattr(self, "_patcher"):
            self._patcher.stop()

    def test_short_query_skips_expansion(self):
        service, llm = self._make_service()
        result = service.expand_query("yes please")
        assert result == ["yes please"]
        llm.complete.assert_not_called()

    def test_medium_query_skips_expansion(self):
        service, llm = self._make_service()
        result = service.expand_query("what about the pricing?")
        assert result == ["what about the pricing?"]
        llm.complete.assert_not_called()

    def test_threshold_query_expands(self):
        """A 7+ word query should trigger LLM expansion."""
        service, llm = self._make_service()
        llm.complete.return_value = MagicMock(
            content="How does the system handle video indexing?\nWhat is the video processing pipeline?"
        )

        query = "how does the system handle video indexing"
        result = service.expand_query(query)
        assert len(result) >= 2
        assert result[0] == query
        llm.complete.assert_called_once()

    def test_long_query_expands(self):
        service, llm = self._make_service()
        llm.complete.return_value = MagicMock(
            content="1. Variant one of the long query\n2. Variant two of the long query"
        )

        query = "can you explain how the RAG pipeline processes and indexes video transcripts for retrieval"
        result = service.expand_query(query)
        assert len(result) >= 2
        assert result[0] == query
        llm.complete.assert_called_once()

    def test_disabled_always_skips(self):
        service, llm = self._make_service(enabled=False)

        query = "this is a very long query that would normally trigger expansion in the system"
        result = service.expand_query(query)
        assert result == [query]
        llm.complete.assert_not_called()

    def test_config_threshold_respected(self):
        """Custom min_words=3 should gate at 3 words."""
        service, llm = self._make_service(min_words=3)

        result = service.expand_query("tell me more")
        assert result == ["tell me more"]
        llm.complete.assert_not_called()

        llm.complete.return_value = MagicMock(content="Variant query here")
        result = service.expand_query("tell me much more")
        assert len(result) >= 1
        llm.complete.assert_called_once()

    def test_single_word_skips(self):
        service, llm = self._make_service()
        result = service.expand_query("yes")
        assert result == ["yes"]
        llm.complete.assert_not_called()

    def test_exact_threshold_skips(self):
        """Query with exactly min_words words should be skipped (<=)."""
        service, llm = self._make_service(min_words=6)
        result = service.expand_query("one two three four five six")
        assert result == ["one two three four five six"]
        llm.complete.assert_not_called()

    def test_one_above_threshold_expands(self):
        """Query with min_words+1 words should trigger expansion."""
        service, llm = self._make_service(min_words=6)
        llm.complete.return_value = MagicMock(content="A variant query")
        result = service.expand_query("one two three four five six seven")
        assert len(result) >= 1
        llm.complete.assert_called_once()
