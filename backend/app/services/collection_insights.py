"""
Collection-level insights service.

Generates a topic graph across ALL videos in a collection using the same
LLM extraction + embedding assignment pipeline as conversation insights.
Results are cached in the collection_insights table.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Collection, CollectionVideo, Video
from app.models.collection_insight import CollectionInsight
from app.services.insights import (
    ConversationInsightsService,
    EXTRACTION_PROMPT_VERSION,
    _canonicalize_video_ids,
)

logger = logging.getLogger(__name__)

# Limit chunks analyzed for collections to control cost
COLLECTION_MAX_CHUNKS = 100


class CollectionInsightsService:
    def __init__(self) -> None:
        self._insights_service = ConversationInsightsService()

    def get_or_generate_insights(
        self,
        db: Session,
        collection_id: uuid.UUID,
        user_id: uuid.UUID,
        force_regenerate: bool = False,
    ) -> Tuple[CollectionInsight, bool]:
        """
        Get cached or generate new insights for a collection.

        Returns (insight_row, was_cached).
        """
        # Get all completed video IDs in the collection
        video_ids = self._get_collection_video_ids(db, collection_id, user_id)
        if not video_ids:
            raise ValueError("No completed videos in this collection")

        canonical_video_ids = _canonicalize_video_ids(video_ids)

        # Check cache
        existing: Optional[CollectionInsight] = (
            db.query(CollectionInsight)
            .filter(
                CollectionInsight.collection_id == collection_id,
                CollectionInsight.user_id == user_id,
            )
            .order_by(CollectionInsight.created_at.desc())
            .first()
        )

        if existing and not force_regenerate:
            existing_video_ids = _canonicalize_video_ids(existing.video_ids or [])
            if existing_video_ids == canonical_video_ids:
                needs_upgrade = (
                    self._insights_service._graph_needs_upgrade(existing.graph_data)
                    or (existing.extraction_prompt_version or 0) != EXTRACTION_PROMPT_VERSION
                )
                if not needs_upgrade:
                    return existing, True

        # Get collection name for root label
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        root_label = collection.name if collection else "Collection"

        # Generate insights using the shared extraction pipeline
        insights = self._insights_service.extract_topics_from_videos(
            db,
            user_id=user_id,
            video_ids=canonical_video_ids,
            root_label=root_label,
            max_chunks_analyzed=COLLECTION_MAX_CHUNKS,
        )

        now = datetime.utcnow()
        graph_data = insights.graph_dict()
        topic_chunks = insights.topic_chunks_dict()

        llm_provider = insights.metadata.get("llm_provider")
        llm_model = insights.metadata.get("llm_model")
        topics_count = int(insights.metadata.get("topics_count") or 0)
        if topics_count <= 0:
            topics_count = sum(
                1 for n in (graph_data.get("nodes") or []) if n.get("type") == "topic"
            )
        total_chunks_analyzed = int(insights.metadata.get("total_chunks_analyzed") or 0)
        generation_time_seconds = float(
            insights.metadata.get("generation_time_seconds") or 0.0
        )

        if existing:
            existing.video_ids = canonical_video_ids
            existing.llm_provider = llm_provider
            existing.llm_model = llm_model
            existing.extraction_prompt_version = EXTRACTION_PROMPT_VERSION
            existing.graph_data = graph_data
            existing.topic_chunks = topic_chunks
            existing.topics_count = topics_count
            existing.total_chunks_analyzed = total_chunks_analyzed
            existing.generation_time_seconds = generation_time_seconds
            existing.created_at = now
            db.commit()
            db.refresh(existing)
            return existing, False

        new_row = CollectionInsight(
            id=uuid.uuid4(),
            collection_id=collection_id,
            user_id=user_id,
            video_ids=canonical_video_ids,
            llm_provider=llm_provider,
            llm_model=llm_model,
            extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
            graph_data=graph_data,
            topic_chunks=topic_chunks,
            topics_count=topics_count,
            total_chunks_analyzed=total_chunks_analyzed,
            generation_time_seconds=generation_time_seconds,
            created_at=now,
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return new_row, False

    @staticmethod
    def _get_collection_video_ids(
        db: Session,
        collection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[uuid.UUID]:
        """Get IDs of all completed videos in the collection."""
        results = (
            db.query(Video.id)
            .join(CollectionVideo, CollectionVideo.video_id == Video.id)
            .filter(
                CollectionVideo.collection_id == collection_id,
                Video.user_id == user_id,
                Video.is_deleted.is_(False),
                Video.status == "completed",
            )
            .all()
        )
        return [r[0] for r in results]


collection_insights_service = CollectionInsightsService()
