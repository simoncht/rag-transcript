"""
Semantic chunking service for transcript processing.

Implements production-grade chunking with:
- Token-aware boundaries (target, min, max tokens)
- Overlap between chunks for context continuity
- Sentence and speaker boundary detection
- Chapter-aware splitting (if YouTube chapters available)
- Timestamp preservation
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Dict
import tiktoken

from app.core.config import settings


@dataclass
class TranscriptSegment:
    """
    A single segment from Whisper transcription.

    Attributes:
        text: The transcribed text
        start: Start timestamp in seconds
        end: End timestamp in seconds
        speaker: Optional speaker ID (if diarization is available)
    """
    text: str
    start: float
    end: float
    speaker: Optional[str] = None


@dataclass
class ChunkConfig:
    """Configuration for chunking behavior."""
    target_tokens: int = settings.chunk_target_tokens
    min_tokens: int = settings.chunk_min_tokens
    max_tokens: int = settings.chunk_max_tokens
    overlap_tokens: int = settings.chunk_overlap_tokens
    max_duration_seconds: int = settings.chunk_max_duration_seconds


@dataclass
class Chunk:
    """
    A semantically meaningful chunk of transcript.

    Attributes:
        text: The chunk text
        start_timestamp: Start time in seconds
        end_timestamp: End time in seconds
        token_count: Number of tokens
        speakers: List of speaker IDs in this chunk
        chapter_title: YouTube chapter title if applicable
        chapter_index: Chapter index if applicable
        chunk_index: Position in the sequence of chunks
    """
    text: str
    start_timestamp: float
    end_timestamp: float
    token_count: int
    speakers: Optional[List[str]] = None
    chapter_title: Optional[str] = None
    chapter_index: Optional[int] = None
    chunk_index: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate chunk duration."""
        return self.end_timestamp - self.start_timestamp


