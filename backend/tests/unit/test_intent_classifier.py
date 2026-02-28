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


class TestBroadQueryCoverage:
    """Tests for broad query patterns that previously misclassified as PRECISION.

    These are the 11 real-world queries from the coverage bug investigation.
    All broad queries should classify as COVERAGE, especially with many videos.
    """

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_different_themes_grouped_by(self, classifier):
        """The original bug query — should be COVERAGE."""
        result = classifier.classify_sync(
            query="what are the different themes can each of these sources be grouped by?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_topics_do_videos_cover(self, classifier):
        """Should detect topic coverage query."""
        result = classifier.classify_sync(
            query="what topics do these videos cover?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_group_by_subject_matter(self, classifier):
        """Should detect grouping queries."""
        result = classifier.classify_sync(
            query="group these by subject matter",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_organize_into_categories(self, classifier):
        """Should detect organize/categorize queries."""
        result = classifier.classify_sync(
            query="organize these sources into categories",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_break_down_content_of_all_40_videos(self, classifier):
        """Should handle 'all N videos' pattern."""
        result = classifier.classify_sync(
            query="break down the content of all 40 videos",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_kind_of_content(self, classifier):
        """Should detect content discovery queries."""
        result = classifier.classify_sync(
            query="what kind of content do I have?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_can_i_learn(self, classifier):
        """Should detect learning/coverage queries."""
        result = classifier.classify_sync(
            query="what can I learn from all these videos?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_how_would_you_organize(self, classifier):
        """Should detect organization queries."""
        result = classifier.classify_sync(
            query="how would you organize these videos?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_each_video_about(self, classifier):
        """Should detect 'each video' pattern (already worked)."""
        result = classifier.classify_sync(
            query="what is each video about?",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_every_source(self, classifier):
        """Should detect 'every source' pattern (already worked)."""
        result = classifier.classify_sync(
            query="list the main ideas from every source",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_overview(self, classifier):
        """Should detect 'overview' pattern (already worked)."""
        result = classifier.classify_sync(
            query="give me an overview of everything",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestCrossSourceThreshold:
    """Tests for the adjusted cross-source keyword threshold."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_single_keyword_with_many_videos_routes_coverage(self, classifier):
        """With >5 videos, a single cross-source keyword should trigger COVERAGE."""
        result = classifier.classify_sync(
            query="what are the different themes here?",
            mode="deep_dive",
            num_videos=20,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_single_keyword_with_few_videos_stays_precision(self, classifier):
        """With <=5 videos, a single keyword should NOT trigger COVERAGE."""
        result = classifier.classify_sync(
            query="tell me about the theme",
            mode="deep_dive",
            num_videos=3,
        )
        # Should not match coverage patterns and fall to mode-based precision
        assert result.intent == QueryIntent.PRECISION

    def test_two_keywords_with_few_videos_routes_coverage(self, classifier):
        """With <=5 videos, 2+ keywords should still trigger COVERAGE."""
        result = classifier.classify_sync(
            query="compare the themes and differences",
            mode="deep_dive",
            num_videos=3,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestGetIntentClassifier:
    """Tests for the global service getter."""

    def test_returns_singleton(self):
        """Should return same instance on repeated calls."""
        classifier1 = get_intent_classifier()
        classifier2 = get_intent_classifier()
        assert classifier1 is classifier2


class TestPatternCollisionGuards:
    """Guards against COVERAGE patterns accidentally matching PRECISION queries.

    The new patterns (different/various themes, grouped, categoriz, classify)
    could collide with precision queries that happen to contain these words.
    This is the highest-risk regression area.
    """

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_why_question_stays_precision_despite_themes_word(self, classifier):
        """'why do different themes emerge?' — has 'different themes' COVERAGE
        pattern but 'why do' is a strong PRECISION signal."""
        result = classifier.classify_sync(
            query="why do different themes emerge in these videos?",
            mode="deep_dive",
            num_videos=10,
        )
        # PRECISION or HYBRID, NOT pure COVERAGE
        assert result.intent in [QueryIntent.PRECISION, QueryIntent.HYBRID]

    def test_find_specific_category_stays_precision(self, classifier):
        """'find the part about categorization' — 'categoriz' matches COVERAGE
        but 'find the part' is PRECISION."""
        result = classifier.classify_sync(
            query="find the part about categorization",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent in [QueryIntent.PRECISION, QueryIntent.HYBRID]

    def test_what_did_speaker_say_about_topics_stays_precision(self, classifier):
        """'what did the speaker say about topics?' — 'topics' is a cross-source
        keyword but 'what did X say about' is a strong PRECISION pattern."""
        result = classifier.classify_sync(
            query="what did the speaker say about topics?",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_timestamp_request_with_group_word(self, classifier):
        """'at what timestamp do they discuss group dynamics?' — 'group' matches
        COVERAGE keyword but 'timestamp' is PRECISION."""
        result = classifier.classify_sync(
            query="at what timestamp do they discuss group dynamics?",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent in [QueryIntent.PRECISION, QueryIntent.HYBRID]

    def test_quote_about_different_themes(self, classifier):
        """'quote what they said about different themes' — 'different themes'
        COVERAGE pattern but 'quote' is PRECISION."""
        result = classifier.classify_sync(
            query="quote what they said about different themes",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent in [QueryIntent.PRECISION, QueryIntent.HYBRID]


class TestCrossSourceBoundaryBehavior:
    """Tests the num_videos > 5 threshold boundary exactly.

    The min_hits = 1 if num_videos > 5 else 2 boundary is critical.
    Off-by-one bugs here would silently misroute hundreds of queries.
    """

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_boundary_5_videos_requires_two_keywords(self, classifier):
        """num_videos=5 (boundary), query with 1 cross-source keyword -> PRECISION."""
        result = classifier.classify_sync(
            query="tell me about the theme",
            mode="deep_dive",
            num_videos=5,
        )
        # With only 1 keyword hit and num_videos=5 (not >5), threshold is 2
        assert result.intent == QueryIntent.PRECISION

    def test_boundary_6_videos_accepts_one_keyword(self, classifier):
        """num_videos=6 (just past boundary), query with 1 keyword -> COVERAGE."""
        result = classifier.classify_sync(
            query="tell me about the theme",
            mode="deep_dive",
            num_videos=6,
        )
        # With 1 keyword hit ("theme") and num_videos=6 (>5), threshold drops to 1
        assert result.intent == QueryIntent.COVERAGE

    def test_zero_videos_no_crash(self, classifier):
        """num_videos=0, ambiguous query -> no exception."""
        result = classifier.classify_sync(
            query="tell me about themes",
            mode="summarize",
            num_videos=0,
        )
        assert isinstance(result, IntentClassification)
        assert result.intent in [QueryIntent.COVERAGE, QueryIntent.PRECISION, QueryIntent.HYBRID]

    def test_negative_videos_no_crash(self, classifier):
        """num_videos=-1 -> no exception."""
        result = classifier.classify_sync(
            query="tell me about themes",
            mode="summarize",
            num_videos=-1,
        )
        assert isinstance(result, IntentClassification)


class TestNewCoveragePatternExhaustive:
    """Each new COVERAGE pattern tested in isolation to verify it fires."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_pattern_various_categories(self, classifier):
        """Pattern: (different|various|main|major) (themes?|topics?|categories)."""
        result = classifier.classify_sync(
            query="what are the various categories?",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_pattern_classify_content(self, classifier):
        """Pattern: classif(y|ied|ying)."""
        result = classifier.classify_sync(
            query="classify this content for me",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_pattern_break_down_all(self, classifier):
        """Pattern: break down .* (content|all|these|the)."""
        result = classifier.classify_sync(
            query="break down all the content",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_pattern_all_40_videos(self, classifier):
        """Pattern: all \\d+ (videos?|sources?|transcripts?)."""
        result = classifier.classify_sync(
            query="summarize all 40 videos",
            mode="summarize",
            num_videos=40,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_pattern_how_would_you_categorize(self, classifier):
        """Pattern: how would you (organize|group|categorize|classify)."""
        result = classifier.classify_sync(
            query="how would you categorize these?",
            mode="summarize",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestExtendedCrossSourceKeywords:
    """Test new cross-source keywords specifically."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_new_keyword_organize_triggers_coverage(self, classifier):
        """'organize' keyword with >5 videos -> COVERAGE."""
        result = classifier.classify_sync(
            query="how should I organize this?",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_new_keyword_content_triggers_coverage(self, classifier):
        """'content' keyword with >5 videos -> COVERAGE."""
        result = classifier.classify_sync(
            query="what content is available?",
            mode="deep_dive",
            num_videos=10,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_keyword_hit_scaling_confidence(self, classifier):
        """3 keyword hits -> higher confidence than 1 keyword hit."""
        result_1kw = classifier.classify_sync(
            query="tell me about themes",
            mode="deep_dive",
            num_videos=10,
        )
        result_3kw = classifier.classify_sync(
            query="compare themes and differences across different topics",
            mode="deep_dive",
            num_videos=10,
        )
        # More keyword hits should give higher or equal confidence
        assert result_3kw.confidence >= result_1kw.confidence


class TestDocumentCoveragePatterns:
    """Tests that document/file/PDF queries route to COVERAGE."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_what_is_this_document_about_classifies_as_coverage(self, classifier):
        """'what is this document all about?' should route to COVERAGE."""
        result = classifier.classify_sync(
            query="what is this document all about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_is_this_about_generic_classifies_as_coverage(self, classifier):
        """'what is this about?' (no noun) should route to COVERAGE."""
        result = classifier.classify_sync(
            query="what is this about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_summarize_this_pdf_classifies_as_coverage(self, classifier):
        """'summarize this PDF' should route to COVERAGE."""
        result = classifier.classify_sync(
            query="summarize this PDF",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_is_this_file_about_classifies_as_coverage(self, classifier):
        """'what is this file about?' should route to COVERAGE."""
        result = classifier.classify_sync(
            query="what is this file about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_is_it_about_classifies_as_coverage(self, classifier):
        """'what is it about?' should route to COVERAGE."""
        result = classifier.classify_sync(
            query="what is it about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_each_document_pattern(self, classifier):
        """'each document' should match the expanded COVERAGE pattern."""
        result = classifier.classify_sync(
            query="what is each document about?",
            mode="summarize",
            num_videos=5,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_is_this_podcast_about(self, classifier):
        """'what is this podcast about?' — future content type, no noun enumeration needed."""
        result = classifier.classify_sync(
            query="what is this podcast about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_what_are_these_recordings_about(self, classifier):
        """'what are these recordings about?' — structural match, not noun-specific."""
        result = classifier.classify_sync(
            query="what are these recordings about?",
            mode="summarize",
            num_videos=3,
        )
        assert result.intent == QueryIntent.COVERAGE


class TestSingleDocCoverageRouting:
    """Tests that single-document queries with summarize mode route to COVERAGE."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier instance."""
        return IntentClassifier()

    def test_single_doc_summarize_mode_routes_to_coverage(self, classifier):
        """Single doc + summarize mode + ambiguous query -> COVERAGE (not PRECISION)."""
        result = classifier.classify_sync(
            query="tell me about this content",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE

    def test_single_doc_deep_dive_still_routes_to_precision(self, classifier):
        """Single doc + deep_dive mode + ambiguous query -> PRECISION (unchanged)."""
        result = classifier.classify_sync(
            query="tell me about this content",
            mode="deep_dive",
            num_videos=1,
        )
        assert result.intent == QueryIntent.PRECISION

    def test_single_doc_summarize_with_what_is_this(self, classifier):
        """'what is this document about' + summarize mode + 1 doc -> COVERAGE."""
        result = classifier.classify_sync(
            query="what is this document about?",
            mode="summarize",
            num_videos=1,
        )
        assert result.intent == QueryIntent.COVERAGE


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
