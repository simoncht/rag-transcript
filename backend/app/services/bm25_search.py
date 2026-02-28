"""
BM25 keyword search service for hybrid retrieval.

Provides BM25 as a parallel search signal alongside dense vector search.
Results are fused with Reciprocal Rank Fusion (RRF) before reranking.

This module is safe to import when rank-bm25 is not installed —
the service degrades to a no-op.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

# Common English stopwords for query-length gating and term overlap checks
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "were",
    "are", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "not", "no", "so", "if", "then", "than", "that", "this", "these",
    "those", "what", "which", "who", "whom", "how", "when", "where",
    "why", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "about", "up",
    "out", "just", "into", "also", "very", "much", "too", "here",
    "there", "me", "my", "i", "you", "your", "he", "she", "we", "they",
    "his", "her", "its", "our", "their", "him", "us", "them",
    "tell", "know", "think", "say", "like", "get", "make",
}


def _tokenize(text: str) -> List[str]:
    """Lowercase whitespace+word-boundary tokenization."""
    return re.findall(r"\b\w+\b", text.lower())


def _content_tokens(text: str) -> List[str]:
    """Return non-stopword tokens from text."""
    return [t for t in _tokenize(text) if t not in STOPWORDS]


def _has_proper_noun(query: str) -> bool:
    """Detect likely proper nouns (capitalized words that aren't sentence-initial)."""
    words = query.split()
    # Skip first word (always capitalized in a sentence)
    return any(w[0].isupper() and w.lower() not in STOPWORDS for w in words[1:] if w)


def _should_skip_bm25(query: str) -> bool:
    """Skip BM25 when query has fewer than 3 non-stopword tokens.

    Exception: never skip if query contains proper nouns — BM25 excels at
    exact-match retrieval for names and entities (e.g., "Ken Robinson").
    """
    if _has_proper_noun(query):
        return False
    return len(_content_tokens(query)) < 3


@dataclass
class BM25Result:
    """A single BM25 search result with chunk metadata."""

    chunk_id: UUID
    video_id: UUID
    user_id: UUID
    text: str
    embedding_text: str
    start_timestamp: float
    end_timestamp: float
    chunk_index: int
    content_type: str = "youtube"
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    chapter_title: Optional[str] = None
    speakers: Optional[List[str]] = None
    bm25_score: float = 0.0
    normalized_score: float = 0.0


class BM25SearchService:
    """
    Lazy-loaded BM25 keyword search over PostgreSQL chunks.

    Follows the same lazy-init pattern as RerankerService:
    - No work at import time
    - Graceful degradation if rank-bm25 is not installed
    """

    def __init__(self) -> None:
        self._bm25_available: Optional[bool] = None
        # TTL cache for BM25 index to avoid rebuilding on every query
        # key: (user_id, frozenset(video_ids)) -> (bm25, chunks, tokenized_corpus, timestamp)
        self._index_cache: dict = {}
        self._cache_ttl: int = 300  # 5 minutes
        self._cache_max_size: int = 32

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "enable_bm25_search", False))

    def _check_bm25(self) -> bool:
        if self._bm25_available is not None:
            return self._bm25_available
        try:
            import rank_bm25  # noqa: F401

            self._bm25_available = True
        except ImportError:
            self._bm25_available = False
            logger.warning(
                "[BM25] rank-bm25 not installed — BM25 search disabled. "
                "Install with: pip install rank-bm25"
            )
        return self._bm25_available

    def search(
        self,
        db,
        query: str,
        user_id: UUID,
        video_ids: List[UUID],
        top_k: int = 20,
    ) -> List[BM25Result]:
        """
        Run BM25 keyword search over chunks matching the given video_ids.

        Returns up to top_k results that pass quality gating (S1):
        - Normalized BM25 score >= threshold
        - At least N non-stopword query terms appear in the chunk text
        """
        if not self.enabled or not self._check_bm25():
            return []

        if not video_ids:
            return []

        import time as _time
        from rank_bm25 import BM25Okapi

        from app.models.chunk import Chunk

        # Check cache for pre-built BM25 index
        cache_key = (str(user_id), frozenset(str(vid) for vid in video_ids))
        cached = self._index_cache.get(cache_key)
        now = _time.time()

        if cached and (now - cached[3]) < self._cache_ttl:
            bm25, chunks, tokenized_corpus = cached[0], cached[1], cached[2]
            logger.debug("[BM25] Using cached index")
        else:
            # Query chunks from PostgreSQL
            try:
                chunks = (
                    db.query(Chunk)
                    .filter(
                        Chunk.user_id == user_id,
                        Chunk.video_id.in_(video_ids),
                        Chunk.is_indexed == True,  # noqa: E712
                    )
                    .all()
                )
            except Exception as exc:
                logger.warning(f"[BM25] DB query failed: {exc}")
                return []

            if not chunks:
                return []

            # Build corpus from embedding_text (S5) — richer keyword surface
            corpus_texts = []
            for chunk in chunks:
                text = chunk.embedding_text or chunk.text or ""
                corpus_texts.append(text)

            tokenized_corpus = [_tokenize(t) for t in corpus_texts]

            # Guard against empty corpus (all empty texts)
            if not any(tokenized_corpus):
                return []

            bm25 = BM25Okapi(tokenized_corpus)

            # Cache the index
            if len(self._index_cache) >= self._cache_max_size:
                # Evict oldest entry
                oldest_key = min(self._index_cache, key=lambda k: self._index_cache[k][3])
                del self._index_cache[oldest_key]
            self._index_cache[cache_key] = (bm25, chunks, tokenized_corpus, now)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = bm25.get_scores(query_tokens)

        # Normalize scores relative to the top score in this batch
        max_score = max(scores) if len(scores) > 0 else 0.0
        if max_score <= 0:
            return []

        min_normalized = getattr(settings, "bm25_min_normalized_score", 0.25)
        min_term_overlap = getattr(settings, "bm25_min_term_overlap", 2)
        query_content_tokens = set(_content_tokens(query))

        results: List[BM25Result] = []
        for idx, (chunk, score) in enumerate(zip(chunks, scores)):
            normalized = score / max_score

            # S1: Quality gate — minimum normalized score
            if normalized < min_normalized:
                continue

            # S1: Quality gate — minimum term overlap
            chunk_text_lower = (chunk.embedding_text or chunk.text or "").lower()
            overlap_count = sum(
                1 for t in query_content_tokens if t in chunk_text_lower
            )
            if overlap_count < min_term_overlap:
                continue

            results.append(
                BM25Result(
                    chunk_id=chunk.id,
                    video_id=chunk.video_id,
                    user_id=chunk.user_id,
                    text=chunk.text,
                    embedding_text=chunk.embedding_text or chunk.text,
                    start_timestamp=chunk.start_timestamp,
                    end_timestamp=chunk.end_timestamp,
                    chunk_index=chunk.chunk_index,
                    content_type=chunk.content_type or "youtube",
                    page_number=chunk.page_number,
                    section_heading=chunk.section_heading,
                    title=chunk.chunk_title,
                    summary=chunk.chunk_summary,
                    keywords=chunk.keywords,
                    chapter_title=chunk.chapter_title,
                    speakers=chunk.speakers,
                    bm25_score=float(score),
                    normalized_score=float(normalized),
                )
            )

        # Sort by BM25 score descending and return top_k
        results.sort(key=lambda r: r.bm25_score, reverse=True)
        return results[:top_k]


