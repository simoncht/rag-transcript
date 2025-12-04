"""
Vector store service for indexing and searching transcript chunks.

Provides abstraction over vector databases (currently Qdrant, could support pgvector later).
Handles embedding storage, similarity search, and filtering.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
from uuid import UUID
import uuid
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from app.core.config import settings
from app.services.enrichment import EnrichedChunk


@dataclass
class ScoredChunk:
    """
    Search result with relevance score.

    Attributes:
        chunk_id: UUID of the chunk
        video_id: UUID of the video
        user_id: UUID of the user
        text: Chunk text
        start_timestamp: Start time in seconds
        end_timestamp: End time in seconds
        score: Relevance score (0.0 to 1.0, higher is better)
        title: Chunk title (if available)
        summary: Chunk summary (if available)
        keywords: Chunk keywords (if available)
        chapter_title: Chapter title (if available)
    """
    chunk_id: UUID
    video_id: UUID
    user_id: UUID
    text: str
    start_timestamp: float
    end_timestamp: float
    score: float
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    chapter_title: Optional[str] = None


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def create_collection(self, dimensions: int):
        """Create collection if it doesn't exist."""
        pass

    @abstractmethod
    def index_chunks(self, enriched_chunks: List[EnrichedChunk], embeddings: List[np.ndarray], user_id: UUID, video_id: UUID):
        """Index chunks with embeddings."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None
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

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None
    ):
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
        self.client = QdrantClient(host=self.host, port=self.port)

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
                    size=dimensions,
                    distance=Distance.COSINE  # Cosine similarity
                )
            )
            print(f"Created Qdrant collection: {self.collection_name}")
        else:
            print(f"Qdrant collection already exists: {self.collection_name}")

    def index_chunks(
        self,
        enriched_chunks: List[EnrichedChunk],
        embeddings: List[np.ndarray],
        user_id: UUID,
        video_id: UUID
    ):
        """
        Index enriched chunks with their embeddings.

        Args:
            enriched_chunks: List of enriched chunks
            embeddings: List of embedding vectors (same length as enriched_chunks)
            user_id: User ID
            video_id: Video ID
        """
        if len(enriched_chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        points = []

        for enriched_chunk, embedding in zip(enriched_chunks, embeddings):
            chunk = enriched_chunk.chunk

            # Prepare payload (metadata)
            payload = {
                "chunk_id": str(chunk.chunk_index),  # Use chunk_index as id within video
                "video_id": str(video_id),
                "user_id": str(user_id),
                "text": chunk.text,
                "start_timestamp": chunk.start_timestamp,
                "end_timestamp": chunk.end_timestamp,
                "duration_seconds": chunk.duration_seconds,
                "token_count": chunk.token_count,
            }

            # Add enrichment metadata if available
            if enriched_chunk.title:
                payload["title"] = enriched_chunk.title
            if enriched_chunk.summary:
                payload["summary"] = enriched_chunk.summary
            if enriched_chunk.keywords:
                payload["keywords"] = enriched_chunk.keywords

            # Add optional fields
            if chunk.speakers:
                payload["speakers"] = chunk.speakers
            if chunk.chapter_title:
                payload["chapter_title"] = chunk.chapter_title
                payload["chapter_index"] = chunk.chapter_index

            # Create point with unique ID (video_id + chunk_index)
            point_id = str(uuid.uuid5(video_id, str(chunk.chunk_index)))

            point = PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload=payload
            )

            points.append(point)

        # Upsert points to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        print(f"Indexed {len(points)} chunks for video {video_id}")

    def search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None
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
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=str(user_id))
                )
            )

        if video_ids:
            # Filter by video IDs (match any - OR logic)
            for video_id in video_ids:
                should_conditions.append(
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=str(video_id))
                    )
                )

        # Add custom filters
        if filters:
            for key, value in filters.items():
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )

        # Build Qdrant filter
        query_filter = None
        if must_conditions or should_conditions:
            query_filter = Filter(
                must=must_conditions if must_conditions else None,
                should=should_conditions if should_conditions else None
            )

        # Perform search
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            query_filter=query_filter,
            limit=top_k
        )

        # Convert results to ScoredChunk objects
        scored_chunks = []

        for result in search_results:
            payload = result.payload

            scored_chunk = ScoredChunk(
                chunk_id=UUID(payload["video_id"]),  # Will be properly set from DB
                video_id=UUID(payload["video_id"]),
                user_id=UUID(payload["user_id"]),
                text=payload["text"],
                start_timestamp=payload["start_timestamp"],
                end_timestamp=payload["end_timestamp"],
                score=result.score,
                title=payload.get("title"),
                summary=payload.get("summary"),
                keywords=payload.get("keywords"),
                chapter_title=payload.get("chapter_title")
            )

            scored_chunks.append(scored_chunk)

        return scored_chunks

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
                        key="video_id",
                        match=MatchValue(value=str(video_id))
                    )
                ]
            )
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

    def initialize(self, dimensions: int):
        """
        Initialize vector store (create collection if needed).

        Args:
            dimensions: Embedding dimensions
        """
        self.vector_store.create_collection(dimensions)

    def index_video_chunks(
        self,
        enriched_chunks: List[EnrichedChunk],
        embeddings: List[np.ndarray],
        user_id: UUID,
        video_id: UUID
    ):
        """
        Index all chunks for a video.

        Args:
            enriched_chunks: List of enriched chunks
            embeddings: List of embeddings
            user_id: User ID
            video_id: Video ID
        """
        self.vector_store.index_chunks(enriched_chunks, embeddings, user_id, video_id)

    def search_chunks(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[UUID] = None,
        video_ids: Optional[List[UUID]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None
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
        return self.vector_store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            video_ids=video_ids,
            top_k=top_k,
            filters=filters
        )

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
