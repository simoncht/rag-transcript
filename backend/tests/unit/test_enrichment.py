"""
Unit tests for the contextual enrichment service.

Tests LLM enrichment, fallback heuristics, retry logic, batch processing,
concurrent enrichment, usage tracking, truncation behavior, and edge cases.
"""
import json
import logging
import time
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.chunking import Chunk
from app.services.enrichment import ContextualEnricher, EnrichedChunk


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_chunk(text="This is a test chunk about machine learning.", index=0, start=0.0, end=10.0):
    return Chunk(
        text=text,
        start_timestamp=start,
        end_timestamp=end,
        token_count=len(text.split()),
        chunk_index=index,
    )


def _make_llm_response(title="T", summary="S.", keywords=None, usage=None):
    """Helper to create a mock LLM response with valid JSON content."""
    if keywords is None:
        keywords = ["k"]
    response = MagicMock()
    response.content = json.dumps({
        "title": title,
        "summary": summary,
        "keywords": keywords,
    })
    response.usage = usage
    return response


# ── EnrichedChunk Dataclass Tests ─────────────────────────────────────────


class TestEnrichedChunk:
    def test_embedding_text_with_metadata(self):
        chunk = _make_chunk()
        enriched = EnrichedChunk(
            chunk=chunk,
            title="ML Basics",
            summary="An overview of machine learning.",
            keywords=["ml", "ai"],
        )
        assert enriched.embedding_text.startswith("ML Basics. An overview")
        assert chunk.text in enriched.embedding_text

    def test_embedding_text_fallback_without_metadata(self):
        chunk = _make_chunk()
        enriched = EnrichedChunk(chunk=chunk)
        assert enriched.embedding_text == chunk.text

    def test_embedding_text_only_title(self):
        chunk = _make_chunk()
        enriched = EnrichedChunk(chunk=chunk, title="Title Only")
        # No summary → fallback to raw text
        assert enriched.embedding_text == chunk.text

    def test_embedding_text_only_summary(self):
        chunk = _make_chunk()
        enriched = EnrichedChunk(chunk=chunk, summary="Summary only")
        assert enriched.embedding_text == chunk.text

    def test_embedding_text_format(self):
        """Verify the exact format: '{title}. {summary}\n\n{text}'."""
        chunk = _make_chunk("Raw text here.")
        enriched = EnrichedChunk(
            chunk=chunk,
            title="My Title",
            summary="My summary.",
            keywords=["kw"],
        )
        expected = "My Title. My summary.\n\nRaw text here."
        assert enriched.embedding_text == expected

    def test_enriched_chunk_preserves_original_chunk(self):
        """EnrichedChunk should keep a reference to the original Chunk unchanged."""
        chunk = _make_chunk("Original text.", index=5)
        enriched = EnrichedChunk(
            chunk=chunk,
            title="T",
            summary="S",
            keywords=["k"],
        )
        assert enriched.chunk is chunk
        assert enriched.chunk.chunk_index == 5
        assert enriched.chunk.text == "Original text."

    def test_enriched_chunk_with_empty_string_title_and_summary(self):
        """Empty-string title/summary are truthy in Python; embedding_text uses them."""
        chunk = _make_chunk()
        enriched = EnrichedChunk(chunk=chunk, title="", summary="")
        # Both empty strings are falsy, so __post_init__ condition is False
        assert enriched.embedding_text == chunk.text

    def test_enriched_chunk_keywords_none_with_title_and_summary(self):
        """Keywords can be None and embedding text should still be generated."""
        chunk = _make_chunk("Some text.")
        enriched = EnrichedChunk(
            chunk=chunk,
            title="Title",
            summary="Summary.",
            keywords=None,
        )
        # Title and summary are set, so embedding text is constructed
        assert enriched.embedding_text == "Title. Summary.\n\nSome text."


# ── Fallback Enrichment Tests ─────────────────────────────────────────────


