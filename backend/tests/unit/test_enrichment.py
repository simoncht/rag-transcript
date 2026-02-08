"""
Unit tests for the contextual enrichment service.

Tests LLM enrichment, fallback heuristics, retry logic, and batch processing.
"""
import json
import time
from unittest.mock import MagicMock, patch

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