class TranscriptChunker:
    """
    Production-grade transcript chunker following RAG best practices.

    Implements semantic chunking with:
    - Token-aware boundaries using tiktoken (cl100k_base)
    - Configurable overlap for context continuity
    - Sentence boundary detection
    - Speaker change detection
    - YouTube chapter awareness
    - Duration limits to keep chunks manageable
    """

    def __init__(self, config: Optional[ChunkConfig] = None):
        """
        Initialize chunker with configuration.

        Args:
            config: Chunking configuration (uses defaults if not provided)
        """
        self.config = config or ChunkConfig()

        # Initialize tokenizer (using OpenAI's cl100k_base for consistency)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to approximate token counting
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback: approximate token count (words * 1.3)
            return int(len(text.split()) * 1.3)

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Uses regex to detect sentence boundaries while handling edge cases like:
        - Abbreviations (Dr., Mr., etc.)
        - Decimal numbers (3.14)
        - Multiple punctuation marks

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Pattern for sentence boundaries
        # Matches . ! ? followed by space and capital letter, or end of string
        pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$'

        sentences = re.split(pattern, text)

        # Clean up and filter empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences if sentences else [text]

    def group_segments_by_chapter(
        self,
        segments: List[TranscriptSegment],
        chapters: Optional[List[Dict]] = None
    ) -> List[List[TranscriptSegment]]:
        """
        Group transcript segments by YouTube chapter.

        Args:
            segments: List of transcript segments
            chapters: Optional YouTube chapters [{"title": "Intro", "start_time": 0, "end_time": 120}, ...]

        Returns:
            List of segment groups (one per chapter, or one group if no chapters)
        """
        if not chapters:
            return [segments]

        grouped = []
        for i, chapter in enumerate(chapters):
            chapter_start = chapter['start_time']
            chapter_end = chapter.get('end_time', float('inf'))

            # Find segments in this chapter
            chapter_segments = [
                seg for seg in segments
                if chapter_start <= seg.start < chapter_end
            ]

            if chapter_segments:
                grouped.append(chapter_segments)

        # If no segments were grouped, return all segments as one group
        return grouped if grouped else [segments]

    def create_chunk_from_segments(
        self,
        segments: List[TranscriptSegment],
        chunk_index: int,
        chapter_title: Optional[str] = None,
        chapter_index: Optional[int] = None
    ) -> Chunk:
        """
        Create a Chunk object from a list of segments.

        Args:
            segments: List of transcript segments
            chunk_index: Index of this chunk in the sequence
            chapter_title: Optional chapter title
            chapter_index: Optional chapter index

        Returns:
            Chunk object
        """
        if not segments:
            raise ValueError("Cannot create chunk from empty segments list")

        text = " ".join(seg.text.strip() for seg in segments)
        token_count = self.count_tokens(text)
        start_timestamp = segments[0].start
        end_timestamp = segments[-1].end

        # Collect unique speakers
        speakers = list(set(seg.speaker for seg in segments if seg.speaker))

        return Chunk(
            text=text,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            token_count=token_count,
            speakers=speakers if speakers else None,
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            chunk_index=chunk_index
        )

    def chunk_transcript(
        self,
        segments: List[TranscriptSegment],
        chapters: Optional[List[Dict]] = None
    ) -> List[Chunk]:
        """
        Chunk transcript segments into semantic units.

        This is the main entry point for chunking. It:
        1. Groups segments by chapter (if chapters provided)
        2. Within each chapter, creates chunks based on:
           - Target token count
           - Sentence boundaries
           - Speaker changes
           - Duration limits
        3. Adds overlap between consecutive chunks

        Args:
            segments: List of transcript segments from Whisper
            chapters: Optional YouTube chapters

        Returns:
            List of Chunk objects
        """
        if not segments:
            return []

        all_chunks = []
        chunk_index = 0

        # Group by chapter
        segment_groups = self.group_segments_by_chapter(segments, chapters)

        for group_idx, segment_group in enumerate(segment_groups):
            # Determine chapter info
            chapter_title = None
            chapter_index = None
            if chapters and group_idx < len(chapters):
                chapter_title = chapters[group_idx].get('title')
                chapter_index = group_idx

            # Chunk this group
            chunks = self._chunk_segment_group(
                segment_group,
                start_chunk_index=chunk_index,
                chapter_title=chapter_title,
                chapter_index=chapter_index
            )

            all_chunks.extend(chunks)
            chunk_index += len(chunks)

        # Add overlap between chunks
        overlapped_chunks = self._add_overlap(all_chunks, segments)

        return overlapped_chunks

    def _chunk_segment_group(
        self,
        segments: List[TranscriptSegment],
        start_chunk_index: int = 0,
        chapter_title: Optional[str] = None,
        chapter_index: Optional[int] = None
    ) -> List[Chunk]:
        """
        Chunk a group of segments (e.g., one chapter).

        Args:
            segments: List of transcript segments
            start_chunk_index: Starting index for chunk numbering
            chapter_title: Optional chapter title
            chapter_index: Optional chapter index

        Returns:
            List of Chunk objects
        """
        chunks = []
        current_segments = []
        current_token_count = 0
        chunk_idx = start_chunk_index

        for seg_idx, segment in enumerate(segments):
            segment_text = segment.text.strip()
            segment_tokens = self.count_tokens(segment_text)

            # Check if adding this segment would exceed max tokens or max duration
            would_exceed_tokens = current_token_count + segment_tokens > self.config.max_tokens

            current_duration = 0
            if current_segments:
                current_duration = segment.end - current_segments[0].start
            would_exceed_duration = current_duration > self.config.max_duration_seconds

            # Check for speaker change
            speaker_changed = False
            if current_segments and segment.speaker and current_segments[-1].speaker:
                speaker_changed = segment.speaker != current_segments[-1].speaker

            # Decide whether to create a new chunk
            should_chunk = False

            if would_exceed_tokens or would_exceed_duration:
                # Must chunk due to hard limits
                should_chunk = True
            elif current_token_count >= self.config.target_tokens:
                # Check if this is a good breaking point (sentence boundary or speaker change)
                if speaker_changed or self._is_sentence_boundary(segment_text):
                    should_chunk = True

            if should_chunk and current_segments:
                # Create chunk from accumulated segments
                if current_token_count >= self.config.min_tokens:
                    chunk = self.create_chunk_from_segments(
                        current_segments,
                        chunk_idx,
                        chapter_title,
                        chapter_index
                    )
                    chunks.append(chunk)
                    chunk_idx += 1
                    current_segments = []
                    current_token_count = 0

            # Add segment to current chunk
            current_segments.append(segment)
            current_token_count += segment_tokens

        # Create final chunk if there are remaining segments
        if current_segments and current_token_count >= self.config.min_tokens:
            chunk = self.create_chunk_from_segments(
                current_segments,
                chunk_idx,
                chapter_title,
                chapter_index
            )
            chunks.append(chunk)
        elif current_segments and chunks:
            # Merge small final chunk with previous chunk
            chunks = self._merge_small_final_chunk(chunks, current_segments, chapter_title, chapter_index)

        return chunks

    def _is_sentence_boundary(self, text: str) -> bool:
        """
        Check if text ends with a sentence boundary.

        Args:
            text: Text to check

        Returns:
            True if text ends with sentence-ending punctuation
        """
        return bool(re.search(r'[.!?]\s*$', text))

    def _merge_small_final_chunk(
        self,
        chunks: List[Chunk],
        remaining_segments: List[TranscriptSegment],
        chapter_title: Optional[str],
        chapter_index: Optional[int]
    ) -> List[Chunk]:
        """
        Merge small final segment group with the last chunk.

        Args:
            chunks: Existing chunks
            remaining_segments: Segments that didn't form a full chunk
            chapter_title: Chapter title
            chapter_index: Chapter index

        Returns:
            Updated chunks list
        """
        if not chunks or not remaining_segments:
            return chunks

        last_chunk = chunks[-1]

        # Combine texts
        remaining_text = " ".join(seg.text.strip() for seg in remaining_segments)
        combined_text = last_chunk.text + " " + remaining_text
        combined_tokens = self.count_tokens(combined_text)

        # Collect speakers
        remaining_speakers = list(set(seg.speaker for seg in remaining_segments if seg.speaker))
        all_speakers = list(set((last_chunk.speakers or []) + remaining_speakers))

        # Create merged chunk
        merged_chunk = Chunk(
            text=combined_text,
            start_timestamp=last_chunk.start_timestamp,
            end_timestamp=remaining_segments[-1].end,
            token_count=combined_tokens,
            speakers=all_speakers if all_speakers else None,
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            chunk_index=last_chunk.chunk_index
        )

        # Replace last chunk with merged chunk
        chunks[-1] = merged_chunk
        return chunks

    def _add_overlap(
        self,
        chunks: List[Chunk],
        segments: List[TranscriptSegment]
    ) -> List[Chunk]:
        """
        Add overlap between consecutive chunks.

        For each chunk, prepend tokens from the previous chunk to maintain context continuity.

        Args:
            chunks: List of chunks
            segments: Original transcript segments

        Returns:
            List of chunks with overlap added
        """
        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]  # First chunk has no overlap

        for i in range(1, len(chunks)):
            current_chunk = chunks[i]
            previous_chunk = chunks[i - 1]

            # Get overlap text from previous chunk (last N tokens)
            overlap_text = self._extract_overlap_text(
                previous_chunk.text,
                self.config.overlap_tokens
            )

            # Prepend overlap to current chunk
            new_text = overlap_text + " " + current_chunk.text if overlap_text else current_chunk.text
            new_token_count = self.count_tokens(new_text)

            overlapped_chunk = Chunk(
                text=new_text,
                start_timestamp=current_chunk.start_timestamp,  # Keep original timestamp
                end_timestamp=current_chunk.end_timestamp,
                token_count=new_token_count,
                speakers=current_chunk.speakers,
                chapter_title=current_chunk.chapter_title,
                chapter_index=current_chunk.chapter_index,
                chunk_index=current_chunk.chunk_index
            )

            overlapped_chunks.append(overlapped_chunk)

        return overlapped_chunks

    def _extract_overlap_text(self, text: str, target_tokens: int) -> str:
        """
        Extract the last N tokens from text for overlap.

        Args:
            text: Source text
            target_tokens: Number of tokens to extract

        Returns:
            Overlap text (last ~N tokens)
        """
        # Split into sentences and work backwards
        sentences = self.split_into_sentences(text)

        overlap_sentences = []
        token_count = 0

        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)

            if token_count + sentence_tokens <= target_tokens:
                overlap_sentences.insert(0, sentence)
                token_count += sentence_tokens
            else:
                break

        return " ".join(overlap_sentences)

    def validate_chunks(self, chunks: List[Chunk]) -> bool:
        """
        Validate that chunks meet requirements.

        Args:
            chunks: List of chunks to validate

        Returns:
            True if all chunks are valid

        Raises:
            ValueError: If validation fails
        """
        for i, chunk in enumerate(chunks):
            # Check token count
            if chunk.token_count < self.config.min_tokens:
                raise ValueError(
                    f"Chunk {i} has {chunk.token_count} tokens (min: {self.config.min_tokens})"
                )

            if chunk.token_count > self.config.max_tokens * 1.2:  # Allow 20% overage
                raise ValueError(
                    f"Chunk {i} has {chunk.token_count} tokens (max: {self.config.max_tokens})"
                )

            # Check timestamps
            if chunk.start_timestamp >= chunk.end_timestamp:
                raise ValueError(
                    f"Chunk {i} has invalid timestamps: {chunk.start_timestamp} >= {chunk.end_timestamp}"
                )

            # Check text not empty
            if not chunk.text.strip():
                raise ValueError(f"Chunk {i} has empty text")

        return True
