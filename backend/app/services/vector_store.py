"""
Vector store service for indexing and searching transcript chunks.

Provides abstraction over vector databases (currently Qdrant, could support pgvector later).
Handles embedding storage, similarity search, and filtering.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass
from uuid import UUID
import uuid
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import settings
from app.services.enrichment import EnrichedChunk


@dataclass
class ScoredChunk:
    """
    Search result with relevance score.

    Attributes:
        chunk_id: UUID of the chunk (DB id when available)
        video_id: UUID of the source (video or document - kept as video_id for backward compat)
        user_id: UUID of the user
        text: Chunk text
        start_timestamp: Start time in seconds (0.0 for documents)
        end_timestamp: End time in seconds (0.0 for documents)
        score: Relevance score (0.0 to 1.0, higher is better)
        content_type: Content type ('youtube', 'pdf', 'docx', etc.)
        page_number: Page number for documents (None for videos)
        section_heading: Section heading for documents (None for videos)
        title: Chunk title (if available)
        summary: Chunk summary (if available)
        keywords: Chunk keywords (if available)
        chapter_title: Chapter title (if available)
        speakers: List of speakers in the chunk (if available)
    """

    chunk_id: Optional[UUID]
    video_id: UUID  # Also serves as source_id for documents
    user_id: UUID
    text: str
    start_timestamp: float
    end_timestamp: float
    score: float
    chunk_index: Optional[int] = None  # Legacy identifier within a video
    content_type: str = "youtube"
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    chapter_title: Optional[str] = None
    speakers: Optional[List[str]] = None

    @property
    def source_id(self) -> UUID:
        """Alias for video_id for content-type-agnostic code."""
        return self.video_id

    @property
    def is_document(self) -> bool:
        """Whether this chunk comes from a document (not a video)."""
        return self.content_type != "youtube"


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def create_collection(self, dimensions: int):
        """Create collection if it doesn't exist."""
        pass

    @abstractmethod
    def index_chunks(
        self,
        enriched_chunks: List[EnrichedChunk],
        embeddings: List[np.ndarray],
        user_id: UUID,
        video_id: UUID,
    ):
        """Index chunks with embeddings."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[ScoredChunk]:
        """Search for similar chunks."""
        pass

    @abstractmethod
    def delete_by_video_id(self, video_id: UUID):
        """Delete all chunks for a video."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict:
        """Get collection statistics."""
        pass


