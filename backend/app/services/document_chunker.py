"""
Document chunker service for section/page-aware chunking.

Parallel to TranscriptChunker but designed for documents:
- Uses page boundaries instead of timestamps
- Preserves section headings
- Reuses tokenizer and overlap logic from chunking.py
"""
import re
from dataclasses import dataclass
from typing import List, Optional

import tiktoken

from app.core.config import settings
from app.services.document_extractor import ExtractedPage


@dataclass
class DocumentChunk:
    """
    A semantically meaningful chunk of document text.

    Analogous to chunking.Chunk but with page/section metadata instead of timestamps.
    """

    text: str
    token_count: int
    chunk_index: int
    page_number: int  # Starting page number
    end_page_number: Optional[int] = None  # Ending page (if chunk spans pages)
    section_heading: Optional[str] = None  # Section heading this chunk belongs to
    # Kept for compatibility with the enrichment/embedding pipeline
    start_timestamp: float = 0.0
    end_timestamp: float = 0.0


class DocumentChunker:
    """
    Section/page-aware chunker for documents.

    Reuses the same tokenizer and overlap approach as TranscriptChunker.
    """

    def __init__(
        self,
        target_tokens: int = None,
        min_tokens: int = None,
        max_tokens: int = None,
        overlap_tokens: int = None,
    ):
        self.target_tokens = target_tokens or settings.chunk_target_tokens
        self.min_tokens = min_tokens or settings.chunk_min_tokens
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return int(len(text.split()) * 1.3)

    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        pattern = r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$"
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()] or [text]

    def chunk_document(self, pages: List[ExtractedPage]) -> List[DocumentChunk]:
        """
        Chunk extracted document pages into semantic units.

        Strategy:
        1. Process pages sequentially
        2. Accumulate text until target token count
        3. Break at sentence boundaries
        4. Respect page boundaries as soft breaks
        5. Add overlap between consecutive chunks
        """
        if not pages:
            return []

        chunks: List[DocumentChunk] = []
        chunk_index = 0

        current_text_parts: List[str] = []
        current_token_count = 0
        current_start_page = pages[0].page_number
        current_heading: Optional[str] = None

        for page in pages:
            # Use first heading from page as section context
            page_heading = page.headings[0] if page.headings else None
            if page_heading:
                current_heading = page_heading

            # Split page text into sentences
            sentences = self.split_into_sentences(page.text)

            for sentence in sentences:
                sentence_tokens = self.count_tokens(sentence)

                # Check if adding this sentence exceeds max
                would_exceed = (
                    current_token_count + sentence_tokens > self.max_tokens
                )

                # Check if we're at a good break point
                at_target = current_token_count >= self.target_tokens
                is_heading = sentence == page_heading

                should_break = would_exceed or (at_target and is_heading)

                if should_break and current_text_parts:
                    # Create chunk from accumulated text
                    if current_token_count >= self.min_tokens:
                        chunk_text = " ".join(current_text_parts)
                        chunks.append(
                            DocumentChunk(
                                text=chunk_text,
                                token_count=current_token_count,
                                chunk_index=chunk_index,
                                page_number=current_start_page,
                                end_page_number=page.page_number,
                                section_heading=current_heading,
                            )
                        )
                        chunk_index += 1

                    current_text_parts = []
                    current_token_count = 0
                    current_start_page = page.page_number

                current_text_parts.append(sentence)
                current_token_count += sentence_tokens

        # Handle remaining text
        if current_text_parts:
            if current_token_count >= self.min_tokens:
                chunk_text = " ".join(current_text_parts)
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        token_count=current_token_count,
                        chunk_index=chunk_index,
                        page_number=current_start_page,
                        end_page_number=pages[-1].page_number if pages else current_start_page,
                        section_heading=current_heading,
                    )
                )
            elif chunks:
                # Merge small final chunk with previous
                last = chunks[-1]
                extra_text = " ".join(current_text_parts)
                combined_text = last.text + " " + extra_text
                chunks[-1] = DocumentChunk(
                    text=combined_text,
                    token_count=self.count_tokens(combined_text),
                    chunk_index=last.chunk_index,
                    page_number=last.page_number,
                    end_page_number=pages[-1].page_number if pages else last.end_page_number,
                    section_heading=last.section_heading,
                )

        # Add overlap
        if len(chunks) > 1:
            chunks = self._add_overlap(chunks)

        return chunks

    def _add_overlap(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Add overlap between consecutive chunks for context continuity."""
        if len(chunks) <= 1:
            return chunks

        overlapped = [chunks[0]]

        for i in range(1, len(chunks)):
            current = chunks[i]
            previous = chunks[i - 1]

            overlap_text = self._extract_overlap_text(
                previous.text, self.overlap_tokens
            )

            if overlap_text:
                new_text = overlap_text + " " + current.text
                new_token_count = self.count_tokens(new_text)
            else:
                new_text = current.text
                new_token_count = current.token_count

            overlapped.append(
                DocumentChunk(
                    text=new_text,
                    token_count=new_token_count,
                    chunk_index=current.chunk_index,
                    page_number=current.page_number,
                    end_page_number=current.end_page_number,
                    section_heading=current.section_heading,
                )
            )

        return overlapped

    def _extract_overlap_text(self, text: str, target_tokens: int) -> str:
        """Extract last N tokens from text for overlap."""
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
