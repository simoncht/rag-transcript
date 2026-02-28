"""
Contextual enrichment service for transcript chunks.

Implements Anthropic-style contextual retrieval by generating:
- Chunk summaries (1-3 sentences)
- Chunk titles (short phrase capturing main idea)
- Keywords/tags (key topics and entities)

This enrichment improves retrieval accuracy by providing semantic context
that can be embedded along with the raw chunk text.
"""
import json
import logging
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.services.llm_providers import LLMService, Message
from app.services.chunking import Chunk


@dataclass
class EnrichedChunk:
    """
    Chunk with contextual enrichment metadata.

    Attributes:
        chunk: Original chunk
        summary: 1-3 sentence summary
        title: Short phrase capturing main idea
        keywords: List of key topics/entities
        embedding_text: Combined text for embedding generation
    """

    chunk: Chunk
    summary: Optional[str] = None
    title: Optional[str] = None
    keywords: Optional[List[str]] = None
    embedding_text: Optional[str] = None

    def __post_init__(self):
        """Generate embedding text after initialization."""
        if self.summary and self.title:
            # Anthropic-style contextual retrieval:
            # Embed "{title}. {summary}\n\n{text}"
            self.embedding_text = f"{self.title}. {self.summary}\n\n{self.chunk.text}"
        else:
            # Fallback to just the chunk text
            self.embedding_text = self.chunk.text