class QdrantVectorStore(VectorStore):
    """
    Qdrant vector store implementation.

    Uses Qdrant for efficient similarity search with filtering.
    """

    def __init__(self, host: str = None, port: int = None, collection_name: str = None):
        """
        Initialize Qdrant vector store.

        Args:
            host: Qdrant host
            port: Qdrant port
            collection_name: Collection name
        """
        self.host = host or settings.qdrant_host
        self.port = port or settings.qdrant_port
        self.collection_name = collection_name or settings.qdrant_collection_name

        # Initialize Qdrant client
        # Use API key if configured for authentication
        # prefer_grpc=False and https=False for local development without TLS
        if settings.qdrant_api_key:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=settings.qdrant_api_key,
                prefer_grpc=False,
                https=False,
            )
        else:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                prefer_grpc=False,
                https=False,
            )

    def create_collection(self, dimensions: int):
        """
        Create Qdrant collection if it doesn't exist.

        Args:
            dimensions: Vector dimensions
        """
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimensions, distance=Distance.COSINE  # Cosine similarity
                ),
            )
            print(f"Created Qdrant collection: {self.collection_name}")
        else:
            print(f"Qdrant collection already exists: {self.collection_name}")

    def index_chunks(
        self,
        enriched_chunks: List[EnrichedChunk],
        embeddings: List[np.ndarray],
        user_id: UUID,
        video_id: UUID,
        content_type: str = "youtube",
    ):
        """
        Index enriched chunks with their embeddings.

        Args:
            enriched_chunks: List of enriched chunks
            embeddings: List of embedding vectors (same length as enriched_chunks)
            user_id: User ID
            video_id: Video ID (also serves as source_id for documents)
            content_type: Content type ('youtube', 'pdf', 'docx', etc.)
        """
        if len(enriched_chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        points = []

        for enriched_chunk, embedding in zip(enriched_chunks, embeddings):
            chunk = enriched_chunk.chunk

            # Prepare payload (metadata)
            payload = {
                "chunk_id": str(
                    chunk.chunk_index
                ),  # Use chunk_index as unique id within video/document
                "video_id": str(video_id),  # Kept as video_id for backward compat
                "user_id": str(user_id),
                "text": chunk.text,
                "start_timestamp": chunk.start_timestamp,
                "end_timestamp": chunk.end_timestamp,
                "duration_seconds": chunk.duration_seconds,
                "token_count": chunk.token_count,
                "content_type": content_type,
            }

            # Add enrichment metadata if available
            if enriched_chunk.title:
                payload["title"] = enriched_chunk.title
            if enriched_chunk.summary:
                payload["summary"] = enriched_chunk.summary
            if enriched_chunk.keywords:
                payload["keywords"] = enriched_chunk.keywords

            # Add optional fields (video-specific)
            if chunk.speakers:
                payload["speakers"] = chunk.speakers
            if chunk.chapter_title:
                payload["chapter_title"] = chunk.chapter_title
                payload["chapter_index"] = chunk.chapter_index

            # Add document-specific fields
            page_number = getattr(chunk, "page_number", None)
            if page_number is not None:
                payload["page_number"] = page_number
            section_heading = getattr(chunk, "section_heading", None)
            if section_heading:
                payload["section_heading"] = section_heading

            # Create point with unique ID (video_id + chunk_index)
            point_id = str(uuid.uuid5(video_id, str(chunk.chunk_index)))

            point = PointStruct(id=point_id, vector=embedding.tolist(), payload=payload)

            points.append(point)

        # Upsert points to Qdrant in batches to avoid payload size limits
        BATCH_SIZE = 500
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            self.client.upsert(collection_name=self.collection_name, points=batch)

        print(f"Indexed {len(points)} chunks for {'document' if content_type != 'youtube' else 'video'} {video_id}")

    def search_with_diversity(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        diversity: float = 0.5,
        prefetch_limit: int = 100,
        filters: Optional[Dict] = None,
    ) -> List[ScoredChunk]:
        """
        Search for similar chunks with MMR-based diversity.

        Uses Maximal Marginal Relevance (MMR) to balance relevance with diversity,
        ensuring chunks from multiple videos are represented in results.

        Args:
            query_embedding: Query embedding vector
            user_id: Optional user ID filter
            video_ids: Optional list of video IDs to search within
            top_k: Number of results to return
            diversity: Balance between relevance (0.0) and diversity (1.0)
                       Recommended: 0.3-0.5 for single video, 0.5-0.7 for multi-video
            prefetch_limit: Number of candidates to fetch before MMR reranking
            filters: Optional additional filters

        Returns:
            List of scored chunks ordered by MMR score (relevance + diversity)
        """
        # First, fetch more candidates than needed for MMR selection
        candidates = self.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=prefetch_limit,
            filters=filters,
        )

        if not candidates or len(candidates) <= top_k:
            return candidates[:top_k] if candidates else []

        # Apply MMR reranking for diversity
        return self._apply_mmr(
            query_embedding=query_embedding,
            candidates=candidates,
            top_k=top_k,
            diversity=diversity,
        )

    def search_with_video_guarantee(
        self,
        query_embedding: np.ndarray,
        video_ids: List[UUID],
        user_id: UUID,
        top_k: int = 10,
        prefetch_limit: int = 100,
    ) -> List[ScoredChunk]:
        """
        Search with guaranteed minimum 1 chunk per video.

        For summarize queries across multiple videos, this ensures every video
        gets at least one representative chunk in the results.

        Two-phase approach:
        1. Phase 1: Select best chunk from each video (guarantees N videos represented)
        2. Phase 2: Fill remaining slots with MMR for diversity

        Args:
            query_embedding: Query embedding vector
            video_ids: List of video IDs to search within (all should be represented)
            user_id: User ID for filtering
            top_k: Number of results to return
            prefetch_limit: Number of candidates to fetch for selection

        Returns:
            List of scored chunks with guaranteed video representation
        """
        # Fetch candidates from all videos
        candidates = self.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=prefetch_limit,
        )

        if not candidates:
            return []

        # Phase 1: Best chunk per video (guarantees video representation)
        best_per_video: Dict[UUID, ScoredChunk] = {}
        for chunk in candidates:
            vid = chunk.video_id
            if vid not in best_per_video or chunk.score > best_per_video[vid].score:
                best_per_video[vid] = chunk

        # Add best chunk from each video (in order of video_ids to be deterministic)
        selected: List[ScoredChunk] = []
        selected_ids: set = set()

        for vid in video_ids:
            if vid in best_per_video and len(selected) < top_k:
                chunk = best_per_video[vid]
                selected.append(chunk)
                selected_ids.add(chunk.chunk_id)

        # If we've hit the limit, return early
        if len(selected) >= top_k:
            return selected[:top_k]

        # Phase 2: Fill remaining slots with MMR for diversity
        remaining = [c for c in candidates if c.chunk_id not in selected_ids]
        slots_to_fill = top_k - len(selected)

        if remaining and slots_to_fill > 0:
            mmr_chunks = self._apply_mmr_with_preselected(
                candidates=remaining,
                top_k=slots_to_fill,
                diversity=0.5,
                preselected=selected,
            )
            selected.extend(mmr_chunks)

        return selected

    def _apply_mmr_with_preselected(
        self,
        candidates: List[ScoredChunk],
        top_k: int,
        diversity: float,
        preselected: List[ScoredChunk],
    ) -> List[ScoredChunk]:
        """
        Apply MMR reranking considering already-selected chunks.

        This is used by search_with_video_guarantee to fill remaining slots
        while respecting diversity from the pre-selected chunks.

        Args:
            candidates: Remaining candidates to select from
            top_k: Number of additional chunks to select
            diversity: Diversity factor (0.0 = relevance only, 1.0 = max diversity)
            preselected: Already-selected chunks to consider for diversity penalty

        Returns:
            List of additional chunks selected via MMR
        """
        if not candidates:
            return []

        lambda_param = 1.0 - diversity
        selected: List[ScoredChunk] = []
        remaining = list(candidates)

        # Include preselected chunks in diversity calculation
        all_selected = list(preselected)

        while len(selected) < top_k and remaining:
            best_score = float("-inf")
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                relevance = candidate.score

                # Diversity penalty: consider both preselected AND newly selected
                max_similarity_to_selected = 0.0
                for sel in all_selected:
                    if candidate.video_id == sel.video_id:
                        proximity_similarity = self._compute_proximity_similarity(
                            candidate, sel
                        )
                        similarity = 0.7 + 0.3 * proximity_similarity
                    else:
                        similarity = 0.1

                    max_similarity_to_selected = max(
                        max_similarity_to_selected, similarity
                    )

                mmr_score = (
                    lambda_param * relevance
                    - (1 - lambda_param) * max_similarity_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            # Add best candidate to both selected and all_selected
            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            all_selected.append(chosen)

        return selected

    def _apply_mmr(
        self,
        query_embedding: np.ndarray,
        candidates: List[ScoredChunk],
        top_k: int,
        diversity: float,
    ) -> List[ScoredChunk]:
        """
        Apply Maximal Marginal Relevance (MMR) reranking.

        MMR balances relevance to query with diversity among selected documents.
        Formula: MMR = λ * sim(doc, query) - (1-λ) * max(sim(doc, selected))

        Where λ = (1 - diversity), so higher diversity means more penalty for similarity
        to already-selected documents.
        """
        if not candidates:
            return []

        # λ parameter: higher means more weight on relevance, lower means more diversity
        lambda_param = 1.0 - diversity

        selected: List[ScoredChunk] = []
        remaining = list(candidates)

        # We use video_id and timestamp as a proxy for diversity
        # Chunks from the same video at similar timestamps are considered more similar

        while len(selected) < top_k and remaining:
            best_score = float("-inf")
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # Relevance component: original similarity score (normalized 0-1)
                relevance = candidate.score

                # Diversity component: penalty if same source already selected
                max_similarity_to_selected = 0.0
                for sel in selected:
                    # Source-based similarity: high if same source, low otherwise
                    if candidate.video_id == sel.video_id:
                        # Same source - high similarity, scaled by proximity
                        proximity_similarity = self._compute_proximity_similarity(
                            candidate, sel
                        )
                        similarity = 0.7 + 0.3 * proximity_similarity
                    else:
                        # Different source - low similarity
                        similarity = 0.1

                    max_similarity_to_selected = max(
                        max_similarity_to_selected, similarity
                    )

                # MMR score: balance relevance with diversity
                mmr_score = (
                    lambda_param * relevance
                    - (1 - lambda_param) * max_similarity_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            # Add best candidate to selected
            selected.append(remaining.pop(best_idx))

        return selected

    def _compute_proximity_similarity(
        self, chunk_a: ScoredChunk, chunk_b: ScoredChunk
    ) -> float:
        """
        Compute proximity-based similarity between two chunks from the same source.

        For videos: uses timestamp proximity (closer timestamps = more similar).
        For documents: uses page proximity (closer pages = more similar).
        """
        if chunk_a.is_document:
            # Document: use page proximity
            page_a = chunk_a.page_number or 0
            page_b = chunk_b.page_number or 0
            page_diff = abs(page_a - page_b)
            # Within 2 pages = very similar, 10+ pages = dissimilar
            return max(0.0, 1.0 - page_diff / 10.0)
        else:
            # Video: use timestamp proximity
            time_diff = abs(chunk_a.start_timestamp - chunk_b.start_timestamp)
            # Closer timestamps = more similar (within 60s = very similar)
            return max(0.0, 1.0 - time_diff / 300.0)

    def search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[ScoredChunk]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query embedding vector
            user_id: Optional user ID filter
            video_ids: Optional list of video IDs to search within
            top_k: Number of results to return
            filters: Optional additional filters (e.g., {"chapter_title": "Introduction"})

        Returns:
            List of scored chunks ordered by relevance
        """
        # Build filter conditions
        must_conditions = []
        should_conditions = []

        if user_id:
            must_conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
            )

        if video_ids:
            # Filter by video IDs (match any - OR logic)
            for video_id in video_ids:
                should_conditions.append(
                    FieldCondition(
                        key="video_id", match=MatchValue(value=str(video_id))
                    )
                )

        # Add custom filters
        if filters:
            for key, value in filters.items():
                must_conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        # Build Qdrant filter
        query_filter = None
        if must_conditions or should_conditions:
            query_filter = Filter(
                must=must_conditions if must_conditions else None,
                should=should_conditions if should_conditions else None,
            )

        # Perform search
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            query_filter=query_filter,
            limit=top_k,
        )

        # Convert results to ScoredChunk objects
        scored_chunks = []

        for result in search_results:
            payload = result.payload

            chunk_db_id_raw = payload.get("chunk_db_id")
            chunk_index_raw = payload.get("chunk_id")
            chunk_db_id = UUID(chunk_db_id_raw) if chunk_db_id_raw else None
            chunk_index = int(chunk_index_raw) if chunk_index_raw is not None else None

            chunk_identifier: Optional[UUID] = chunk_db_id
            if chunk_identifier is None:
                try:
                    # Provide a stable, per-video chunk identifier when DB id is not stored
                    video_uuid = UUID(payload["video_id"])
                    if chunk_index is not None:
                        chunk_identifier = uuid.uuid5(video_uuid, str(chunk_index))
                    else:
                        chunk_identifier = video_uuid
                except Exception:
                    chunk_identifier = None

            scored_chunk = ScoredChunk(
                chunk_id=chunk_identifier,
                video_id=UUID(payload["video_id"]),
                user_id=UUID(payload["user_id"]),
                text=payload["text"],
                start_timestamp=payload["start_timestamp"],
                end_timestamp=payload["end_timestamp"],
                score=result.score,
                chunk_index=chunk_index,
                content_type=payload.get("content_type", "youtube"),
                page_number=payload.get("page_number"),
                section_heading=payload.get("section_heading"),
                title=payload.get("title"),
                summary=payload.get("summary"),
                keywords=payload.get("keywords"),
                chapter_title=payload.get("chapter_title"),
                speakers=payload.get("speakers"),
            )

            scored_chunks.append(scored_chunk)

        return scored_chunks

    def fetch_video_chunk_vectors(
        self,
        *,
        user_id: UUID,
        video_ids: Sequence[UUID],
        limit: int = 256,
    ) -> Dict[Tuple[UUID, int], np.ndarray]:
        """
        Fetch stored embeddings for a user's videos from Qdrant.

        Returns a mapping keyed by (video_id, chunk_index) so callers can join
        back to DB chunks without relying on internal Qdrant point IDs.
        """

        if not video_ids:
            return {}

        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
        ]
        should_conditions = [
            FieldCondition(key="video_id", match=MatchValue(value=str(video_id)))
            for video_id in video_ids
        ]

        scroll_filter = Filter(
            must=must_conditions,
            should=should_conditions,
        )

        out: Dict[Tuple[UUID, int], np.ndarray] = {}
        offset = None

        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                with_payload=["video_id", "chunk_id"],
                with_vectors=True,
                limit=limit,
                offset=offset,
            )

            if not records:
                break

            for record in records:
                payload = record.payload or {}
                video_id_raw = payload.get("video_id")
                chunk_id_raw = payload.get("chunk_id")

                if not video_id_raw or chunk_id_raw is None:
                    continue

                try:
                    video_id = UUID(str(video_id_raw))
                    chunk_index = int(chunk_id_raw)
                except Exception:
                    continue

                vector = getattr(record, "vector", None)
                if vector is None:
                    continue

                # qdrant-client can return a named vectors dict.
                if isinstance(vector, dict):
                    vector = next(iter(vector.values()), None)
                if vector is None:
                    continue

                try:
                    out[(video_id, chunk_index)] = np.asarray(vector, dtype=np.float32)
                except Exception:
                    continue

            if offset is None:
                break

        return out

    def delete_by_video_id(self, video_id: UUID):
        """
        Delete all chunks for a video.

        Args:
            video_id: Video ID
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="video_id", match=MatchValue(value=str(video_id))
                    )
                ]
            ),
        )

        print(f"Deleted chunks for video {video_id}")

    def get_stats(self) -> Dict:
        """
        Get collection statistics.

        Returns:
            Dictionary with stats (total points, etc.)
        """
        collection_info = self.client.get_collection(self.collection_name)

        return {
            "total_points": collection_info.points_count,
            "vectors_count": collection_info.vectors_count,
            "indexed_vectors_count": collection_info.indexed_vectors_count,
            "collection_name": self.collection_name,
        }


