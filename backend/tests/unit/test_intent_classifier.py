"""
Unit tests for the Intent Classifier Service.

Tests cover:
- Coverage query detection (summarize, overview, themes)
- Precision query detection (what did X say, find, specific)
- Hybrid query detection (summarize with quotes)
- Ambiguous query fallback to mode
- Follow-up query detection (tell me more, expand on that)
- Intent switch detection (now summarize, get specific)
- Regex fallback classification
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.intent_classifier import (
    IntentClassifier,
    QueryIntent,
    IntentClassification,
    get_intent_classifier,
)


class TestQueryIntentEnum:
    """Tests for QueryIntent enum."""

    def test_intent_values(self):
        """Should have correct string values."""
        assert QueryIntent.COVERAGE.value == "coverage"
        assert QueryIntent.PRECISION.value == "precision"
        assert QueryIntent.HYBRID.value == "hybrid"


class TestIntentClassification:
    """Tests for IntentClassification dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        classification = IntentClassification(
            intent=QueryIntent.COVERAGE,
            confidence=0.85,
            reasoning="Coverage patterns matched",
        )
        result = classification.to_dict()
        assert result == {
            "intent": "coverage",
            "confidence": 0.85,
            "reasoning": "Coverage patterns matched",
        }


class TestCoveragePatterns:
    """Tests for coverage pattern detection."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_detects_summarize(self, classifier):
        """Should detect summarize queries as coverage."""
        result = classifier.classify_sync(
            query="Summarize these videos",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE
        assert result.confidence > 0.5

    def test_detects_overview(self, classifier):
        """Should detect overview queries as coverage."""
        result = classifier.classify_sync(
            query="Give me an overview of the content",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_detects_main_points(self, classifier):
        """Should detect main points queries as coverage."""
        result = classifier.classify_sync(
            query="What are the main points?",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_detects_key_themes(self, classifier):
        """Should detect key themes queries as coverage."""
        result = classifier.classify_sync(
            query="What are the key themes across these videos?",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_detects_all_videos_reference(self, classifier):
        """Should detect 'all videos' reference as coverage."""
        result = classifier.classify_sync(
            query="What do all the videos discuss?",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_detects_compare_videos(self, classifier):
        """Should detect compare queries as coverage."""
        result = classifier.classify_sync(
            query="Compare the speakers across these videos",
            mode="compare_sources",
            num_videos=3,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_detects_tldr(self, classifier):
        """Should detect TL;DR queries as coverage."""
        result = classifier.classify_sync(
            query="TL;DR of these videos",
            mode="summarize",
            num_videos=3,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestPrecisionPatterns:
    """Tests for precision pattern detection."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_detects_what_did_say(self, classifier):
        """Should detect 'what did X say' as precision."""
        result = classifier.classify_sync(
            query="What did Ken Robinson say about creativity?",
            mode="deep_dive",
            num_videos=5,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_detects_find_specific(self, classifier):
        """Should detect 'find' queries as precision."""
        result = classifier.classify_sync(
            query="Find the part where they talk about procrastination",
            mode="deep_dive",
            num_videos=3,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_detects_why_questions(self, classifier):
        """Should detect 'why' questions as precision."""
        result = classifier.classify_sync(
            query="Why do schools kill creativity?",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_detects_quote_requests(self, classifier):
        """Should detect quote requests as precision."""
        result = classifier.classify_sync(
            query="Can you quote what they said about education?",
            mode="deep_dive",
            num_videos=5,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_detects_timestamp_requests(self, classifier):
        """Should detect timestamp requests as precision."""
        result = classifier.classify_sync(
            query="At what timestamp do they discuss innovation?",
            mode="deep_dive",
            num_videos=1,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_detects_who_said(self, classifier):
        """Should detect 'who said' as precision."""
        result = classifier.classify_sync(
            query="Who said mistakes are the essence of creativity?",
            mode="deep_dive",
            num_videos=5,
        )
        assert result.intent == QueryIntent.PRECISION


class TestHybridPatterns:
    """Tests for hybrid pattern detection."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_detects_summarize_with_quotes(self, classifier):
        """Should detect summarize with quotes as hybrid."""
        result = classifier.classify_sync(
            query="Summarize the videos and give me key quotes",
            mode="summarize",
            num_videos=5,
        )
        # Should be hybrid or have mixed signals
        assert result.intent in [QueryIntent.HYBRID, QueryIntent.COVERAGE]

    def test_detects_overview_with_examples(self, classifier):
        """Should detect overview with examples as hybrid."""
        result = classifier.classify_sync(
            query="Give me an overview with specific examples",
            mode="summarize",
            num_videos=5,
        )
        # Could be hybrid due to mixed signals
        assert result.intent in [QueryIntent.HYBRID, QueryIntent.COVERAGE]


class TestAmbiguousQueries:
    """Tests for ambiguous query handling."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_ambiguous_query_uses_mode_fallback_summarize(self, classifier):
        """Should fall back to mode when query is ambiguous."""
        result = classifier.classify_sync(
            query="Tell me about motivation",
            mode="summarize",
            num_videos=10,
        )
        # Should have low confidence and default based on mode
        assert result.confidence <= 0.7

    def test_ambiguous_query_uses_mode_fallback_deep_dive(self, classifier):
        """Should prefer precision for deep_dive mode when ambiguous."""
        result = classifier.classify_sync(
            query="Explain the concept",
            mode="deep_dive",
            num_videos=5,
        )
        # Should prefer precision for deep_dive mode
        assert result.intent == QueryIntent.PRECISION

    def test_single_word_query_low_confidence(self, classifier):
        """Should have low confidence for single word queries."""
        result = classifier.classify_sync(
            query="explain",
            mode="summarize",
            num_videos=5,
        )
        assert result.confidence < 0.7


class TestFollowUpDetection:
    """Tests for follow-up query detection."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_tell_me_more_inherits_intent(self, classifier):
        """Should inherit intent from previous query for 'tell me more'."""
        history = [
            {"role": "user", "content": "Summarize these videos"},
            {"role": "assistant", "content": "Here is a summary..."},
        ]
        result = classifier.classify_sync(
            query="Tell me more",
            mode="summarize",
            num_videos=5,
            recent_messages=history,
        )
        # Should inherit COVERAGE from previous summarize query
        assert result.intent == QueryIntent.COVERAGE
        assert "follow-up" in result.reasoning.lower()

    def test_expand_on_that_inherits_intent(self, classifier):
        """Should inherit intent from previous query for 'expand on that'."""
        history = [
            {"role": "user", "content": "Why do schools kill creativity?"},
            {"role": "assistant", "content": "Because..."},
        ]
        result = classifier.classify_sync(
            query="Expand on that",
            mode="deep_dive",
            num_videos=5,
            recent_messages=history,
        )
        # Should inherit PRECISION from previous why query
        assert result.intent == QueryIntent.PRECISION

    def test_continue_inherits_intent(self, classifier):
        """Should inherit intent for 'continue'."""
        history = [
            {"role": "user", "content": "What are the key themes?"},
            {"role": "assistant", "content": "The main themes are..."},
        ]
        result = classifier.classify_sync(
            query="Continue",
            mode="summarize",
            num_videos=5,
            recent_messages=history,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestIntentSwitchDetection:
    """Tests for explicit intent switch detection."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_now_summarize_switches_to_coverage(self, classifier):
        """Should detect 'now summarize' as switch to coverage."""
        result = classifier.classify_sync(
            query="Now give me an overview",
            mode="deep_dive",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE
        assert "switch" in result.reasoning.lower()

    def test_get_specific_switches_to_precision(self, classifier):
        """Should detect 'get specific' as switch to precision."""
        result = classifier.classify_sync(
            query="Now find me the specific part",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.PRECISION


class TestRegexFallback:
    """Tests for regex-based fallback classification."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_multiple_coverage_patterns_increase_confidence(self, classifier):
        """Should have higher confidence with multiple pattern matches."""
        # Single pattern
        result1 = classifier.classify_sync(
            query="Summarize",
            mode="summarize",
            num_videos=5,
        )

        # Multiple patterns
        result2 = classifier.classify_sync(
            query="Summarize the main points and key themes",
            mode="summarize",
            num_videos=5,
        )

        assert result2.confidence >= result1.confidence

    def test_case_insensitive_matching(self, classifier):
        """Should match patterns case-insensitively."""
        result = classifier.classify_sync(
            query="SUMMARIZE THESE VIDEOS",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestModeInfluence:
    """Tests for mode influence on classification."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_summarize_mode_prefers_coverage(self, classifier):
        """Summarize mode should prefer coverage for ambiguous queries."""
        result = classifier.classify_sync(
            query="What is discussed?",
            mode="summarize",
            num_videos=10,
        )
        # Should lean towards coverage due to mode
        assert result.intent in [QueryIntent.COVERAGE, QueryIntent.HYBRID]

    def test_deep_dive_mode_prefers_precision(self, classifier):
        """Deep dive mode should prefer precision for ambiguous queries."""
        result = classifier.classify_sync(
            query="What is discussed?",
            mode="deep_dive",
            num_videos=10,
        )
        # Should lean towards precision due to mode
        assert result.intent == QueryIntent.PRECISION


class TestVideoCountInfluence:
    """Tests for video count influence on classification."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_single_video_query(self, classifier):
        """Should handle single video queries appropriately."""
        result = classifier.classify_sync(
            query="Summarize this video",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_many_videos_with_summarize(self, classifier):
        """Should handle many videos with summarize mode."""
        result = classifier.classify_sync(
            query="Summarize these videos",
            mode="summarize",
            num_videos=50,
        )
        assert result.intent == QueryIntent.COVERAGE
        assert result.confidence > 0.5


class TestGetIntentClassifier:
    """Tests for the global service getter."""

    def test_returns_singleton(self):
        """Should return same instance on repeated calls."""
        classifier1 = get_intent_classifier()
        classifier2 = get_intent_classifier()
        assert classifier1 is classifier2


class TestIntegrationScenarios:
    """Integration-style tests for realistic scenarios."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_ken_robinson_creativity_question(self, classifier):
        """Test specific question about Ken Robinson's TED talk."""
        result = classifier.classify_sync(
            query="Why do schools kill creativity according to Ken Robinson?",
            mode="summarize",  # Even in summarize mode, this is precision
            num_videos=10,
        )
        # Should be precision because it's a specific 'why' question
        assert result.intent == QueryIntent.PRECISION

    def test_multi_video_summary_request(self, classifier):
        """Test summary request across multiple videos."""
        result = classifier.classify_sync(
            query="What are the common themes across all these TED talks?",
            mode="summarize",
            num_videos=15,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_comparison_with_evidence(self, classifier):
        """Test comparison request that needs evidence."""
        result = classifier.classify_sync(
            query="Compare what each speaker says about education with specific quotes",
            mode="compare_sources",
            num_videos=5,
        )
        # Could be hybrid due to comparison + quotes
        assert result.intent in [QueryIntent.HYBRID, QueryIntent.COVERAGE]

    def test_conversation_flow(self, classifier):
        """Test a multi-turn conversation flow."""
        # Turn 1: Overview question
        result1 = classifier.classify_sync(
            query="What are these videos about?",
            mode="summarize",
            num_videos=5,
        )
        assert result1.intent == QueryIntent.COVERAGE

        # Turn 2: Follow-up precision question
        history = [
            {"role": "user", "content": "What are these videos about?"},
            {"role": "assistant", "content": "These videos discuss creativity..."},
        ]
        result2 = classifier.classify_sync(
            query="What specifically did they say about school systems?",
            mode="summarize",
            num_videos=5,
            recent_messages=history,
        )
        assert result2.intent == QueryIntent.PRECISION

        # Turn 3: Back to overview
        history2 = history + [
            {"role": "user", "content": "What specifically did they say about school systems?"},
            {"role": "assistant", "content": "They said schools kill creativity..."},
        ]
        result3 = classifier.classify_sync(
            query="Now give me the overall summary",
            mode="summarize",
            num_videos=5,
            recent_messages=history2,
        )
        assert result3.intent == QueryIntent.COVERAGE
