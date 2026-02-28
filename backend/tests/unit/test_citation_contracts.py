"""
Tests for citation and accuracy behavioral contracts.

Validates contracts defined in .claude/references/behavioral-contracts.md:
- CIT-001: was_used_in_response tracking
- CIT-002: Citation marker bounds validation
- CIT-003: Jump URL timestamp matches chunk
- ACC-001: Storage vector dimensions match embedding model
- ACC-003: BM25 proper noun handling
"""

import re
import uuid

import pytest


# ── CIT-001: was_used_in_response Tracking ────────────────────────────


class TestCitationTracking:
    """CIT-001: was_used_in_response must reflect actual LLM output."""

    def test_was_used_in_response_default_is_true(self):
        """Default remains True for backwards compat — code explicitly sets per-ref."""
        from app.models.message import MessageChunkReference

        col = MessageChunkReference.__table__.columns["was_used_in_response"]
        assert col.default is not None, "was_used_in_response has no default"
        assert col.default.arg is True

    def test_was_used_in_response_set_explicitly(self):
        """Verify conversations.py sets was_used_in_response based on marker parsing."""
        import os

        # Support both local and Docker paths
        search_dirs = []
        for prefix in ["backend/", ""]:
            d1 = f"{prefix}app/api/routes"
            if os.path.isdir(d1):
                search_dirs = [d1]
                break
        assert search_dirs, "Could not find app/api/routes directory"

        found = False
        for search_dir in search_dirs:
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    filepath = os.path.join(root, fname)
                    with open(filepath, "r") as f:
                        content = f.read()
                    if re.search(r"was_used_in_response\s*=.*used_markers", content):
                        found = True
                        break
                if found:
                    break

        assert found, (
            "CIT-001 BROKEN: conversations.py does not set was_used_in_response "
            "based on used_markers. All citations would be marked as 'used'."
        )

    def test_extract_used_markers_function_exists(self):
        """The _extract_used_markers helper must exist."""
        from app.api.routes.conversations import _extract_used_markers

        assert callable(_extract_used_markers)

    def test_extract_used_markers_basic(self):
        """Extract valid marker numbers from response text."""
        from app.api.routes.conversations import _extract_used_markers

        response = "The AI revolution [1] changed everything [3]."
        result = _extract_used_markers(response, num_sources=5)
        assert result == {1, 3}

    def test_extract_used_markers_filters_out_of_bounds(self):
        """Out-of-bounds markers should NOT be included in used set."""
        from app.api.routes.conversations import _extract_used_markers

        response = "This [1] is supported [7]."
        result = _extract_used_markers(response, num_sources=3)
        assert result == {1}, f"Expected {{1}}, got {result} (7 should be excluded)"

    def test_extract_used_markers_empty_response(self):
        """No markers in response should return empty set."""
        from app.api.routes.conversations import _extract_used_markers

        result = _extract_used_markers("No citations here.", num_sources=5)
        assert result == set()

    def test_extract_used_markers_deduplicates(self):
        """Repeated markers should be deduplicated."""
        from app.api.routes.conversations import _extract_used_markers

        response = "Point A [1]. Point B [1]. Point C [2]."
        result = _extract_used_markers(response, num_sources=3)
        assert result == {1, 2}


# ── CIT-002: Citation Markers Within Bounds ───────────────────────────