class VectorStoreService:
    """
    High-level vector store service.

    Provides convenient methods for common operations.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize vector store service.

        Args:
            vector_store: Vector store implementation (defaults to Qdrant)
        """
        self.vector_store = vector_store or QdrantVectorStore()

    def initialize(self, dimensions: int, collection_name: Optional[str] = None):
        """
        Initialize vector store (create collection if needed).

        Args:
            dimensions: Embedding dimensions
        """
        if collection_name and isinstance(self.vector_store, QdrantVectorStore):
            self.vector_store = QdrantVectorStore(
                host=self.vector_store.host,
                port=self.vector_store.port,
                collection_name=collection_name,
            )
        self.vector_store.create_collection(dimensions)

    def index_video_chunks(
        self,
        enriched_chunks: List[EnrichedChunk],
        embeddings: List[np.ndarray],
        user_id: UUID,
        video_id: UUID,
        content_type: str = "youtube",
    ):
        """
        Index all chunks for a video or document.

        Args:
            enriched_chunks: List of enriched chunks
            embeddings: List of embeddings
            user_id: User ID
            video_id: Video/content ID
            content_type: Content type ('youtube', 'pdf', etc.)
        """
        self.vector_store.index_chunks(
            enriched_chunks, embeddings, user_id, video_id, content_type=content_type
        )

    def search_chunks(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None,
        collection_name: Optional[str] = None,
    ) -> List[ScoredChunk]:
        """
        Search for relevant chunks.

        Args:
            query_embedding: Query embedding
            user_id: Optional user ID filter
            video_ids: Optional video IDs filter
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of scored chunks
        """
        if collection_name and isinstance(self.vector_store, QdrantVectorStore):
            self.vector_store = QdrantVectorStore(
                host=self.vector_store.host,
                port=self.vector_store.port,
                collection_name=collection_name,
            )

        return self.vector_store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=top_k,
            filters=filters,
        )

    def search_with_diversity(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        diversity: float = 0.5,
        prefetch_limit: int = 100,
        filters: Optional[Dict] = None,
        collection_name: Optional[str] = None,
    ) -> List[ScoredChunk]:
        """
        Search for relevant chunks with diversity-aware retrieval (MMR).

        Uses Maximal Marginal Relevance to balance relevance with diversity,
        ensuring results span multiple videos when applicable.

        Args:
            query_embedding: Query embedding
            user_id: Optional user ID filter
            video_ids: Optional video IDs filter
            top_k: Number of results
            diversity: Diversity factor (0.0 = relevance only, 1.0 = max diversity)
            prefetch_limit: Candidates to fetch before MMR reranking
            filters: Optional filters
            collection_name: Optional collection name override

        Returns:
            List of scored chunks with diverse representation
        """
        if collection_name and isinstance(self.vector_store, QdrantVectorStore):
            self.vector_store = QdrantVectorStore(
                host=self.vector_store.host,
                port=self.vector_store.port,
                collection_name=collection_name,
            )

        if isinstance(self.vector_store, QdrantVectorStore):
            return self.vector_store.search_with_diversity(
                query_embedding=query_embedding,
                user_id=user_id,
                video_ids=video_ids,
                top_k=top_k,
                diversity=diversity,
                prefetch_limit=prefetch_limit,
                filters=filters,
            )

        # Fallback to regular search for non-Qdrant stores
        return self.vector_store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=top_k,
            filters=filters,
        )

    def search_with_video_guarantee(
        self,
        query_embedding: np.ndarray,
        video_ids: List[UUID],
        user_id: UUID,
        top_k: int = 10,
        prefetch_limit: int = 100,
        collection_name: Optional[str] = None,
    ) -> List[ScoredChunk]:
        """
        Search with guaranteed minimum 1 chunk per video.

        For summarize queries across multiple videos, ensures every video
        gets at least one representative chunk in the results.

        Args:
            query_embedding: Query embedding
            video_ids: Video IDs to search (all should be represented)
            user_id: User ID filter
            top_k: Number of results
            prefetch_limit: Candidates to fetch before selection
            collection_name: Optional collection name override

        Returns:
            List of scored chunks with guaranteed video representation
        """
        if collection_name and isinstance(self.vector_store, QdrantVectorStore):
            self.vector_store = QdrantVectorStore(
                host=self.vector_store.host,
                port=self.vector_store.port,
                collection_name=collection_name,
            )

        if isinstance(self.vector_store, QdrantVectorStore):
            return self.vector_store.search_with_video_guarantee(
                query_embedding=query_embedding,
                video_ids=video_ids,
                user_id=user_id,
                top_k=top_k,
                prefetch_limit=prefetch_limit,
            )

        # Fallback to regular search for non-Qdrant stores
        return self.vector_store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=top_k,
        )

    def fetch_video_chunk_vectors(
        self,
        *,
        user_id: UUID,
        video_ids: Sequence[UUID],
        collection_name: Optional[str] = None,
    ) -> Dict[Tuple[UUID, int], np.ndarray]:
        """
        Fetch stored vectors for a user's videos (Qdrant only).

        This is used to reuse existing chunk embeddings for analytics/insights so
        we don't re-embed every chunk at generation time.
        """
        if collection_name and isinstance(self.vector_store, QdrantVectorStore):
            self.vector_store = QdrantVectorStore(
                host=self.vector_store.host,
                port=self.vector_store.port,
                collection_name=collection_name,
            )

        if isinstance(self.vector_store, QdrantVectorStore):
            return self.vector_store.fetch_video_chunk_vectors(
                user_id=user_id, video_ids=video_ids
            )
        return {}

    def delete_video(self, video_id: UUID):
        """
        Delete all chunks for a video.

        Args:
            video_id: Video ID
        """
        self.vector_store.delete_by_video_id(video_id)

    def get_stats(self) -> Dict:
        """Get vector store statistics."""
        return self.vector_store.get_stats()


# Global vector store service instance
vector_store_service = VectorStoreService()
