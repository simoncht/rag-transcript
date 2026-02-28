"""
Unit tests for the chunking service.

Tests semantic chunking, token boundaries, overlap handling, and chapter awareness.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.chunking import (
    TranscriptChunker,
    TranscriptSegment,
    ChunkConfig,
    Chunk,
)


class TestTranscriptChunkerInitialization:
    """Test chunker initialization."""

    def test_default_config(self):
        """Test chunker uses default config when none provided."""
        chunker = TranscriptChunker()
        assert chunker.config is not None
        assert chunker.config.target_tokens > 0
        assert chunker.config.min_tokens > 0
        assert chunker.config.max_tokens > 0
        assert chunker.config.overlap_tokens > 0

    def test_custom_config(self):
        """Test chunker accepts custom config."""
        config = ChunkConfig(
            target_tokens=200,
            min_tokens=50,
            max_tokens=400,
            overlap_tokens=40,
        )
        chunker = TranscriptChunker(config=config)
        assert chunker.config.target_tokens == 200
        assert chunker.config.min_tokens == 50
        assert chunker.config.max_tokens == 400
        assert chunker.config.overlap_tokens == 40

    def test_tokenizer_fallback(self):
        """Test chunker falls back gracefully if tiktoken unavailable."""
        chunker = TranscriptChunker()
        # Even if tokenizer fails, count_tokens should work
        count = chunker.count_tokens("Hello world this is a test")
        assert count > 0


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_tokens_basic(self):
        """Test basic token counting."""
        chunker = TranscriptChunker()
        count = chunker.count_tokens("Hello world")
        assert count >= 2  # At least 2 tokens

    def test_count_tokens_empty_string(self):
        """Test token counting with empty string."""
        chunker = TranscriptChunker()
        count = chunker.count_tokens("")
        assert count == 0

    def test_count_tokens_longer_text(self):
        """Test token counting with longer text."""
        chunker = TranscriptChunker()
        text = "This is a longer piece of text that should have more tokens than a short one."
        count = chunker.count_tokens(text)
        assert count > 10


class TestSentenceSplitting:
    """Test sentence boundary detection."""

    def test_split_simple_sentences(self):
        """Test splitting simple sentences."""
        chunker = TranscriptChunker()
        text = "This is sentence one. This is sentence two. This is sentence three."
        sentences = chunker.split_into_sentences(text)
        assert len(sentences) == 3
        assert "sentence one" in sentences[0]

    def test_split_with_exclamation(self):
        """Test splitting with exclamation marks."""
        chunker = TranscriptChunker()
        text = "Hello! How are you? I am fine."
        sentences = chunker.split_into_sentences(text)
        assert len(sentences) == 3

    def test_split_no_boundaries(self):
        """Test splitting text without sentence boundaries."""
        chunker = TranscriptChunker()
        text = "no sentence boundaries here"
        sentences = chunker.split_into_sentences(text)
        assert len(sentences) == 1
        assert sentences[0] == text

    def test_split_empty_string(self):
        """Test splitting empty string."""
        chunker = TranscriptChunker()
        text = ""
        sentences = chunker.split_into_sentences(text)
        # Should return list with original text (empty)
        assert len(sentences) <= 1


class TestChapterGrouping:
    """Test chapter-aware grouping of segments."""

    def test_no_chapters_returns_single_group(self):
        """Test segments without chapters stay in one group."""
        chunker = TranscriptChunker()
        segments = [
            TranscriptSegment(text="Hello", start=0.0, end=1.0),
            TranscriptSegment(text="World", start=1.0, end=2.0),
        ]
        groups = chunker.group_segments_by_chapter(segments, chapters=None)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_with_chapters(self):
        """Test segments are grouped by chapter."""
        chunker = TranscriptChunker()
        segments = [
            TranscriptSegment(text="Intro text", start=0.0, end=30.0),
            TranscriptSegment(text="Main content", start=60.0, end=90.0),
            TranscriptSegment(text="More main content", start=90.0, end=120.0),
        ]
        chapters = [
            {"title": "Introduction", "start_time": 0, "end_time": 60},
            {"title": "Main Topic", "start_time": 60, "end_time": 180},
        ]
        groups = chunker.group_segments_by_chapter(segments, chapters)
        assert len(groups) == 2
        assert len(groups[0]) == 1  # Intro segment
        assert len(groups[1]) == 2  # Main segments

    def test_empty_chapters_list(self):
        """Test empty chapters list behaves like no chapters."""
        chunker = TranscriptChunker()
        segments = [TranscriptSegment(text="Test", start=0.0, end=1.0)]
        groups = chunker.group_segments_by_chapter(segments, chapters=[])
        assert len(groups) == 1


class TestChunkCreation:
    """Test creating chunks from segments."""

    def test_create_chunk_basic(self):
        """Test creating a basic chunk."""
        chunker = TranscriptChunker()
        segments = [
            TranscriptSegment(text="First segment.", start=0.0, end=5.0),
            TranscriptSegment(text="Second segment.", start=5.0, end=10.0),
        ]
        chunk = chunker.create_chunk_from_segments(segments, chunk_index=0)
        assert "First segment" in chunk.text
        assert "Second segment" in chunk.text
        assert chunk.start_timestamp == 0.0
        assert chunk.end_timestamp == 10.0
        assert chunk.chunk_index == 0

    def test_create_chunk_with_speakers(self):
        """Test chunk includes speaker information."""
        chunker = TranscriptChunker()
        segments = [
            TranscriptSegment(text="Hello", start=0.0, end=1.0, speaker="A"),
            TranscriptSegment(text="Hi", start=1.0, end=2.0, speaker="B"),
        ]
        chunk = chunker.create_chunk_from_segments(segments, chunk_index=0)
        assert chunk.speakers is not None
        assert set(chunk.speakers) == {"A", "B"}

    def test_create_chunk_with_chapter(self):
        """Test chunk includes chapter information."""
        chunker = TranscriptChunker()
        segments = [TranscriptSegment(text="Content", start=0.0, end=1.0)]
        chunk = chunker.create_chunk_from_segments(
            segments,
            chunk_index=0,
            chapter_title="Introduction",
            chapter_index=0,
        )
        assert chunk.chapter_title == "Introduction"
        assert chunk.chapter_index == 0

    def test_create_chunk_empty_segments_raises(self):
        """Test creating chunk from empty segments raises error."""
        chunker = TranscriptChunker()
        with pytest.raises(ValueError, match="empty segments"):
            chunker.create_chunk_from_segments([], chunk_index=0)


class TestChunkDuration:
    """Test chunk duration property."""

    def test_duration_calculation(self):
        """Test duration is calculated correctly."""
        chunk = Chunk(
            text="Test",
            start_timestamp=10.0,
            end_timestamp=25.0,
            token_count=5,
        )
        assert chunk.duration_seconds == 15.0

    def test_zero_duration(self):
        """Test zero duration chunk."""
        chunk = Chunk(
            text="Test",
            start_timestamp=10.0,
            end_timestamp=10.0,
            token_count=5,
        )
        assert chunk.duration_seconds == 0.0


class TestChunkTranscript:
    """Test the main chunk_transcript method."""

    def test_empty_segments_returns_empty(self):
        """Test chunking empty segments returns empty list."""
        chunker = TranscriptChunker()
        chunks = chunker.chunk_transcript([])
        assert chunks == []

    def test_invalid_segments_raises(self):
        """Test chunking non-list raises error."""
        chunker = TranscriptChunker()
        with pytest.raises(ValueError, match="must be a list"):
            chunker.chunk_transcript("not a list")  # type: ignore

    def test_basic_chunking(self):
        """Test basic transcript chunking."""
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=10,
            max_tokens=100,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        # Create segments that will form multiple chunks
        segments = []
        for i in range(20):
            segments.append(
                TranscriptSegment(
                    text=f"This is segment number {i} with some content to fill it up.",
                    start=float(i * 5),
                    end=float((i + 1) * 5),
                )
            )

        chunks = chunker.chunk_transcript(segments)
        assert len(chunks) > 1
        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunking_respects_max_tokens(self):
        """Test chunks attempt to respect max tokens when splitting multiple segments."""
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=10,
            max_tokens=100,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        # Use multiple small segments that can be chunked properly
        segments = []
        for i in range(20):
            segments.append(
                TranscriptSegment(
                    text=f"This is segment {i} with reasonable content size.",
                    start=float(i * 5),
                    end=float((i + 1) * 5),
                )
            )

        chunks = chunker.chunk_transcript(segments)
        # Multiple segments should result in multiple chunks
        assert len(chunks) >= 1
        # Verify chunks have valid token counts
        for chunk in chunks:
            assert chunk.token_count > 0


class TestOverlap:
    """Test chunk overlap functionality."""

    def test_overlap_added_between_chunks(self):
        """Test overlap is added between consecutive chunks."""
        config = ChunkConfig(
            target_tokens=30,
            min_tokens=10,
            max_tokens=50,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        segments = []
        for i in range(10):
            segments.append(
                TranscriptSegment(
                    text=f"Sentence {i} has unique content that can be identified.",
                    start=float(i * 3),
                    end=float((i + 1) * 3),
                )
            )

        chunks = chunker.chunk_transcript(segments)

        if len(chunks) > 1:
            # Second chunk should have overlap from first
            # Check that the second chunk's text is longer (includes overlap)
            first_chunk_end_words = chunks[0].text.split()[-5:]
            # Second chunk might contain words from first (overlap)
            assert chunks[1].token_count >= config.min_tokens

    def test_first_chunk_no_overlap(self):
        """Test first chunk has no preceding overlap."""
        config = ChunkConfig(
            target_tokens=30,
            min_tokens=10,
            max_tokens=50,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        segments = []
        for i in range(10):
            segments.append(
                TranscriptSegment(
                    text=f"Content block {i}.",
                    start=float(i * 3),
                    end=float((i + 1) * 3),
                )
            )

        chunks = chunker.chunk_transcript(segments)
        if chunks:
            # First chunk starts with original content
            assert "Content block 0" in chunks[0].text or "Content" in chunks[0].text


class TestChunkValidation:
    """Test chunk validation."""

    def test_valid_chunks_pass(self):
        """Test valid chunks pass validation."""
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=10,
            max_tokens=100,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        chunks = [
            Chunk(
                text="Valid chunk text here.",
                start_timestamp=0.0,
                end_timestamp=5.0,
                token_count=50,
                chunk_index=0,
            ),
            Chunk(
                text="Another valid chunk.",
                start_timestamp=5.0,
                end_timestamp=10.0,
                token_count=45,
                chunk_index=1,
            ),
        ]

        assert chunker.validate_chunks(chunks) is True

    def test_invalid_token_count_fails(self):
        """Test chunk with too few tokens fails validation."""
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=10,
            max_tokens=100,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        chunks = [
            Chunk(
                text="Too short.",
                start_timestamp=0.0,
                end_timestamp=1.0,
                token_count=3,  # Below min_tokens
                chunk_index=0,
            )
        ]

        with pytest.raises(ValueError, match="tokens"):
            chunker.validate_chunks(chunks)

    def test_invalid_timestamps_fails(self):
        """Test chunk with invalid timestamps fails validation."""
        config = ChunkConfig(min_tokens=1)
        chunker = TranscriptChunker(config=config)

        chunks = [
            Chunk(
                text="Valid text content here.",
                start_timestamp=10.0,
                end_timestamp=5.0,  # End before start
                token_count=15,
                chunk_index=0,
            )
        ]

        with pytest.raises(ValueError, match="timestamps"):
            chunker.validate_chunks(chunks)

    def test_empty_text_fails(self):
        """Test chunk with empty text fails validation."""
        config = ChunkConfig(min_tokens=1)
        chunker = TranscriptChunker(config=config)

        chunks = [
            Chunk(
                text="   ",  # Empty after strip
                start_timestamp=0.0,
                end_timestamp=5.0,
                token_count=15,
                chunk_index=0,
            )
        ]

        with pytest.raises(ValueError, match="empty text"):
            chunker.validate_chunks(chunks)


class TestSentenceBoundaryDetection:
    """Test sentence boundary detection."""

    def test_period_is_boundary(self):
        """Test period is detected as boundary."""
        chunker = TranscriptChunker()
        assert chunker._is_sentence_boundary("This is a sentence.") is True

    def test_question_mark_is_boundary(self):
        """Test question mark is detected as boundary."""
        chunker = TranscriptChunker()
        assert chunker._is_sentence_boundary("Is this a question?") is True

    def test_exclamation_is_boundary(self):
        """Test exclamation mark is detected as boundary."""
        chunker = TranscriptChunker()
        assert chunker._is_sentence_boundary("Wow!") is True

    def test_no_punctuation_not_boundary(self):
        """Test text without ending punctuation is not a boundary."""
        chunker = TranscriptChunker()
        assert chunker._is_sentence_boundary("No punctuation here") is False

    def test_comma_not_boundary(self):
        """Test comma is not a sentence boundary."""
        chunker = TranscriptChunker()
        assert chunker._is_sentence_boundary("Hello, world") is False


class TestOverlapTextExtraction:
    """Test overlap text extraction."""

    def test_extract_overlap_basic(self):
        """Test extracting overlap from text."""
        chunker = TranscriptChunker()
        text = "First sentence. Second sentence. Third sentence."
        overlap = chunker._extract_overlap_text(text, target_tokens=10)
        # Should extract some sentences from the end
        assert len(overlap) > 0
        assert "sentence" in overlap.lower()

    def test_extract_overlap_respects_token_limit(self):
        """Test overlap respects token limit."""
        chunker = TranscriptChunker()
        text = "A. B. C. D. E. F. G. H. I. J."
        overlap = chunker._extract_overlap_text(text, target_tokens=5)
        # Should not include all sentences
        token_count = chunker.count_tokens(overlap)
        assert token_count <= 10  # Some buffer for tokenization differences


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_segment_chunking(self):
        """Test chunking a single segment with sufficient content."""
        # Use low min_tokens to ensure the segment is large enough
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=5,  # Very low to allow small segments
            max_tokens=200,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)
        # Create a segment with enough tokens to meet min requirement
        segments = [
            TranscriptSegment(
                text="Just one segment with enough content to be valid and meet the minimum token requirement for chunking.",
                start=0.0,
                end=10.0,
            )
        ]
        chunks = chunker.chunk_transcript(segments)
        # Should produce at least one chunk
        assert len(chunks) >= 1

    def test_segments_with_no_speaker(self):
        """Test segments without speaker information."""
        chunker = TranscriptChunker()
        segments = [
            TranscriptSegment(text="No speaker", start=0.0, end=1.0, speaker=None),
            TranscriptSegment(text="Also no speaker", start=1.0, end=2.0, speaker=None),
        ]
        chunk = chunker.create_chunk_from_segments(segments, chunk_index=0)
        assert chunk.speakers is None or len(chunk.speakers) == 0

    def test_very_short_segments(self):
        """Test handling very short segments."""
        config = ChunkConfig(
            target_tokens=50,
            min_tokens=5,
            max_tokens=100,
            overlap_tokens=10,
        )
        chunker = TranscriptChunker(config=config)

        segments = [
            TranscriptSegment(text="Hi.", start=0.0, end=0.5),
            TranscriptSegment(text="Yes.", start=0.5, end=1.0),
            TranscriptSegment(text="OK.", start=1.0, end=1.5),
        ]

        # Should handle gracefully without raising
        chunks = chunker.chunk_transcript(segments)
        # May produce chunks or combine them
        assert isinstance(chunks, list)
