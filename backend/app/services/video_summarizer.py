"""
Video-level summary generation service.

Generates comprehensive summaries for entire videos by synthesizing all chunks.
This enables two-level retrieval (NotebookLM-style):
- Level 1: Video summaries for "summarize all" queries
- Level 0: Chunks for specific detail queries

Based on industry best practices from Google NotebookLM and Anthropic RAG guidelines.
"""
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm_providers import LLMService, Message
from app.models import Video, Chunk

logger = logging.getLogger(__name__)


class VideoSummarizer:
    """
    Service for generating video-level summaries from chunks.

    Produces:
    - summary: 200-500 word comprehensive summary
    - key_topics: Main themes/topics covered in the video
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize video summarizer.

        Args:
            llm_service: LLM service instance (defaults to global instance)
        """
        from app.services.llm_providers import llm_service as default_llm_service

        self.llm_service = llm_service or default_llm_service
        self.max_retries = 2
        # Target chunk sample size to fit in context while covering the video
        self.max_chunks_for_summary = 30
        self.max_tokens_per_chunk = 300

    def _sample_chunks_for_summary(
        self, chunks: List[Chunk], max_chunks: int = None
    ) -> List[Chunk]:
        """
        Sample chunks to cover the video evenly while fitting in context.

        Uses uniform sampling to get representative chunks from throughout
        the video rather than just the beginning.

        Args:
            chunks: All chunks from the video
            max_chunks: Maximum chunks to include

        Returns:
            Sampled list of chunks
        """
        max_chunks = max_chunks or self.max_chunks_for_summary

        if len(chunks) <= max_chunks:
            return chunks

        # Uniform sampling to cover the entire video
        step = len(chunks) / max_chunks
        sampled_indices = [int(i * step) for i in range(max_chunks)]
        return [chunks[i] for i in sampled_indices]

    def _truncate_chunk_text(self, text: str, max_chars: int = 1000) -> str:
        """Truncate chunk text to fit more chunks in context."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + "..."

    def _build_chunks_context(self, chunks: List[Chunk]) -> str:
        """
        Build context string from sampled chunks.

        Args:
            chunks: Sampled chunks

        Returns:
            Formatted context string
        """
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            # Format timestamp
            minutes = int(chunk.start_timestamp // 60)
            seconds = int(chunk.start_timestamp % 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"

            # Prefer enrichment summary over raw text (saves ~170 chars/chunk)
            text = (
                chunk.chunk_summary
                if chunk.chunk_summary
                else self._truncate_chunk_text(chunk.text)
            )

            # Add speaker/chapter info if available
            metadata = []
            if chunk.speakers:
                metadata.append(f"Speaker: {chunk.speakers[0]}")
            if chunk.chapter_title:
                metadata.append(f"Topic: {chunk.chapter_title}")
            metadata_str = f" ({', '.join(metadata)})" if metadata else ""

            context_parts.append(f"[{timestamp}]{metadata_str}\n{text}")

        return "\n\n---\n\n".join(context_parts)

    def _create_summary_prompt(
        self, video: Video, chunks_context: str
    ) -> List[Message]:
        """
        Create prompt for video summary generation.

        Args:
            video: Video metadata
            chunks_context: Formatted chunk excerpts

        Returns:
            List of messages for LLM
        """
        system_message = Message(
            role="system",
            content=(
                "You are an expert at summarizing video content. Your task is to create "
                "a comprehensive summary of a video based on transcript excerpts.\n\n"
                "Return your response as valid JSON with these exact fields:\n"
                "{\n"
                '  "summary": "A comprehensive 200-500 word summary covering the main points, '
                'key arguments, and important details discussed in the video",\n'
                '  "key_topics": ["5-10 main themes or topics covered in the video"]\n'
                "}\n\n"
                "Guidelines:\n"
                "- Summary should be comprehensive but concise (200-500 words)\n"
                "- Cover the main points in a logical flow\n"
                "- Include key arguments, examples, or insights mentioned\n"
                "- Key topics should be specific (not generic like 'introduction')\n"
                "- Write in third person (e.g., 'The speaker discusses...')\n"
                "- If speakers are identified, mention them by name\n"
                "- Do not make up information not present in the excerpts\n"
            ),
        )

        # Build user message with video context
        video_info = f"Title: {video.title}\n"
        if video.channel_name:
            video_info += f"Channel: {video.channel_name}\n"
        if video.description and len(video.description) < 500:
            video_info += f"Description: {video.description[:500]}\n"

        user_message = Message(
            role="user",
            content=(
                f"Please summarize this video:\n\n"
                f"{video_info}\n"
                f"Transcript excerpts (sampled from throughout the video):\n\n"
                f"{chunks_context}"
            ),
        )

        return [system_message, user_message]

    def _parse_summary_response(
        self, response_text: str
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        Parse LLM response to extract summary and key topics.

        Args:
            response_text: Raw LLM response

        Returns:
            Tuple of (summary, key_topics)
        """
        try:
            # Try to parse as JSON
            # Handle potential markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            summary = data.get("summary", "").strip()
            key_topics = data.get("key_topics", [])

            # Validate
            if not summary or len(summary) < 50:
                logger.warning("Summary too short or missing")
                return None, None

            if not isinstance(key_topics, list):
                key_topics = []

            # Clean up key topics
            key_topics = [str(t).strip() for t in key_topics if t][:10]

            return summary, key_topics

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summary response as JSON: {e}")
            # Try to extract summary from plain text
            if len(response_text) > 100:
                return response_text.strip()[:2000], []
            return None, None

    def generate_summary(
        self,
        db: Session,
        video: Video,
        chunks: Optional[List[Chunk]] = None,
        usage_collector=None,
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        Generate video-level summary from chunks.

        Args:
            db: Database session
            video: Video to summarize
            chunks: Optional pre-loaded chunks (will query if not provided)
            usage_collector: Optional LLMUsageCollector for tracking costs

        Returns:
            Tuple of (summary, key_topics)
        """
        logger.info(f"[Video Summary] Generating summary for video: {video.title[:50]}...")

        # Load chunks if not provided
        if chunks is None:
            chunks = (
                db.query(Chunk)
                .filter(Chunk.video_id == video.id)
                .order_by(Chunk.start_timestamp.asc())
                .all()
            )

        if not chunks:
            logger.warning(f"[Video Summary] No chunks found for video {video.id}")
            return None, None

        logger.info(f"[Video Summary] Processing {len(chunks)} chunks")

        # Sample chunks for summary
        sampled_chunks = self._sample_chunks_for_summary(chunks)
        logger.info(f"[Video Summary] Sampled {len(sampled_chunks)} chunks for context")

        # Build context
        chunks_context = self._build_chunks_context(sampled_chunks)

        # Create prompt
        messages = self._create_summary_prompt(video, chunks_context)

        # Generate summary with retries
        for attempt in range(self.max_retries):
            try:
                response = self.llm_service.complete(
                    messages,
                    temperature=0.3,  # Low temperature for consistent summaries
                )

                if usage_collector and response.usage:
                    usage_collector.record(
                        response, "summarization", content_id=video.id
                    )

                summary, key_topics = self._parse_summary_response(response.content)

                if summary:
                    logger.info(
                        f"[Video Summary] Generated summary ({len(summary)} chars) "
                        f"with {len(key_topics)} topics"
                    )
                    return summary, key_topics

                logger.warning(f"[Video Summary] Attempt {attempt + 1} failed to parse response")

            except Exception as e:
                logger.error(f"[Video Summary] Attempt {attempt + 1} failed: {e}")

        logger.error(f"[Video Summary] Failed to generate summary after {self.max_retries} attempts")
        return None, None

    def update_video_summary(
        self,
        db: Session,
        video_id: UUID,
        usage_collector=None,
    ) -> bool:
        """
        Generate and save summary for a video.

        Args:
            db: Database session
            video_id: Video ID to summarize
            usage_collector: Optional LLMUsageCollector for tracking costs

        Returns:
            True if successful, False otherwise
        """
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"[Video Summary] Video not found: {video_id}")
            return False

        summary, key_topics = self.generate_summary(
            db, video, usage_collector=usage_collector
        )

        if summary:
            video.summary = summary
            video.key_topics = key_topics
            video.summary_generated_at = datetime.utcnow()
            db.commit()
            logger.info(f"[Video Summary] Saved summary for video {video_id}")
            return True

        return False


# Global service instance
video_summarizer_service = VideoSummarizer()


def get_video_summarizer_service() -> VideoSummarizer:
    """Get video summarizer service instance."""
    return video_summarizer_service
