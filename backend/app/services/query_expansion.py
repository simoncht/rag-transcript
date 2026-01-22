"""
Query Expansion Service - Generates multiple query variants for improved recall

This service takes a user query and generates semantically similar variants using an LLM.
The variants are then used to retrieve from multiple perspectives, improving recall.

Strategy:
- Generate 2-3 paraphrases of the original query
- Use lightweight LLM calls (fast, low cost)
- Return original + variants for multi-query retrieval
"""
import logging
from typing import List
from app.services.llm_providers import LLMService, Message
from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """
    Generates query variants to improve retrieval recall.

    Uses LLM to create semantically similar but differently-phrased queries.
    This helps capture content that uses different terminology or phrasing.
    """

    def __init__(self, llm_service: LLMService | None = None):
        """
        Initialize query expansion service.

        Args:
            llm_service: Optional LLM service. If None, creates new instance.
        """
        self.llm_service = llm_service or LLMService()
        self.enabled = settings.enable_query_expansion
        self.num_variants = settings.query_expansion_variants

    def expand_query(self, query: str) -> List[str]:
        """
        Generate query variants for multi-query retrieval.

        Args:
            query: Original user query

        Returns:
            List of queries: [original, variant1, variant2, ...]
            If expansion fails or is disabled, returns [original]
        """
        # Fast path: if disabled, return original only
        if not self.enabled:
            logger.debug("Query expansion disabled, returning original query")
            return [query]

        # Always include original query first
        queries = [query]

        try:
            logger.info(f"Expanding query: '{query[:50]}...'")

            # Generate variants using LLM
            variants = self._generate_variants(query, count=self.num_variants)

            # Filter out empty or duplicate variants
            unique_variants = []
            seen = {query.lower().strip()}

            for variant in variants:
                variant_normalized = variant.lower().strip()
                if variant_normalized and variant_normalized not in seen:
                    unique_variants.append(variant)
                    seen.add(variant_normalized)

            queries.extend(unique_variants)

            logger.info(
                f"Query expansion: generated {len(unique_variants)} unique variants "
                f"(total queries: {len(queries)})"
            )

            # Log the variants for debugging
            for i, q in enumerate(queries):
                logger.debug(f"  Query {i}: {q}")

            return queries

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}. Using original query only.")
            return [query]

    def _generate_variants(self, query: str, count: int = 2) -> List[str]:
        """
        Use LLM to generate query variants.

        Args:
            query: Original query
            count: Number of variants to generate

        Returns:
            List of variant queries
        """
        prompt = f"""Generate {count} alternative ways to ask the following question.
The variants should be semantically similar but use different wording or phrasing.
Keep variants concise and natural. Return ONLY the variant questions, one per line.

Original question: {query}

Variant questions:"""

        try:
            # Use LLM with low temperature for consistent, focused output
            messages = [Message(role="user", content=prompt)]

            response = self.llm_service.complete(
                messages=messages,
                max_tokens=150,  # Short responses
                temperature=0.3,  # Low temperature for consistency
            )

            # Parse response - expect one variant per line
            variants = []
            for line in response.content.strip().split('\n'):
                line = line.strip()
                # Remove numbering (1., 2., etc.) if present
                if line and line[0].isdigit():
                    line = line.split('.', 1)[1].strip() if '.' in line else line
                # Remove bullet points if present
                if line.startswith('- ') or line.startswith('* '):
                    line = line[2:].strip()
                if line and len(line) > 5:  # Minimum length check
                    variants.append(line)

            return variants[:count]  # Limit to requested count

        except Exception as e:
            logger.error(f"Failed to generate query variants via LLM: {e}")
            return []


# Global instance
_query_expansion_service: QueryExpansionService | None = None


def get_query_expansion_service() -> QueryExpansionService:
    """Get or create global query expansion service instance."""
    global _query_expansion_service
    if _query_expansion_service is None:
        _query_expansion_service = QueryExpansionService()
    return _query_expansion_service
