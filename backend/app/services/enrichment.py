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
from typing import List, Optional, Dict
from dataclasses import dataclass
import time

from app.core.config import settings
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
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        video_context: Optional[str] = None
    ):
        """
        Initialize contextual enricher.

        Args:
            llm_service: LLM service instance (defaults to global instance)
            video_context: Optional video context (title, description) to improve enrichment
        """
        from app.services.llm_providers import llm_service as default_llm_service

        self.llm_service = llm_service or default_llm_service
        self.video_context = video_context
        self.max_retries = settings.enrichment_max_retries

    def _create_enrichment_prompt(self, chunk: Chunk) -> List[Message]:
        """
        Create prompt for chunk enrichment.

        Args:
            chunk: Chunk to enrich

        Returns:
            List of messages for LLM
        """
        system_message = Message(
            role="system",
            content=(
                "You are an expert at analyzing transcript segments and extracting key information. "
                "Your task is to generate concise metadata for a chunk of transcript text.\n\n"
                "Return your response as valid JSON with these exact fields:\n"
                "{\n"
                '  "title": "A short phrase (3-7 words) capturing the main topic",\n'
                '  "summary": "A concise 1-3 sentence summary of what is discussed",\n'
                '  "keywords": ["3-7 key topics, entities, or concepts mentioned"]\n'
                "}\n\n"
                "Guidelines:\n"
                "- Title should be specific and descriptive\n"
                "- Summary should capture the essence and key points\n"
                "- Keywords should be searchable terms someone might use to find this content\n"
                "- Return ONLY valid JSON, no additional text"
            )
        )

        # Add video context if available
        context_info = ""
        if self.video_context:
            context_info = f"\n\nVideo context: {self.video_context}"

        # Add timestamp for context
        timestamp_str = f"{int(chunk.start_timestamp // 60):02d}:{int(chunk.start_timestamp % 60):02d}"

        user_message = Message(
            role="user",
            content=(
                f"Analyze this transcript segment (from {timestamp_str}):{context_info}\n\n"
                f"Transcript:\n{chunk.text}\n\n"
                "Return JSON with title, summary, and keywords."
            )
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
        sentences = chunk.text.split('. ')
        first_sentence = sentences[0] if sentences else chunk.text
        title = first_sentence[:50] + "..." if len(first_sentence) > 50 else first_sentence

        # Use first 2-3 sentences as summary
        summary_sentences = sentences[:3] if len(sentences) >= 3 else sentences
        summary = '. '.join(summary_sentences)
        if not summary.endswith('.'):
            summary += '.'

        # Extract simple keywords (most common words, excluding stopwords)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                     'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
                     'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}

        words = chunk.text.lower().split()
        word_freq = {}
        for word in words:
            # Clean word
            word = ''.join(c for c in word if c.isalnum())
            if word and word not in stopwords and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get top 5 keywords
        keywords = sorted(word_freq.keys(), key=lambda w: word_freq[w], reverse=True)[:5]

        return {
            "title": title,
            "summary": summary[:300],  # Limit summary length
            "keywords": keywords
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
                keywords=fallback["keywords"]
            )

        # Try to enrich using LLM with retries
        for attempt in range(self.max_retries):
            try:
                messages = self._create_enrichment_prompt(chunk)

                response = self.llm_service.complete(
                    messages=messages,
                    temperature=0.3,  # Lower temperature for more consistent output
                    max_tokens=500,   # Enough for title + summary + keywords
                    retry=False       # We handle retries here
                )

                # Parse response
                enrichment_data = self._parse_enrichment_response(response.content)

                return EnrichedChunk(
                    chunk=chunk,
                    title=enrichment_data["title"],
                    summary=enrichment_data["summary"],
                    keywords=enrichment_data["keywords"]
                )

            except Exception as e:
                if attempt < self.max_retries - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    # All retries failed, use fallback
                    print(f"Warning: Enrichment failed for chunk {chunk.chunk_index}, using fallback. Error: {str(e)}")
                    fallback = self._create_fallback_enrichment(chunk)
                    return EnrichedChunk(
                        chunk=chunk,
                        title=fallback["title"],
                        summary=fallback["summary"],
                        keywords=fallback["keywords"]
                    )

    def enrich_chunks_batch(
        self,
        chunks: List[Chunk],
        show_progress: bool = False
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

    def set_video_context(self, video_title: str, video_description: Optional[str] = None):
        """
        Set video context to improve enrichment quality.

        Args:
            video_title: Video title
            video_description: Optional video description
        """
        context_parts = [f"Title: {video_title}"]
        if video_description:
            # Limit description length
            desc = video_description[:500] + "..." if len(video_description) > 500 else video_description
            context_parts.append(f"Description: {desc}")

        self.video_context = " | ".join(context_parts)
