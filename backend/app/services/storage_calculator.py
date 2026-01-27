"""
Storage calculator service for comprehensive billing.

Calculates storage usage across PostgreSQL database and Qdrant vectors
for accurate billing based on actual storage footprint.
"""
from uuid import UUID

from sqlalchemy import func, String
from sqlalchemy.orm import Session

from app.models import Chunk, Message, ConversationFact, ConversationInsight, Conversation, Video


# Estimated bytes per vector in Qdrant (1536 dimensions * 4 bytes + metadata overhead)
BYTES_PER_VECTOR = 5 * 1024  # ~5 KB per vector


class StorageCalculator:
    """
    Calculates storage usage for billing purposes.

    Includes:
    - Database storage: text content in chunks, messages, facts, insights
    - Vector storage: estimated from chunk count
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_database_storage_mb(self, user_id: UUID) -> float:
        """
        Calculate PostgreSQL storage used by a user.

        Sums text field lengths from:
        - Chunks: text, chunk_summary, embedding_text
        - Messages: content
        - Conversation facts: fact_value
        - Conversation insights: graph_data (JSONB)

        Returns:
            Storage in megabytes
        """
        total_bytes = 0

        # Chunk storage: text + summary + embedding_text
        # Only count chunks from non-deleted videos
        chunk_bytes = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        func.length(Chunk.text)
                        + func.coalesce(func.length(Chunk.chunk_summary), 0)
                        + func.coalesce(func.length(Chunk.embedding_text), 0)
                    ),
                    0,
                )
            )
            .join(Video, Chunk.video_id == Video.id)
            .filter(Chunk.user_id == user_id, Video.is_deleted.is_(False))
            .scalar()
            or 0
        )
        total_bytes += chunk_bytes

        # Message storage: content
        # Need to join through Conversation to filter by user_id
        message_bytes = (
            self.db.query(func.coalesce(func.sum(func.length(Message.content)), 0))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user_id)
            .scalar()
            or 0
        )
        total_bytes += message_bytes

        # Conversation facts storage: fact_value
        fact_bytes = (
            self.db.query(
                func.coalesce(func.sum(func.length(ConversationFact.fact_value)), 0)
            )
            .filter(ConversationFact.user_id == user_id)
            .scalar()
            or 0
        )
        total_bytes += fact_bytes

        # Conversation insights storage: graph_data (JSONB cast to text for length)
        # JSONB doesn't have a direct length function, so we cast to text
        insight_bytes = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        func.length(func.cast(ConversationInsight.graph_data, String))
                        + func.length(func.cast(ConversationInsight.topic_chunks, String))
                    ),
                    0,
                )
            )
            .filter(ConversationInsight.user_id == user_id)
            .scalar()
            or 0
        )
        total_bytes += insight_bytes

        # Convert bytes to megabytes
        return total_bytes / (1024 * 1024)

    def calculate_vector_storage_mb(self, user_id: UUID) -> float:
        """
        Estimate Qdrant vector storage used by a user.

        Uses chunk count * estimated bytes per vector.
        This avoids expensive Qdrant API calls while providing
        a reasonable estimate for billing.

        Returns:
            Estimated storage in megabytes
        """
        # Only count chunks from non-deleted videos
        chunk_count = (
            self.db.query(func.count(Chunk.id))
            .join(Video, Chunk.video_id == Video.id)
            .filter(
                Chunk.user_id == user_id,
                Chunk.is_indexed.is_(True),
                Video.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )

        # Calculate estimated bytes and convert to MB
        estimated_bytes = chunk_count * BYTES_PER_VECTOR
        return estimated_bytes / (1024 * 1024)

    def calculate_total_storage_mb(self, user_id: UUID) -> dict:
        """
        Calculate all storage components for a user.

        Returns:
            Dict with database_mb, vector_mb, and total_mb
        """
        database_mb = self.calculate_database_storage_mb(user_id)
        vector_mb = self.calculate_vector_storage_mb(user_id)

        return {
            "database_mb": round(database_mb, 3),
            "vector_mb": round(vector_mb, 3),
            "total_mb": round(database_mb + vector_mb, 3),
        }