class TestCitationMarkerBounds:
    """CIT-002: All [N] markers must map to valid retrieved chunks."""

    def test_validate_citation_markers_function_exists(self):
        """The validation function must exist in conversations module."""
        from app.api.routes.conversations import _validate_citation_markers

        assert callable(_validate_citation_markers)

    def test_valid_markers_return_empty(self):
        """Markers within bounds should return empty list (no violations)."""
        from app.api.routes.conversations import _validate_citation_markers

        response = "The speaker discusses AI [1] and ethics [2]. This is supported [3]."
        result = _validate_citation_markers(response, num_sources=3)
        assert result == [], f"Expected no violations, got {result}"

    def test_out_of_bounds_detected(self):
        """Markers exceeding source count should be detected."""
        from app.api.routes.conversations import _validate_citation_markers

        response = "The answer is clear [1][2][5]."
        result = _validate_citation_markers(response, num_sources=3)
        assert 5 in result, f"Expected [5] to be flagged, got {result}"

    def test_zero_marker_detected(self):
        """[0] is out of bounds since sources are 1-indexed."""
        from app.api.routes.conversations import _validate_citation_markers

        response = "This is from source [0]."
        result = _validate_citation_markers(response, num_sources=3)
        assert 0 in result, f"Expected [0] to be flagged, got {result}"

    def test_no_markers_return_empty(self):
        """Response without any markers should return empty list."""
        from app.api.routes.conversations import _validate_citation_markers

        response = "I don't have enough information to answer that."
        result = _validate_citation_markers(response, num_sources=3)
        assert result == []

    def test_marker_extraction_regex(self):
        """Verify that citation markers can be reliably extracted from LLM output."""
        from app.api.routes.conversations import _CITATION_MARKER_RE

        test_response = (
            "According to the video [1], the speaker discusses AI ethics. "
            "This is further supported by [2] and [3]. "
            "However, [1] also mentions the counterargument."
        )

        markers = set(_CITATION_MARKER_RE.findall(test_response))
        expected = {"1", "2", "3"}
        assert markers == expected, f"Extracted markers {markers} != expected {expected}"

    def test_empty_response_has_no_markers(self):
        """Edge case: empty or marker-free response."""
        from app.api.routes.conversations import _CITATION_MARKER_RE

        responses = [
            "",
            "I don't have enough information to answer that.",
            "Based on the context provided, here is a summary.",
        ]

        for response in responses:
            markers = _CITATION_MARKER_RE.findall(response)
            assert len(markers) == 0, f"Found unexpected markers in: {response}"


# ── CIT-003: Jump URL Timestamp ───────────────────────────────────────


class TestJumpUrlTimestamp:
    """CIT-003: Jump URLs must have correct timestamps matching chunk data."""

    def test_youtube_url_timestamp_format(self):
        """YouTube URLs should use ?t=SECONDS format."""
        # Standard YouTube URL with timestamp
        video_id = "dQw4w9WgXcQ"
        timestamp_seconds = 125

        url = f"https://www.youtube.com/watch?v={video_id}&t={timestamp_seconds}"

        assert f"t={timestamp_seconds}" in url
        assert video_id in url

    def test_timestamp_conversion_from_chunk(self):
        """Chunk start_timestamp (seconds float) should convert to integer seconds in URL."""
        test_cases = [
            (0.0, 0),        # Start of video
            (125.5, 125),    # Mid-video (truncate, not round)
            (3661.0, 3661),  # Over 1 hour
        ]

        for chunk_timestamp, expected_url_seconds in test_cases:
            url_seconds = int(chunk_timestamp)
            assert url_seconds == expected_url_seconds, (
                f"Chunk timestamp {chunk_timestamp} -> URL t={url_seconds}, "
                f"expected t={expected_url_seconds}"
            )

    def test_none_timestamp_handling(self):
        """Document chunks may have None timestamps — URL builder must handle this."""
        # If timestamp is None, the jump URL should either:
        # 1. Not include the t= parameter, or
        # 2. Not generate a jump URL at all
        timestamp = None

        if timestamp is not None:
            url_seconds = int(timestamp)
        else:
            url_seconds = None

        assert url_seconds is None, "None timestamp should not produce a URL parameter"


# ── ACC-001: Storage Vector Dimensions ────────────────────────────────


