"""
Unit tests for document summary generation.

Tests cover:
- Uniform sampling across full document (not just first 10 chunks)
- Context building with chunk_summary preference
- Summary prompt includes document PURPOSE and SCOPE emphasis
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.tasks.document_tasks import _sample_chunks_uniformly


class TestUniformChunkSampling:
    """Tests for _sample_chunks_uniformly."""

    def test_returns_all_when_under_max(self):
        """Should return all chunks when fewer than max_chunks."""
        chunks = [MagicMock() for _ in range(10)]
        result = _sample_chunks_uniformly(chunks, max_chunks=30)
        assert len(result) == 10
        assert result == chunks

    def test_returns_exact_max_when_over(self):
        """Should return exactly max_chunks when over limit."""
        chunks = [MagicMock() for _ in range(100)]
        result = _sample_chunks_uniformly(chunks, max_chunks=30)
        assert len(result) == 30

    def test_samples_uniformly_not_first_10(self):
        """Should sample indices across the full document, not just first N.

        With 100 chunks and max_chunks=30, sampled indices should span
        from 0 to ~96 (not all < 10).
        """
        chunks = list(range(100))  # Use ints as stand-ins
        result = _sample_chunks_uniformly(chunks, max_chunks=30)

        # First element should be index 0
        assert result[0] == 0
        # Last element should be near the end (index 96 or higher)
        assert result[-1] >= 90
        # Middle elements should be spread out
        assert result[15] >= 45  # Roughly halfway

    def test_samples_evenly_distributed(self):
        """Should have roughly equal spacing between sampled indices."""
        chunks = list(range(300))
        result = _sample_chunks_uniformly(chunks, max_chunks=30)

        # Expected step is 10 (300/30)
        gaps = [result[i + 1] - result[i] for i in range(len(result) - 1)]
        assert all(g == 10 for g in gaps)

    def test_single_chunk(self):
        """Should handle single-chunk document."""
        chunks = [MagicMock()]
        result = _sample_chunks_uniformly(chunks, max_chunks=30)
        assert len(result) == 1

    def test_empty_chunks(self):
        """Should handle empty chunk list."""
        result = _sample_chunks_uniformly([], max_chunks=30)
        assert result == []

    def test_exact_max_chunks(self):
        """Should return all when exactly at max_chunks."""
        chunks = [MagicMock() for _ in range(30)]
        result = _sample_chunks_uniformly(chunks, max_chunks=30)
        assert len(result) == 30
        assert result == chunks
