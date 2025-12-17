"""
API endpoints for conversation insights.

Endpoints:
- GET /conversations/{conversation_id}/insights
- GET /conversations/{conversation_id}/insights/topics/{topic_id}/chunks
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models import Conversation, ConversationSource, User
from app.schemas import ConversationInsightsResponse, TopicChunksResponse
from app.services.insights import insights_service


router = APIRouter()


@router.get("/{conversation_id}/insights", response_model=ConversationInsightsResponse)
async def get_conversation_insights(
    conversation_id: uuid.UUID,
    regenerate: bool = Query(
        False, description="Force regeneration even if cache exists"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id, Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    selected_video_ids = [
        row.video_id
        for row in db.query(ConversationSource.video_id)
        .filter(
            ConversationSource.conversation_id == conversation_id,
            ConversationSource.is_selected == True,  # noqa: E712
        )
        .all()
    ]

    if not selected_video_ids:
        selected_video_ids = list(conversation.selected_video_ids or [])

    if not selected_video_ids:
        raise HTTPException(
            status_code=400, detail="No videos selected for this conversation"
        )

    insight, cached = insights_service.get_or_generate_insights(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        video_ids=selected_video_ids,
        force_regenerate=regenerate,
        root_label=conversation.title or "Conversation",
    )

    return {
        "conversation_id": conversation_id,
        "graph": insight.graph_data,
        "metadata": {
            "topics_count": insight.topics_count,
            "total_chunks_analyzed": insight.total_chunks_analyzed,
            "generation_time_seconds": insight.generation_time_seconds,
            "cached": cached,
            "created_at": insight.created_at,
            "llm_provider": insight.llm_provider,
            "llm_model": insight.llm_model,
            "extraction_prompt_version": insight.extraction_prompt_version,
        },
    }


@router.get(
    "/{conversation_id}/insights/topics/{topic_id}/chunks",
    response_model=TopicChunksResponse,
)
async def get_topic_chunks(
    conversation_id: uuid.UUID,
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id, Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        return insights_service.get_topic_chunks(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            topic_id=topic_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