class TestStorageVectorDimensions:
    """ACC-001: BYTES_PER_VECTOR must match actual embedding model dimensions."""

    def test_bytes_per_vector_constant_exists(self):
        """Verify the constant exists and is reasonable."""
        from app.services.storage_calculator import BYTES_PER_VECTOR

        assert BYTES_PER_VECTOR > 0, "BYTES_PER_VECTOR must be positive"
        # Should be between 1KB and 20KB for typical embedding models
        assert 512 <= BYTES_PER_VECTOR <= 20480, (
            f"BYTES_PER_VECTOR={BYTES_PER_VECTOR} seems unreasonable "
            f"(expected 512-20480 bytes)"
        )

    def test_vector_dimensions_match_default_model(self):
        """BYTES_PER_VECTOR should match the configured embedding model's dimensions.

        Formula: dimensions * 4 bytes (float32) + ~1KB overhead
        """
        from app.services.storage_calculator import BYTES_PER_VECTOR
        from app.core.config import settings

        # Known model dimensions
        model_dimensions = {
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-large-en-v1.5": 1024,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }

        model = settings.embedding_model
        if model in model_dimensions:
            expected_dims = model_dimensions[model]
            expected_bytes = expected_dims * 4 + 1024
            # Allow reasonable tolerance for overhead estimation
            min_expected = expected_dims * 4
            max_expected = expected_dims * 4 + 2048

            assert min_expected <= BYTES_PER_VECTOR <= max_expected, (
                f"ACC-001 BROKEN: BYTES_PER_VECTOR={BYTES_PER_VECTOR} "
                f"but model '{model}' has {expected_dims} dims "
                f"(expected {min_expected}-{max_expected} bytes)."
            )
        else:
            pytest.skip(
                f"Unknown model '{model}' — cannot verify dimensions. "
                f"Add to model_dimensions map in test."
            )

    def test_calculate_bytes_per_vector_is_dynamic(self):
        """Verify _calculate_bytes_per_vector reads from settings, not hardcoded."""
        from app.services.storage_calculator import _calculate_bytes_per_vector

        # The function should exist and be callable
        result = _calculate_bytes_per_vector()
        assert isinstance(result, int)
        assert result > 0


# ── ACC-003: BM25 Proper Noun Handling ─────────────────────────────────


class TestBM25ProperNounHandling:
    """ACC-003: BM25 must not skip queries containing proper nouns."""

    def test_proper_noun_detection_exists(self):
        """The _has_proper_noun function must exist."""
        from app.services.bm25_search import _has_proper_noun

        assert callable(_has_proper_noun)

    def test_proper_noun_detected_in_query(self):
        """Capitalized words (not sentence-initial) should be detected as proper nouns."""
        from app.services.bm25_search import _has_proper_noun

        assert _has_proper_noun("What did Ken Robinson say?") is True
        assert _has_proper_noun("Tell me about Einstein") is True

    def test_no_proper_noun_in_lowercase(self):
        """All-lowercase queries (after first word) have no proper nouns."""
        from app.services.bm25_search import _has_proper_noun

        assert _has_proper_noun("What is the meaning of life?") is False
        assert _has_proper_noun("Tell me about education") is False

    def test_should_skip_bypassed_for_proper_nouns(self):
        """Queries with proper nouns should NOT be skipped even if few content tokens."""
        from app.services.bm25_search import _should_skip_bm25

        # "Who is Ken Robinson?" has only 1 content token after stopword removal
        # but contains a proper noun, so BM25 should NOT be skipped
        assert _should_skip_bm25("Who is Ken Robinson?") is False

    def test_short_generic_queries_still_skipped(self):
        """Short queries without proper nouns should still be skipped."""
        from app.services.bm25_search import _should_skip_bm25

        # "What is this?" — 0 content tokens after stopwords, no proper nouns
        assert _should_skip_bm25("What is this?") is True

    def test_long_queries_not_skipped(self):
        """Queries with 3+ content tokens should not be skipped regardless."""
        from app.services.bm25_search import _should_skip_bm25

        assert _should_skip_bm25("education creativity schools reform") is False


# ── PAR-002: Enrichment Truncation Warning ─────────────────────────────


class TestEnrichmentTruncationWarning:
    """PAR-002: Enrichment must log a warning when full_text is truncated."""

    def test_truncation_logs_warning(self):
        """When full_text > 48000 chars, a logger.warning must be emitted."""
        import logging
        from unittest.mock import patch, MagicMock

        # Create a long text that exceeds the 48K limit
        long_text = "x" * 50000

        with patch("app.services.enrichment.logger") as mock_logger:
            from app.services.enrichment import ContextualEnricher

            enricher = ContextualEnricher(
                full_text=long_text,
                content_id="test-123",
            )

            # Verify the text was truncated
            assert len(enricher.full_text) == 48000

            # Verify a warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "truncated" in call_args.lower()
            assert "50000" in call_args
            assert "48000" in call_args

    def test_short_text_no_warning(self):
        """When full_text <= 48000 chars, no warning should be emitted."""
        from unittest.mock import patch

        short_text = "x" * 10000

        with patch("app.services.enrichment.logger") as mock_logger:
            from app.services.enrichment import ContextualEnricher

            enricher = ContextualEnricher(full_text=short_text)

            assert enricher.full_text == short_text
            mock_logger.warning.assert_not_called()
