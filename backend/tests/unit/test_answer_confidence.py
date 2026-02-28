"""
Unit tests for answer confidence computation.

Tests the confidence level calculation from retrieval signals.
Confidence is computed inline in conversations.py send_message_stream
but we test the logic in isolation here.
"""

import pytest


def compute_confidence(avg_relevance: float, chunk_count: int, unique_videos: int) -> dict:
    """
    Extracted confidence computation logic from conversations.py send_message_stream.
    This mirrors the inline computation for testability.
    """
    if avg_relevance >= 0.70 and chunk_count >= 3:
        confidence_level = "strong"
    elif avg_relevance >= 0.50 or chunk_count >= 2:
        confidence_level = "moderate"
    else:
        confidence_level = "limited"

    return {
        "level": confidence_level,
        "avg_relevance": round(avg_relevance, 3),
        "chunk_count": chunk_count,
        "unique_videos": unique_videos,
    }


class TestAnswerConfidence:

    def test_strong_confidence_high_relevance_many_chunks(self):
        result = compute_confidence(avg_relevance=0.85, chunk_count=5, unique_videos=3)
        assert result["level"] == "strong"
        assert result["avg_relevance"] == 0.85
        assert result["chunk_count"] == 5
        assert result["unique_videos"] == 3

    def test_strong_confidence_at_threshold(self):
        result = compute_confidence(avg_relevance=0.70, chunk_count=3, unique_videos=1)
        assert result["level"] == "strong"

    def test_moderate_confidence_medium_relevance(self):
        result = compute_confidence(avg_relevance=0.60, chunk_count=1, unique_videos=1)
        assert result["level"] == "moderate"

    def test_moderate_confidence_multiple_chunks_low_relevance(self):
        result = compute_confidence(avg_relevance=0.40, chunk_count=2, unique_videos=1)
        assert result["level"] == "moderate"

    def test_limited_confidence_low_relevance_single_chunk(self):
        result = compute_confidence(avg_relevance=0.30, chunk_count=1, unique_videos=1)
        assert result["level"] == "limited"

    def test_limited_confidence_very_low_relevance(self):
        result = compute_confidence(avg_relevance=0.10, chunk_count=1, unique_videos=1)
        assert result["level"] == "limited"

    def test_empty_chunks_returns_limited(self):
        result = compute_confidence(avg_relevance=0.0, chunk_count=0, unique_videos=0)
        assert result["level"] == "limited"

    def test_boundary_050_relevance(self):
        # Exactly 0.50 should be moderate
        result = compute_confidence(avg_relevance=0.50, chunk_count=1, unique_videos=1)
        assert result["level"] == "moderate"

    def test_boundary_070_relevance_few_chunks(self):
        # 0.70 but only 2 chunks = moderate (needs >=3)
        result = compute_confidence(avg_relevance=0.70, chunk_count=2, unique_videos=1)
        assert result["level"] == "moderate"

    def test_high_relevance_single_chunk(self):
        # Even high relevance with 1 chunk = moderate (because 0.90 >= 0.50)
        result = compute_confidence(avg_relevance=0.90, chunk_count=1, unique_videos=1)
        assert result["level"] == "moderate"

    def test_just_below_strong_threshold(self):
        result = compute_confidence(avg_relevance=0.69, chunk_count=3, unique_videos=2)
        assert result["level"] == "moderate"
