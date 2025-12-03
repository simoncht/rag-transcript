"""
API endpoints for conversation management.

Endpoints:
- POST /conversations - Create new conversation
- GET /conversations - List conversations
- GET /conversations/{conversation_id} - Get conversation details
- PATCH /conversations/{conversation_id} - Update conversation
- DELETE /conversations/{conversation_id} - Delete conversation
- POST /conversations/{conversation_id}/messages - Send message (TODO: Phase 2)
"""
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import Conversation, Video, User
from app.schemas import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationDetail,
    ConversationList,
    ConversationWithMessages,
    MessageSendRequest,
    MessageResponse,
)
from app.api.routes.videos import get_current_user

router = APIRouter()


@router.post("", response_model=ConversationDetail)
async def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new conversation.

    Args:
        request: Conversation creation request with title and video IDs

    Returns:
        ConversationDetail with created conversation
    """
    # Validate that all videos exist and belong to user
    videos = db.query(Video).filter(
        Video.id.in_(request.selected_video_ids),
        Video.user_id == current_user.id,
        Video.is_deleted == False,
        Video.status == "completed"
    ).all()

    if len(videos) != len(request.selected_video_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more videos not found or not completed processing"
        )

    # Auto-generate title if not provided
    title = request.title
    if not title:
        if len(videos) == 1:
            title = f"Chat about {videos[0].title[:50]}"
        else:
            title = f"Chat about {len(videos)} videos"

    # Create conversation
    conversation = Conversation(
        user_id=current_user.id,
        title=title,
        selected_video_ids=[str(v.id) for v in videos],
        message_count=0,
        total_tokens_used=0
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationDetail.model_validate(conversation)


@router.get("", response_model=ConversationList)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List user's conversations with pagination.

    Args:
        skip: Number of records to skip
        limit: Number of records to return

    Returns:
        ConversationList with conversations and total count
    """
    query = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    )

    total = query.count()

    conversations = query.order_by(
        Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()

    return ConversationList(
        total=total,
        conversations=[ConversationDetail.model_validate(c) for c in conversations]
    )


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get conversation details with full message history.

    Args:
        conversation_id: Conversation UUID

    Returns:
        ConversationWithMessages including all messages and chunk references
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # TODO: Load messages with chunk references
    # For now, return conversation without messages
    return ConversationWithMessages(
        **ConversationDetail.model_validate(conversation).model_dump(),
        messages=[]
    )


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: uuid.UUID,
    request: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update conversation (title or selected videos).

    Args:
        conversation_id: Conversation UUID
        request: Update request with optional title and video IDs

    Returns:
        ConversationDetail with updated conversation
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update title if provided
    if request.title is not None:
        conversation.title = request.title

    # Update selected videos if provided
    if request.selected_video_ids is not None:
        # Validate videos
        videos = db.query(Video).filter(
            Video.id.in_(request.selected_video_ids),
            Video.user_id == current_user.id,
            Video.is_deleted == False,
            Video.status == "completed"
        ).all()

        if len(videos) != len(request.selected_video_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more videos not found or not completed"
            )

        conversation.selected_video_ids = [str(v.id) for v in videos]

    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)

    return ConversationDetail.model_validate(conversation)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation.

    Args:
        conversation_id: Conversation UUID

    Returns:
        Success message
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted successfully", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a message in a conversation (RAG chat).

    TODO: Phase 2 implementation
    - Embed user query
    - Retrieve relevant chunks from vector store
    - Optional re-ranking
    - Build prompt with context
    - Generate LLM response
    - Save message and chunk references
    - Track usage

    Args:
        conversation_id: Conversation UUID
        request: Message request with text and stream option

    Returns:
        MessageResponse with assistant reply and chunk references
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # TODO: Implement RAG chat logic (Phase 2)
    raise HTTPException(
        status_code=501,
        detail="Chat functionality will be implemented in Phase 2"
    )