class ContextualEnricher:
    """
    Service for enriching transcript chunks with contextual metadata.

    Uses an LLM to generate summaries, titles, and keywords for each chunk.
    Implements retry logic and graceful degradation if enrichment fails.
    Works for both video transcripts and document chunks.
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        video_context: Optional[str] = None,
        source_context: Optional[str] = None,
        content_type: str = "youtube",
        full_text: Optional[str] = None,
        usage_collector=None,
        content_id=None,
    ):
        """
        Initialize contextual enricher.

        Args:
            llm_service: LLM service instance (defaults to global instance)
            video_context: Optional video context (title, description) - legacy param
            source_context: Optional source context (title, description) - preferred param
            content_type: Type of content being enriched ('youtube', 'pdf', 'docx', etc.)
            full_text: Optional full transcript/document text for contextual grounding.
                       When provided, the LLM sees the entire document to produce
                       better chunk-level summaries (Anthropic contextual retrieval pattern).
            usage_collector: Optional LLMUsageCollector for tracking LLM costs
            content_id: Optional video/document UUID for cost attribution
        """
        from app.services.llm_providers import llm_service as default_llm_service

        self.llm_service = llm_service or default_llm_service
        # Support both legacy video_context and new source_context
        self.video_context = source_context or video_context
        self.content_type = content_type
        self.max_retries = settings.enrichment_max_retries
        # Full text for contextual enrichment (truncated to ~12K tokens ≈ 48K chars)
        if full_text and len(full_text) > 48000:
            logger.warning(
                f"[Enrichment] Full text truncated from {len(full_text)} to 48000 chars "
                f"({len(full_text) - 48000} chars lost). Content ID: {content_id}"
            )
            self.full_text = full_text[:48000]
        else:
            self.full_text = full_text
        self.usage_collector = usage_collector
        self.content_id = content_id

    def _create_enrichment_prompt(self, chunk: Chunk) -> List[Message]:
        """
        Create prompt for chunk enrichment.

        When full_text is available, uses the Anthropic contextual retrieval pattern:
        system message (static) → full text (cached per video) → chunk (varies).
        This lets DeepSeek cache the full text prefix after the first chunk.

        Works for both video transcript chunks (with timestamps) and document chunks
        (with page numbers).

        Args:
            chunk: Chunk to enrich

        Returns:
            List of messages for LLM
        """
        is_document = self.content_type != "youtube"
        content_descriptor = "document section" if is_document else "transcript segment"

        # Build system message — static, always cached
        system_parts = [
            f"You are an expert at analyzing {content_descriptor}s and extracting key information. "
            f"Your task is to generate concise metadata for a chunk of {'document' if is_document else 'transcript'} text.",
            "",
            "Return your response as valid JSON with these exact fields:",
            "{",
            '  "title": "A short phrase (3-7 words) capturing the main topic",',
            '  "summary": "A concise 1-3 sentence summary of what is discussed",',
            '  "keywords": ["3-7 key topics, entities, or concepts mentioned"]',
            "}",
            "",
            "Guidelines:",
            "- Title should be specific and descriptive",
            "- Summary should capture the essence, situating the chunk within the broader document",
            "- Keywords should be searchable terms someone might use to find this content",
            "- Return ONLY valid JSON, no additional text",
        ]

        # Append full text to system message for cache optimization
        # DeepSeek caches identical prefixes — full text is the same for all chunks
        if self.full_text:
            system_parts.extend([
                "",
                f"<full_{'document' if is_document else 'transcript'}>",
                self.full_text,
                f"</full_{'document' if is_document else 'transcript'}>",
            ])

        system_message = Message(
            role="system",
            content="\n".join(system_parts),
        )

        # Add source context if available
        context_info = ""
        if self.video_context:
            context_label = "Document context" if is_document else "Video context"
            context_info = f"\n\n{context_label}: {self.video_context}"

        # Location info: timestamp for videos, page number for documents
        if is_document:
            page_num = getattr(chunk, "page_number", None)
            location_str = f"page {page_num}" if page_num else "unknown location"
        else:
            timestamp_str = f"{int(chunk.start_timestamp // 60):02d}:{int(chunk.start_timestamp % 60):02d}"
            location_str = f"timestamp {timestamp_str}"

        # User message — varies per chunk
        user_message = Message(
            role="user",
            content=(
                f"Analyze this {content_descriptor} (from {location_str}):{context_info}\n\n"
                f"Text:\n{chunk.text}\n\n"
                "Return JSON with title, summary, and keywords."
            ),
        )

        return [system_message, user_message]

    def _parse_enrichment_response(self, response_text: str) -> Dict:
        """
        Parse LLM response into structured enrichment data.

        Args:
            response_text: LLM response text

        Returns:
            Dictionary with title, summary, keywords

        Raises:
            ValueError: If response cannot be parsed
        """
        try:
            # Try to extract JSON from response
            # Sometimes LLMs add markdown code blocks
            text = response_text.strip()

            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]

            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            # Validate required fields
            if "title" not in data or "summary" not in data or "keywords" not in data:
                raise ValueError("Missing required fields in response")

            # Validate types
            if not isinstance(data["title"], str):
                raise ValueError("Title must be a string")
            if not isinstance(data["summary"], str):
                raise ValueError("Summary must be a string")
            if not isinstance(data["keywords"], list):
                raise ValueError("Keywords must be a list")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse enrichment response: {str(e)}")

    def _create_fallback_enrichment(self, chunk: Chunk) -> Dict:
        """
        Create basic enrichment using heuristics when LLM enrichment fails.

        Args:
            chunk: Chunk to enrich

        Returns:
            Dictionary with basic title, summary, keywords
        """
        # Use first sentence as title (limited to 50 chars)
        sentences = chunk.text.split(". ")
        first_sentence = sentences[0] if sentences else chunk.text
        title = (
            first_sentence[:50] + "..." if len(first_sentence) > 50 else first_sentence
        )

        # Use first 2-3 sentences as summary
        summary_sentences = sentences[:3] if len(sentences) >= 3 else sentences
        summary = ". ".join(summary_sentences)
        if not summary.endswith("."):
            summary += "."

        # Extract simple keywords (most common words, excluding stopwords)
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
        }

        words = chunk.text.lower().split()
        word_freq = {}
        for word in words:
            # Clean word
            word = "".join(c for c in word if c.isalnum())
            if word and word not in stopwords and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get top 5 keywords
        keywords = sorted(word_freq.keys(), key=lambda w: word_freq[w], reverse=True)[
            :5
        ]

        return {
            "title": title,
            "summary": summary[:300],  # Limit summary length
            "keywords": keywords,
        }

    def enrich_chunk(self, chunk: Chunk) -> EnrichedChunk:
        """
        Enrich a single chunk with contextual metadata.

        Args:
            chunk: Chunk to enrich

        Returns:
            EnrichedChunk with summary, title, and keywords
        """
        if not settings.enable_contextual_enrichment:
            # Enrichment disabled, return chunk with fallback enrichment
            fallback = self._create_fallback_enrichment(chunk)
            return EnrichedChunk(
                chunk=chunk,
                title=fallback["title"],
                summary=fallback["summary"],
                keywords=fallback["keywords"],
            )

        # Try to enrich using LLM with retries
        for attempt in range(self.max_retries):
            try:
                messages = self._create_enrichment_prompt(chunk)

                response = self.llm_service.complete(
                    messages=messages,
                    temperature=0.3,  # Lower temperature for more consistent output
                    max_tokens=500,  # Enough for title + summary + keywords
                    retry=False,  # We handle retries here
                )

                # Record LLM usage
                if self.usage_collector and response.usage:
                    self.usage_collector.record(
                        response, "enrichment", content_id=self.content_id
                    )

                # Parse response
                enrichment_data = self._parse_enrichment_response(response.content)

                return EnrichedChunk(
                    chunk=chunk,
                    title=enrichment_data["title"],
                    summary=enrichment_data["summary"],
                    keywords=enrichment_data["keywords"],
                )

            except Exception as e:
                # Don't retry billing/auth errors — they won't resolve with retries
                error_str = str(e)
                is_permanent = any(code in error_str for code in ("402", "401", "403", "Insufficient Balance"))
                if not is_permanent and attempt < self.max_retries - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                else:
                    # All retries failed, use fallback
                    print(
                        f"Warning: Enrichment failed for chunk {chunk.chunk_index}, using fallback. Error: {str(e)}"
                    )
                    fallback = self._create_fallback_enrichment(chunk)
                    return EnrichedChunk(
                        chunk=chunk,
                        title=fallback["title"],
                        summary=fallback["summary"],
                        keywords=fallback["keywords"],
                    )

    def enrich_chunks_batch(
        self, chunks: List[Chunk], show_progress: bool = False
    ) -> List[EnrichedChunk]:
        """
        Enrich multiple chunks in batch.

        Processes chunks sequentially with rate limiting to avoid overwhelming the LLM.

        Args:
            chunks: List of chunks to enrich
            show_progress: Whether to print progress

        Returns:
            List of enriched chunks
        """
        enriched_chunks = []

        batch_size = settings.enrichment_batch_size

        for i, chunk in enumerate(chunks):
            enriched = self.enrich_chunk(chunk)
            enriched_chunks.append(enriched)

            if show_progress and (i + 1) % 10 == 0:
                print(f"Enriched {i + 1}/{len(chunks)} chunks")

            # Rate limiting: add small delay every batch_size chunks
            if (i + 1) % batch_size == 0 and i + 1 < len(chunks):
                time.sleep(1)  # 1 second delay between batches

        return enriched_chunks

    def enrich_chunks_concurrent(
        self,
        chunks: List[Chunk],
        max_workers: int = 5,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_chunk_complete: Optional[Callable[["EnrichedChunk"], None]] = None,
    ) -> List[EnrichedChunk]:
        """
        Enrich chunks concurrently using thread pool. Same quality, ~5x faster.

        Each chunk gets the exact same LLM prompt, model, and temperature.
        Concurrent calls produce identical results to sequential.

        Args:
            chunks: List of chunks to enrich
            max_workers: Maximum concurrent enrichment calls
            on_progress: Optional callback(completed, total) for progress tracking
            on_chunk_complete: Optional callback(enriched_chunk) called per chunk for incremental DB saves

        Returns:
            List of enriched chunks in original order
        """
        if not chunks:
            return []

        results: List[Optional[EnrichedChunk]] = [None] * len(chunks)
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.enrich_chunk, chunk): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    # Fallback for unexpected errors — enrich_chunk already handles retries
                    print(f"Warning: Concurrent enrichment failed for chunk {idx}: {e}")
                    fallback = self._create_fallback_enrichment(chunks[idx])
                    results[idx] = EnrichedChunk(
                        chunk=chunks[idx],
                        title=fallback["title"],
                        summary=fallback["summary"],
                        keywords=fallback["keywords"],
                    )
                if on_chunk_complete and results[idx]:
                    on_chunk_complete(results[idx])
                completed += 1
                if on_progress:
                    on_progress(completed, len(chunks))

        return results  # type: ignore[return-value]

    def set_video_context(
        self, video_title: str, video_description: Optional[str] = None
    ):
        """
        Set video context to improve enrichment quality.

        Args:
            video_title: Video title
            video_description: Optional video description
        """
        self.set_source_context(video_title, video_description)

    def set_source_context(
        self, title: str, description: Optional[str] = None
    ):
        """
        Set source context to improve enrichment quality.

        Works for both videos and documents.

        Args:
            title: Content title
            description: Optional description
        """
        context_parts = [f"Title: {title}"]
        if description:
            desc = (
                description[:500] + "..."
                if len(description) > 500
                else description
            )
            context_parts.append(f"Description: {desc}")

        self.video_context = " | ".join(context_parts)