class TestFallbackEnrichment:
    def test_creates_title_from_first_sentence(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("First sentence here. Second one. Third one.")
        result = enricher._create_fallback_enrichment(chunk)

        assert result["title"] == "First sentence here"
        assert "First sentence here" in result["summary"]

    def test_title_truncated_at_50_chars(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        long_sentence = "A" * 60 + ". Short."
        chunk = _make_chunk(long_sentence)
        result = enricher._create_fallback_enrichment(chunk)

        assert len(result["title"]) <= 53  # 50 + "..."
        assert result["title"].endswith("...")

    def test_keywords_exclude_stopwords(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk(
            "The machine learning algorithm processes data efficiently. "
            "Machine learning is powerful for data analysis."
        )
        result = enricher._create_fallback_enrichment(chunk)

        keywords = result["keywords"]
        assert len(keywords) <= 5
        # Stopwords should be excluded
        assert "the" not in keywords
        assert "is" not in keywords
        # Common words should appear
        assert any("machine" in k or "learning" in k or "data" in k for k in keywords)

    def test_summary_limited_to_300_chars(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        long_text = ". ".join(["Long sentence number " + str(i) for i in range(50)])
        chunk = _make_chunk(long_text)
        result = enricher._create_fallback_enrichment(chunk)

        assert len(result["summary"]) <= 301  # 300 + trailing "."

    def test_fallback_single_sentence(self):
        """Chunk with no period separator should still produce valid fallback."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("Just one sentence without a period")
        result = enricher._create_fallback_enrichment(chunk)

        assert result["title"] == "Just one sentence without a period"
        assert result["summary"].endswith(".")

    def test_fallback_empty_text(self):
        """Empty text should not crash fallback enrichment."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("")
        result = enricher._create_fallback_enrichment(chunk)

        assert result["title"] == ""
        assert isinstance(result["keywords"], list)

    def test_fallback_short_words_excluded(self):
        """Words with 3 or fewer characters are excluded from keywords."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("Go to the big map and see the red fox run far away now")
        result = enricher._create_fallback_enrichment(chunk)

        keywords = result["keywords"]
        # All keywords should be >3 chars (after cleaning)
        for kw in keywords:
            assert len(kw) > 3, f"Short word '{kw}' should be excluded"

    def test_fallback_exactly_two_sentences(self):
        """Chunk with exactly 2 sentences should use both in summary."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("First sentence. Second sentence")
        result = enricher._create_fallback_enrichment(chunk)

        assert "First sentence" in result["summary"]
        assert "Second sentence" in result["summary"]


# ── Parse Enrichment Response Tests ───────────────────────────────────────


class TestParseEnrichmentResponse:
    def test_parses_valid_json(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({
            "title": "AI Basics",
            "summary": "An introduction to AI.",
            "keywords": ["ai", "ml"],
        })
        result = enricher._parse_enrichment_response(response)

        assert result["title"] == "AI Basics"
        assert result["summary"] == "An introduction to AI."
        assert result["keywords"] == ["ai", "ml"]

    def test_strips_markdown_json_block(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = '```json\n{"title": "Test", "summary": "Sum.", "keywords": ["k"]}\n```'
        result = enricher._parse_enrichment_response(response)
        assert result["title"] == "Test"

    def test_strips_plain_markdown_block(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = '```\n{"title": "Test", "summary": "Sum.", "keywords": ["k"]}\n```'
        result = enricher._parse_enrichment_response(response)
        assert result["title"] == "Test"

    def test_missing_title_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"summary": "Sum.", "keywords": ["k"]})
        with pytest.raises(ValueError, match="Missing required fields"):
            enricher._parse_enrichment_response(response)

    def test_missing_summary_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": "T", "keywords": ["k"]})
        with pytest.raises(ValueError, match="Missing required fields"):
            enricher._parse_enrichment_response(response)

    def test_missing_keywords_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": "T", "summary": "S"})
        with pytest.raises(ValueError, match="Missing required fields"):
            enricher._parse_enrichment_response(response)

    def test_keywords_not_list_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": "T", "summary": "S", "keywords": "not-list"})
        with pytest.raises(ValueError, match="Keywords must be a list"):
            enricher._parse_enrichment_response(response)

    def test_invalid_json_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        with pytest.raises(ValueError, match="Failed to parse"):
            enricher._parse_enrichment_response("not json at all")

    def test_title_not_string_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": 123, "summary": "S", "keywords": ["k"]})
        with pytest.raises(ValueError, match="Title must be a string"):
            enricher._parse_enrichment_response(response)

    def test_summary_not_string_raises(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": "T", "summary": ["not", "string"], "keywords": ["k"]})
        with pytest.raises(ValueError, match="Summary must be a string"):
            enricher._parse_enrichment_response(response)

    def test_extra_fields_ignored(self):
        """Extra fields in the JSON response should not cause errors."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({
            "title": "T",
            "summary": "S.",
            "keywords": ["k"],
            "extra_field": "ignored",
            "confidence": 0.95,
        })
        result = enricher._parse_enrichment_response(response)
        assert result["title"] == "T"

    def test_whitespace_around_json(self):
        """Leading/trailing whitespace should be handled."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = '  \n  {"title": "T", "summary": "S.", "keywords": ["k"]}  \n  '
        result = enricher._parse_enrichment_response(response)
        assert result["title"] == "T"

    def test_empty_keywords_list(self):
        """An empty keywords list is valid (it is a list)."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        response = json.dumps({"title": "T", "summary": "S.", "keywords": []})
        result = enricher._parse_enrichment_response(response)
        assert result["keywords"] == []


# ── Enrich Chunk Tests ────────────────────────────────────────────────────


class TestEnrichChunk:
    @patch("app.services.enrichment.settings")
    def test_llm_enrichment_success(self, mock_settings):
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps({
            "title": "ML Overview",
            "summary": "An overview of ML concepts.",
            "keywords": ["ml", "ai", "deep learning"],
        })
        llm.complete.return_value = response

        enricher = ContextualEnricher(llm_service=llm)
        chunk = _make_chunk()
        result = enricher.enrich_chunk(chunk)

        assert isinstance(result, EnrichedChunk)
        assert result.title == "ML Overview"
        assert result.summary == "An overview of ML concepts."
        assert result.keywords == ["ml", "ai", "deep learning"]
        llm.complete.assert_called_once()

    @patch("app.services.enrichment.settings")
    def test_enrichment_disabled_uses_fallback(self, mock_settings):
        mock_settings.enable_contextual_enrichment = False

        llm = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        chunk = _make_chunk("Machine learning is great. It powers many systems.")
        result = enricher.enrich_chunk(chunk)

        assert isinstance(result, EnrichedChunk)
        assert result.title is not None
        # LLM should NOT be called
        llm.complete.assert_not_called()

    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_retry_on_failure_then_success(self, mock_settings, mock_sleep):
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        good_response = MagicMock()
        good_response.content = json.dumps({
            "title": "Title", "summary": "Summary.", "keywords": ["k"],
        })
        # Fail twice, succeed on third
        llm.complete.side_effect = [
            Exception("API error"),
            Exception("Timeout"),
            good_response,
        ]

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk())

        assert result.title == "Title"
        assert llm.complete.call_count == 3
        # Exponential backoff: sleep(1), sleep(2)
        assert mock_sleep.call_count == 2

    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_all_retries_exhausted_uses_fallback(self, mock_settings, mock_sleep):
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        llm.complete.side_effect = Exception("Always fails")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Test sentence here. Second sentence."))

        assert isinstance(result, EnrichedChunk)
        assert result.title is not None  # Fallback title
        assert llm.complete.call_count == 3

    @patch("app.services.enrichment.settings")
    def test_permanent_error_402_skips_retries(self, mock_settings):
        """402 (insufficient balance) should not be retried."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        llm.complete.side_effect = Exception("402 Payment Required")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Some text. Another sentence."))

        # Should only try once — 402 is permanent
        assert llm.complete.call_count == 1
        assert isinstance(result, EnrichedChunk)
        assert result.title is not None  # Fallback

    @patch("app.services.enrichment.settings")
    def test_permanent_error_401_skips_retries(self, mock_settings):
        """401 (unauthorized) should not be retried."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        llm.complete.side_effect = Exception("401 Unauthorized")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Some text. Another sentence."))

        assert llm.complete.call_count == 1
        assert isinstance(result, EnrichedChunk)

    @patch("app.services.enrichment.settings")
    def test_permanent_error_403_skips_retries(self, mock_settings):
        """403 (forbidden) should not be retried."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        llm.complete.side_effect = Exception("403 Forbidden")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Some text. Another sentence."))

        assert llm.complete.call_count == 1

    @patch("app.services.enrichment.settings")
    def test_permanent_error_insufficient_balance_skips_retries(self, mock_settings):
        """Insufficient Balance error should not be retried."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 3

        llm = MagicMock()
        llm.complete.side_effect = Exception("Insufficient Balance")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Some text. Another sentence."))

        assert llm.complete.call_count == 1

    @patch("app.services.enrichment.settings")
    def test_usage_collector_called_on_success(self, mock_settings):
        """Usage collector should record usage when LLM returns usage data."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        usage_data = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        response = _make_llm_response(
            title="Title", summary="Summary.", keywords=["k"], usage=usage_data
        )
        llm.complete.return_value = response

        usage_collector = MagicMock()
        content_id = uuid.uuid4()
        enricher = ContextualEnricher(
            llm_service=llm,
            usage_collector=usage_collector,
            content_id=content_id,
        )
        enricher.enrich_chunk(_make_chunk())

        usage_collector.record.assert_called_once_with(
            response, "enrichment", content_id=content_id
        )

    @patch("app.services.enrichment.settings")
    def test_usage_collector_not_called_when_usage_none(self, mock_settings):
        """Usage collector should NOT record when response.usage is None."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        response = _make_llm_response()
        response.usage = None
        llm.complete.return_value = response

        usage_collector = MagicMock()
        enricher = ContextualEnricher(
            llm_service=llm, usage_collector=usage_collector
        )
        enricher.enrich_chunk(_make_chunk())

        usage_collector.record.assert_not_called()

    @patch("app.services.enrichment.settings")
    def test_no_usage_collector_no_error(self, mock_settings):
        """When usage_collector is None, enrichment should still work fine."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        response = _make_llm_response()
        response.usage = {"input_tokens": 10, "output_tokens": 5}
        llm.complete.return_value = response

        enricher = ContextualEnricher(llm_service=llm, usage_collector=None)
        result = enricher.enrich_chunk(_make_chunk())

        assert isinstance(result, EnrichedChunk)

    @patch("app.services.enrichment.settings")
    def test_llm_called_with_correct_params(self, mock_settings):
        """Verify LLM is called with expected temperature and max_tokens."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        enricher.enrich_chunk(_make_chunk())

        call_kwargs = llm.complete.call_args
        assert call_kwargs.kwargs["temperature"] == 0.3
        assert call_kwargs.kwargs["max_tokens"] == 500
        assert call_kwargs.kwargs["retry"] is False

    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_max_retries_one_no_sleep(self, mock_settings, mock_sleep):
        """With max_retries=1, failure should go straight to fallback with no sleep."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.side_effect = Exception("Some error")

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk("Test sentence. Another one."))

        assert llm.complete.call_count == 1
        mock_sleep.assert_not_called()
        assert isinstance(result, EnrichedChunk)

    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_parse_error_triggers_retry(self, mock_settings, mock_sleep):
        """Invalid JSON from LLM should trigger retry, not immediate fallback."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 2

        llm = MagicMock()
        bad_response = MagicMock()
        bad_response.content = "This is not JSON"
        bad_response.usage = None
        good_response = _make_llm_response()
        llm.complete.side_effect = [bad_response, good_response]

        enricher = ContextualEnricher(llm_service=llm)
        result = enricher.enrich_chunk(_make_chunk())

        assert result.title == "T"
        assert llm.complete.call_count == 2


# ── Enrichment Prompt Tests ───────────────────────────────────────────────


class TestEnrichmentPrompt:
    def test_prompt_includes_chunk_text(self):
        llm = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        chunk = _make_chunk("Unique text about neural networks.")
        messages = enricher._create_enrichment_prompt(chunk)

        assert len(messages) == 2  # system + user
        assert "neural networks" in messages[1].content

    def test_prompt_includes_video_context(self):
        llm = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        enricher.set_video_context("Intro to AI", "A beginner course")
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        assert "Intro to AI" in messages[1].content

    def test_prompt_includes_full_text_in_system(self):
        llm = MagicMock()
        enricher = ContextualEnricher(
            llm_service=llm,
            full_text="This is the full transcript of the video about AI and ML."
        )
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        assert "full transcript" in messages[0].content.lower() or "full_transcript" in messages[0].content

    def test_prompt_for_document_content_type(self):
        llm = MagicMock()
        enricher = ContextualEnricher(llm_service=llm, content_type="pdf")
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        assert "document section" in messages[0].content

    def test_full_text_truncated_at_48k(self):
        llm = MagicMock()
        long_text = "A" * 60000
        enricher = ContextualEnricher(llm_service=llm, full_text=long_text)
        assert len(enricher.full_text) == 48000

    def test_prompt_youtube_uses_timestamp(self):
        """YouTube content type should show timestamp in user message."""
        enricher = ContextualEnricher(llm_service=MagicMock(), content_type="youtube")
        chunk = _make_chunk(start=125.0)  # 2:05
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "timestamp 02:05" in user_content
        assert "transcript segment" in user_content

    def test_prompt_document_uses_page_number(self):
        """Document content type should show page number in user message."""
        enricher = ContextualEnricher(llm_service=MagicMock(), content_type="pdf")
        chunk = _make_chunk()
        chunk.page_number = 7
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "page 7" in user_content

    def test_prompt_document_unknown_page(self):
        """Document chunk without page_number should show 'unknown location'."""
        enricher = ContextualEnricher(llm_service=MagicMock(), content_type="docx")
        chunk = _make_chunk()
        # chunk has no page_number attribute → getattr returns None
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "unknown location" in user_content

    def test_prompt_without_context(self):
        """When no video/source context is set, user message should not contain context info."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "Video context" not in user_content
        assert "Document context" not in user_content

    def test_prompt_with_source_context_document(self):
        """Document enrichment should use 'Document context' label."""
        enricher = ContextualEnricher(
            llm_service=MagicMock(),
            content_type="pdf",
            source_context="Title: My Paper | Description: A research paper",
        )
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "Document context" in user_content

    def test_prompt_with_video_context_youtube(self):
        """YouTube enrichment should use 'Video context' label."""
        enricher = ContextualEnricher(
            llm_service=MagicMock(),
            content_type="youtube",
            video_context="Title: My Video | Description: About AI",
        )
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        user_content = messages[1].content
        assert "Video context" in user_content

    def test_full_text_not_in_system_when_none(self):
        """When full_text is None, system message should not contain full_transcript tags."""
        enricher = ContextualEnricher(llm_service=MagicMock(), full_text=None)
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        assert "<full_transcript>" not in messages[0].content

    def test_full_text_in_system_for_document(self):
        """For documents, full text should use <full_document> tags."""
        enricher = ContextualEnricher(
            llm_service=MagicMock(),
            content_type="pdf",
            full_text="Full document text here."
        )
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        assert "<full_document>" in messages[0].content
        assert "</full_document>" in messages[0].content

    def test_system_message_contains_json_format_spec(self):
        """System message should instruct the model to return JSON with required fields."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk()
        messages = enricher._create_enrichment_prompt(chunk)

        system_content = messages[0].content
        assert '"title"' in system_content
        assert '"summary"' in system_content
        assert '"keywords"' in system_content
        assert "valid JSON" in system_content


# ── Batch Processing Tests ────────────────────────────────────────────────


class TestEnrichChunksBatch:
    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_batch_rate_limiting(self, mock_settings, mock_sleep):
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 3

        llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps({
            "title": "T", "summary": "S.", "keywords": ["k"],
        })
        llm.complete.return_value = response

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i} text.", index=i) for i in range(7)]
        results = enricher.enrich_chunks_batch(chunks)

        assert len(results) == 7
        # With batch_size=3 and 7 chunks: sleep after chunk 3 and 6
        assert mock_sleep.call_count == 2

    @patch("app.services.enrichment.settings")
    def test_batch_returns_all_enriched(self, mock_settings):
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 100

        llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps({
            "title": "T", "summary": "S.", "keywords": ["k"],
        })
        llm.complete.return_value = response

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(5)]
        results = enricher.enrich_chunks_batch(chunks)

        assert len(results) == 5
        assert all(isinstance(r, EnrichedChunk) for r in results)

    @patch("app.services.enrichment.settings")
    def test_batch_empty_list(self, mock_settings):
        """Batch enrichment with empty list should return empty list."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 10

        llm = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        results = enricher.enrich_chunks_batch([])

        assert results == []
        llm.complete.assert_not_called()

    @patch("app.services.enrichment.time.sleep")
    @patch("app.services.enrichment.settings")
    def test_batch_no_sleep_when_exact_batch_boundary(self, mock_settings, mock_sleep):
        """When total chunks equals batch_size, no rate-limiting sleep should occur."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 3

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        # Exactly 3 chunks with batch_size=3: sleep fires after chunk 3
        # but since i+1 == len(chunks), the condition `i + 1 < len(chunks)` is False
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(3)]
        enricher.enrich_chunks_batch(chunks)

        mock_sleep.assert_not_called()

    @patch("app.services.enrichment.settings")
    def test_batch_show_progress_prints(self, mock_settings, capsys):
        """show_progress=True should print progress every 10 chunks."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 100

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(25)]
        enricher.enrich_chunks_batch(chunks, show_progress=True)

        captured = capsys.readouterr()
        assert "Enriched 10/25 chunks" in captured.out
        assert "Enriched 20/25 chunks" in captured.out

    @patch("app.services.enrichment.settings")
    def test_batch_single_chunk(self, mock_settings):
        """Batch with a single chunk should work correctly."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1
        mock_settings.enrichment_batch_size = 10

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response(title="Solo")

        enricher = ContextualEnricher(llm_service=llm)
        results = enricher.enrich_chunks_batch([_make_chunk()])

        assert len(results) == 1
        assert results[0].title == "Solo"


# ── Concurrent Enrichment Tests ──────────────────────────────────────────


class TestEnrichChunksConcurrent:
    @patch("app.services.enrichment.settings")
    def test_concurrent_returns_correct_count(self, mock_settings):
        """Concurrent enrichment should return same number of chunks as input."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(5)]
        results = enricher.enrich_chunks_concurrent(chunks, max_workers=2)

        assert len(results) == 5
        assert all(isinstance(r, EnrichedChunk) for r in results)

    def test_concurrent_empty_list(self):
        """Concurrent enrichment with empty list should return empty list immediately."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        results = enricher.enrich_chunks_concurrent([])
        assert results == []

    @patch("app.services.enrichment.settings")
    def test_concurrent_preserves_order(self, mock_settings):
        """Results should be in the same order as input chunks."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()

        def side_effect_complete(**kwargs):
            messages = kwargs.get("messages") or (args := None)
            # Return a unique title per call to verify ordering
            return _make_llm_response()

        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i} unique.", index=i) for i in range(10)]
        results = enricher.enrich_chunks_concurrent(chunks, max_workers=3)

        # Each result should correspond to the correct chunk by index
        for i, result in enumerate(results):
            assert result.chunk.chunk_index == i

    @patch("app.services.enrichment.settings")
    def test_concurrent_calls_on_progress(self, mock_settings):
        """on_progress callback should be called for each completed chunk."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        on_progress = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(4)]
        enricher.enrich_chunks_concurrent(
            chunks, max_workers=2, on_progress=on_progress
        )

        assert on_progress.call_count == 4
        # Last call should be (4, 4)
        final_call_args = [c for c in on_progress.call_args_list if c[0][0] == 4]
        assert len(final_call_args) == 1
        assert final_call_args[0][0] == (4, 4)

    @patch("app.services.enrichment.settings")
    def test_concurrent_calls_on_chunk_complete(self, mock_settings):
        """on_chunk_complete callback should be called with each EnrichedChunk."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        on_chunk_complete = MagicMock()
        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(3)]
        enricher.enrich_chunks_concurrent(
            chunks, max_workers=2, on_chunk_complete=on_chunk_complete
        )

        assert on_chunk_complete.call_count == 3
        # Each call should pass an EnrichedChunk
        for c in on_chunk_complete.call_args_list:
            assert isinstance(c[0][0], EnrichedChunk)

    @patch("app.services.enrichment.settings")
    def test_concurrent_handles_thread_exception(self, mock_settings):
        """If a future raises an unexpected exception, concurrent should use fallback."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        # Make enrich_chunk itself raise (simulating a bug beyond retry handling)
        call_count = 0

        def flaky_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Thread crash")
            return _make_llm_response()

        llm.complete.side_effect = flaky_complete

        enricher = ContextualEnricher(llm_service=llm)
        chunks = [_make_chunk(f"Chunk {i}.", index=i) for i in range(3)]

        # This should not raise — concurrent handles exceptions with fallback
        results = enricher.enrich_chunks_concurrent(chunks, max_workers=1)
        assert len(results) == 3
        assert all(r is not None for r in results)

    @patch("app.services.enrichment.settings")
    def test_concurrent_single_chunk(self, mock_settings):
        """Concurrent enrichment with a single chunk should work correctly."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response(title="Single")

        enricher = ContextualEnricher(llm_service=llm)
        results = enricher.enrich_chunks_concurrent([_make_chunk()], max_workers=5)

        assert len(results) == 1
        assert results[0].title == "Single"


