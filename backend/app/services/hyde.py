"""
HyDE (Hypothetical Document Embeddings) Service.

For coverage/hybrid queries, generates a hypothetical answer passage and embeds it
as an additional search vector. The hypothetical passage is semantically closer to
the actual relevant documents, improving recall for abstract or broad queries.

The HyDE embedding is an ADDITIONAL retrieval path, not a replacement. Max-score
fusion (already in conversations.py) naturally picks the best chunks from either
original or HyDE retrieval.
"""
import logging
from typing import Any, List, Optional

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class HyDEService:
    """
    Generates hypothetical answer passages and embeds them for retrieval.

    Only activates for COVERAGE and HYBRID intent queries where the user
    is asking broad or abstract questions.
    """

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        usage_collector=None,
    ):
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.enabled = getattr(settings, "enable_hyde", False)
        self.usage_collector = usage_collector

    def _ensure_services(self):
        if self.llm_service is None:
            from app.services.llm_providers import llm_service

            self.llm_service = llm_service
        if self.embedding_service is None:
            from app.services.embeddings import embedding_service

            self.embedding_service = embedding_service

    def generate_hypothetical_passage(self, query: str) -> Optional[str]:
        """
        Generate a hypothetical answer passage for the query.

        Args:
            query: user query

        Returns:
            hypothetical answer passage, or None if generation fails
        """
        if not self.enabled:
            return None

        self._ensure_services()

        try:
            from app.services.llm_providers import Message

            prompt = (
                "You are a helpful expert. Write a short passage (3-5 sentences) "
                "that would be a good answer to the following question. "
                "Write as if you are quoting from a transcript or document. "
                "Be specific and factual in tone.\n\n"
                f"Question: {query}\n\n"
                "Answer passage:"
            )

            messages = [Message(role="user", content=prompt)]
            response = self.llm_service.complete(
                messages=messages,
                temperature=0.7,  # Some creativity for diverse passages
                max_tokens=200,
            )

            if self.usage_collector and response.usage:
                self.usage_collector.record(response, "hyde")

            passage = response.content.strip()
            if passage and len(passage) > 20:
                logger.info(
                    f"[HyDE] Generated hypothetical passage ({len(passage)} chars)"
                )
                return passage
            else:
                logger.warning("[HyDE] Generated passage too short, skipping")
                return None

        except Exception as e:
            logger.warning(f"[HyDE] Passage generation failed: {e}")
            return None

    def generate_hyde_embedding(self, query: str) -> Optional[np.ndarray]:
        """
        Generate a HyDE embedding: hypothetical passage → embedding.

        Args:
            query: user query

        Returns:
            embedding vector for the hypothetical passage, or None
        """
        passage = self.generate_hypothetical_passage(query)
        if not passage:
            return None

        self._ensure_services()

        try:
            embedding = self.embedding_service.embed_text(passage)
            if isinstance(embedding, tuple):
                embedding = np.array(embedding, dtype=np.float32)
            logger.debug("[HyDE] Hypothetical passage embedded successfully")
            return embedding
        except Exception as e:
            logger.warning(f"[HyDE] Embedding failed: {e}")
            return None


# Global instance
_hyde_service: Optional[HyDEService] = None


def get_hyde_service() -> HyDEService:
    """Get or create global HyDE service instance."""
    global _hyde_service
    if _hyde_service is None:
        _hyde_service = HyDEService()
    return _hyde_service