def rrf_fuse(
    vector_chunks: Sequence,
    bm25_results: List[BM25Result],
    k: int = 60,
    vector_weight: float = 1.0,
    bm25_weight: float = 0.3,
    max_bm25_unique: int = 3,
) -> List:
    """
    Reciprocal Rank Fusion of vector search and BM25 results.

    For chunks in both lists: keeps the vector ScoredChunk (preserves cosine score).
    For BM25-only chunks: converts to ScoredChunk with score=0.45 (S8).
    Caps BM25-only additions at max_bm25_unique (S2).

    Returns merged list ordered by RRF rank.
    """
    from app.services.vector_store import ScoredChunk

    if not vector_chunks and not bm25_results:
        return []

    if not bm25_results:
        return list(vector_chunks)

    # Build lookup by chunk_id
    vector_by_id = {}
    for rank, chunk in enumerate(vector_chunks):
        cid = chunk.chunk_id
        if cid is not None:
            vector_by_id[cid] = (rank, chunk)

    bm25_by_id = {}
    for rank, result in enumerate(bm25_results):
        bm25_by_id[result.chunk_id] = (rank, result)

    # Compute RRF scores
    all_ids = set(vector_by_id.keys()) | set(bm25_by_id.keys())
    rrf_scores: dict = {}

    for cid in all_ids:
        score = 0.0
        if cid in vector_by_id:
            rank = vector_by_id[cid][0]
            score += vector_weight / (k + rank + 1)
        if cid in bm25_by_id:
            rank = bm25_by_id[cid][0]
            score += bm25_weight / (k + rank + 1)
        rrf_scores[cid] = score

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    # Build output list
    default_score = getattr(settings, "bm25_default_score", 0.45)
    bm25_unique_count = 0
    merged: list = []

    for cid in sorted_ids:
        if cid in vector_by_id:
            # Use existing vector ScoredChunk (preserves cosine score)
            merged.append(vector_by_id[cid][1])
        else:
            # BM25-only chunk — apply cap (S2)
            if bm25_unique_count >= max_bm25_unique:
                continue
            bm25_unique_count += 1

            result = bm25_by_id[cid][1]
            merged.append(
                ScoredChunk(
                    chunk_id=result.chunk_id,
                    video_id=result.video_id,
                    user_id=result.user_id,
                    text=result.text,
                    start_timestamp=result.start_timestamp,
                    end_timestamp=result.end_timestamp,
                    score=default_score,  # S8: below primary threshold
                    chunk_index=result.chunk_index,
                    content_type=result.content_type,
                    page_number=result.page_number,
                    section_heading=result.section_heading,
                    title=result.title,
                    summary=result.summary,
                    keywords=result.keywords,
                    chapter_title=result.chapter_title,
                    speakers=result.speakers,
                )
            )

    return merged


# Module-level singleton (follows reranker.py pattern)
_bm25_service: Optional[BM25SearchService] = None


def get_bm25_search_service() -> BM25SearchService:
    global _bm25_service
    if _bm25_service is None:
        _bm25_service = BM25SearchService()
    return _bm25_service
