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

    Implements full RAG pipeline:
    1. Embed user query
    2. Retrieve relevant chunks from vector store
    3. Build prompt with context and conversation history
    4. Generate LLM response
    5. Save messages and chunk references
    6. Track usage

    Args:
        conversation_id: Conversation UUID
        request: Message request with text and stream option

    Returns:
        MessageResponse with assistant reply and chunk references
    """
    import time
    import numpy as np
    from app.services.embeddings import embedding_service
    from app.services.vector_store import vector_store_service
    from app.services.llm_providers import llm_service, Message as LLMMessage
    from app.models import Message, MessageChunkReference, Chunk, Video
    from app.core.config import settings

    start_time = time.time()

    # 1. Verify conversation exists and belongs to user
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. Save user message
    user_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=request.message,
        token_count=len(request.message.split()),  # Simple approximation
    )
    db.add(user_message)
    db.commit()

    # 3. Embed user query
    query_embedding = embedding_service.embed_text(request.message)
    if isinstance(query_embedding, tuple):
        query_embedding = np.array(query_embedding, dtype=np.float32)

    # 4. Retrieve relevant chunks from vector store (filtered by conversation's videos)
    scored_chunks = vector_store_service.search_chunks(
        query_embedding=query_embedding,
        user_id=current_user.id,
        video_ids=conversation.selected_video_ids,
        top_k=settings.retrieval_top_k
    )

    # 5. Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(scored_chunks[:5], 1):  # Use top 5 for context
        context_parts.append(
            f"[Source {i}] (Relevance: {chunk.score:.2f})\n"
            f"Timestamp: {chunk.start_timestamp:.1f}s - {chunk.end_timestamp:.1f}s\n"
            f"{chunk.text}\n"
        )

    context = "\n---\n".join(context_parts) if context_parts else "No relevant context found."

    # 6. Get conversation history (last 5 messages)
    history_messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.desc()).limit(5).all()
    history_messages.reverse()  # Oldest first

    # 7. Build LLM messages
    llm_messages = [
        LLMMessage(
            role="system",
            content=(
                "You are a helpful AI assistant that answers questions based on video transcripts. "
                "Use the provided context to answer the user's question. "
                "If the context doesn't contain relevant information, say so honestly. "
                "Always cite the source number when referencing information from the context."
            )
        )
    ]

    # Add conversation history (excluding the message we just added)
    for msg in history_messages[:-1]:
        llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

    # Add current user message with context
    user_message_with_context = (
        f"Context from video transcripts:\n\n{context}\n\n"
        f"---\n\nUser question: {request.message}"
    )
    llm_messages.append(LLMMessage(role="user", content=user_message_with_context))

    # 8. Generate LLM response
    try:
        llm_response = llm_service.complete(llm_messages)
        assistant_content = llm_response.content
        token_count = llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # 9. Save assistant message
    assistant_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_count=token_count,
        chunks_retrieved_count=len(scored_chunks),
        response_time_seconds=time.time() - start_time
    )
    db.add(assistant_message)

    # 10. Save chunk references
    chunk_references = []
    chunk_index_map = {}  # Map (video_id, chunk_index) -> chunk_db

    for rank, scored_chunk in enumerate(scored_chunks[:5], 1):  # Save top 5 references
        # Get the actual chunk from database to get its ID
        # The chunk_id from Qdrant is actually the video_id (set incorrectly in vector_store.py)
        # We need to use timestamps to match chunks
        chunk_db = db.query(Chunk).filter(
            Chunk.video_id == scored_chunk.video_id,
            Chunk.start_timestamp == scored_chunk.start_timestamp,
            Chunk.end_timestamp == scored_chunk.end_timestamp
        ).first()

        if chunk_db:
            ref = MessageChunkReference(
                id=uuid.uuid4(),
                message_id=assistant_message.id,
                chunk_id=chunk_db.id,
                relevance_score=scored_chunk.score,
                rank=rank
            )
            db.add(ref)
            chunk_references.append(ref)

    # 11. Update conversation metadata
    conversation.message_count = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).count()
    conversation.total_tokens_used += token_count
    conversation.last_message_at = assistant_message.created_at

    db.commit()
    db.refresh(assistant_message)

    # 12. Build response with chunk references
    response_time = time.time() - start_time

    chunk_refs_response = []
    for scored_chunk, ref in zip(scored_chunks[:5], chunk_references):
        # Get video title
        video = db.query(Video).filter(Video.id == scored_chunk.video_id).first()

        # Format timestamp
        start_min, start_sec = divmod(int(scored_chunk.start_timestamp), 60)
        end_min, end_sec = divmod(int(scored_chunk.end_timestamp), 60)
        timestamp_display = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"

        chunk_refs_response.append({
            "chunk_id": ref.chunk_id,
            "video_id": scored_chunk.video_id,
            "video_title": video.title if video else "Unknown",
            "start_timestamp": scored_chunk.start_timestamp,
            "end_timestamp": scored_chunk.end_timestamp,
            "text_snippet": scored_chunk.text[:200] + "..." if len(scored_chunk.text) > 200 else scored_chunk.text,
            "relevance_score": scored_chunk.score,
            "timestamp_display": timestamp_display
        })

    return MessageResponse(
        message_id=assistant_message.id,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        chunk_references=chunk_refs_response,
        token_count=token_count,
        response_time_seconds=response_time
    )