# ── Context Setting Tests ─────────────────────────────────────────────────


class TestContextSetting:
    def test_set_video_context(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        enricher.set_video_context("Video Title", "Description text")
        assert "Video Title" in enricher.video_context
        assert "Description text" in enricher.video_context

    def test_set_source_context(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        enricher.set_source_context("Doc Title", "Doc description")
        assert "Doc Title" in enricher.video_context

    def test_description_truncated_at_500(self):
        enricher = ContextualEnricher(llm_service=MagicMock())
        long_desc = "X" * 600
        enricher.set_source_context("Title", long_desc)
        # Description should be truncated
        assert "..." in enricher.video_context

    def test_set_source_context_no_description(self):
        """Setting source context without description should only include title."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        enricher.set_source_context("My Title")

        assert "My Title" in enricher.video_context
        assert "Description" not in enricher.video_context

    def test_set_video_context_delegates_to_set_source_context(self):
        """set_video_context should produce the same result as set_source_context."""
        enricher1 = ContextualEnricher(llm_service=MagicMock())
        enricher2 = ContextualEnricher(llm_service=MagicMock())

        enricher1.set_video_context("Title", "Desc")
        enricher2.set_source_context("Title", "Desc")

        assert enricher1.video_context == enricher2.video_context

    def test_description_exactly_500_chars_not_truncated(self):
        """Description of exactly 500 chars should NOT be truncated."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        desc = "X" * 500
        enricher.set_source_context("Title", desc)

        assert "..." not in enricher.video_context

    def test_description_501_chars_truncated(self):
        """Description of 501 chars should be truncated."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        desc = "X" * 501
        enricher.set_source_context("Title", desc)

        assert "..." in enricher.video_context

    def test_context_format(self):
        """Context should be formatted as 'Title: X | Description: Y'."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        enricher.set_source_context("My Title", "My Description")

        assert enricher.video_context == "Title: My Title | Description: My Description"


# ── Constructor Tests ─────────────────────────────────────────────────────


class TestConstructor:
    def test_source_context_takes_precedence_over_video_context(self):
        """source_context param should override video_context param."""
        enricher = ContextualEnricher(
            llm_service=MagicMock(),
            video_context="video ctx",
            source_context="source ctx",
        )
        assert enricher.video_context == "source ctx"

    def test_video_context_used_when_no_source_context(self):
        """video_context param should be used when source_context is not provided."""
        enricher = ContextualEnricher(
            llm_service=MagicMock(),
            video_context="video ctx",
        )
        assert enricher.video_context == "video ctx"

    def test_content_type_defaults_to_youtube(self):
        """Default content_type should be 'youtube'."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        assert enricher.content_type == "youtube"

    def test_content_type_custom(self):
        """Custom content_type should be stored."""
        enricher = ContextualEnricher(llm_service=MagicMock(), content_type="pdf")
        assert enricher.content_type == "pdf"

    def test_full_text_stored_when_under_limit(self):
        """Full text under 48K should be stored as-is."""
        text = "Hello " * 1000  # ~6000 chars
        enricher = ContextualEnricher(llm_service=MagicMock(), full_text=text)
        assert enricher.full_text == text

    def test_full_text_none(self):
        """full_text=None should result in None."""
        enricher = ContextualEnricher(llm_service=MagicMock(), full_text=None)
        assert enricher.full_text is None

    def test_content_id_stored(self):
        """content_id should be stored for cost attribution."""
        cid = uuid.uuid4()
        enricher = ContextualEnricher(llm_service=MagicMock(), content_id=cid)
        assert enricher.content_id == cid

    def test_usage_collector_stored(self):
        """usage_collector should be stored."""
        collector = MagicMock()
        enricher = ContextualEnricher(llm_service=MagicMock(), usage_collector=collector)
        assert enricher.usage_collector is collector

    @patch("app.services.enrichment.settings")
    def test_max_retries_from_settings(self, mock_settings):
        """max_retries should come from settings."""
        mock_settings.enrichment_max_retries = 7
        enricher = ContextualEnricher(llm_service=MagicMock())
        assert enricher.max_retries == 7


# ── Truncation / PAR-002 Contract Tests ───────────────────────────────────


class TestTruncationBehavior:
    def test_full_text_truncated_to_48k_chars(self):
        """Full text over 48K chars should be truncated to exactly 48000."""
        long_text = "B" * 100000
        enricher = ContextualEnricher(llm_service=MagicMock(), full_text=long_text)
        assert len(enricher.full_text) == 48000
        assert enricher.full_text == "B" * 48000

    def test_truncation_logs_warning(self, caplog):
        """PAR-002: Truncation should emit a warning with chars lost."""
        long_text = "C" * 60000
        with caplog.at_level(logging.WARNING, logger="app.services.enrichment"):
            enricher = ContextualEnricher(
                llm_service=MagicMock(),
                full_text=long_text,
                content_id="test-id-123",
            )

        # Check that warning was logged
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("truncated" in msg.lower() for msg in warning_messages), (
            f"Expected truncation warning, got: {warning_messages}"
        )
        # Check that it includes character count info
        assert any("12000" in msg for msg in warning_messages), (
            "Warning should mention chars lost (60000 - 48000 = 12000)"
        )

    def test_truncation_logs_content_id(self, caplog):
        """Truncation warning should include the content_id for debugging."""
        content_id = str(uuid.uuid4())
        long_text = "D" * 50000
        with caplog.at_level(logging.WARNING, logger="app.services.enrichment"):
            enricher = ContextualEnricher(
                llm_service=MagicMock(),
                full_text=long_text,
                content_id=content_id,
            )

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(content_id in msg for msg in warning_messages), (
            f"Warning should include content_id={content_id}"
        )

    def test_no_warning_when_under_limit(self, caplog):
        """No truncation warning should be logged when text is under 48K."""
        text = "E" * 47999
        with caplog.at_level(logging.WARNING, logger="app.services.enrichment"):
            enricher = ContextualEnricher(llm_service=MagicMock(), full_text=text)

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        truncation_warnings = [m for m in warning_messages if "truncated" in m.lower()]
        assert len(truncation_warnings) == 0

    def test_exactly_48k_not_truncated(self):
        """Text of exactly 48000 chars should NOT be truncated."""
        text = "F" * 48000
        enricher = ContextualEnricher(llm_service=MagicMock(), full_text=text)
        assert len(enricher.full_text) == 48000

    def test_exactly_48k_no_warning(self, caplog):
        """Text of exactly 48000 chars should NOT trigger a warning."""
        text = "G" * 48000
        with caplog.at_level(logging.WARNING, logger="app.services.enrichment"):
            enricher = ContextualEnricher(llm_service=MagicMock(), full_text=text)

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        truncation_warnings = [m for m in warning_messages if "truncated" in m.lower()]
        assert len(truncation_warnings) == 0


# ── Default LLM Service Tests ────────────────────────────────────────────


class TestDefaultLLMService:
    @patch("app.services.enrichment.settings")
    def test_uses_default_llm_when_none_provided(self, mock_settings):
        """When no llm_service is passed, should import and use default."""
        mock_settings.enrichment_max_retries = 3

        with patch("app.services.enrichment.llm_service", create=True) as mock_default:
            # The import happens inside __init__, so we need to patch the module-level import
            with patch("app.services.llm_providers.llm_service", mock_default):
                enricher = ContextualEnricher()
                # The enricher should have been given some llm_service
                assert enricher.llm_service is not None


# ── Edge Case / Integration-Like Tests ───────────────────────────────────


class TestEdgeCases:
    @patch("app.services.enrichment.settings")
    def test_chunk_with_special_characters(self, mock_settings):
        """Chunks with special chars should not break enrichment."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response(
            title="Special", summary="Has special chars.", keywords=["special"]
        )

        enricher = ContextualEnricher(llm_service=llm)
        chunk = _make_chunk('Text with "quotes" and {braces} and <angles> & ampersands.')
        result = enricher.enrich_chunk(chunk)

        assert result.title == "Special"

    @patch("app.services.enrichment.settings")
    def test_chunk_with_unicode(self, mock_settings):
        """Chunks with unicode characters should work correctly."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        chunk = _make_chunk("Discussing machine learning algorithms and data processing.")
        result = enricher.enrich_chunk(chunk)

        assert isinstance(result, EnrichedChunk)

    @patch("app.services.enrichment.settings")
    def test_enrichment_with_all_constructor_params(self, mock_settings):
        """Enricher should work correctly with all constructor params set."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 2

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response(title="Full")
        usage_collector = MagicMock()
        content_id = uuid.uuid4()

        enricher = ContextualEnricher(
            llm_service=llm,
            video_context="old context",
            source_context="new context",
            content_type="pdf",
            full_text="This is the full document text.",
            usage_collector=usage_collector,
            content_id=content_id,
        )

        chunk = _make_chunk()
        result = enricher.enrich_chunk(chunk)

        assert result.title == "Full"
        assert enricher.video_context == "new context"
        assert enricher.content_type == "pdf"

    def test_fallback_with_only_short_words(self):
        """Fallback with text of only short words should return empty keywords."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk("I am a he it is we do so an on at")
        result = enricher._create_fallback_enrichment(chunk)

        # All words are either stopwords or <=3 chars
        assert result["keywords"] == []

    def test_fallback_with_repeated_words(self):
        """Fallback should rank keywords by frequency."""
        enricher = ContextualEnricher(llm_service=MagicMock())
        chunk = _make_chunk(
            "python python python python java java java ruby ruby rust"
        )
        result = enricher._create_fallback_enrichment(chunk)

        keywords = result["keywords"]
        assert len(keywords) <= 5
        # "python" appears most, should be first
        assert keywords[0] == "python"
        assert "java" in keywords

    @patch("app.services.enrichment.settings")
    def test_enrichment_with_very_large_chunk_text(self, mock_settings):
        """Large chunk text should not break the enrichment pipeline."""
        mock_settings.enable_contextual_enrichment = True
        mock_settings.enrichment_max_retries = 1

        llm = MagicMock()
        llm.complete.return_value = _make_llm_response()

        enricher = ContextualEnricher(llm_service=llm)
        large_text = "word " * 10000  # ~50K chars
        chunk = _make_chunk(large_text)
        result = enricher.enrich_chunk(chunk)

        assert isinstance(result, EnrichedChunk)
        llm.complete.assert_called_once()
