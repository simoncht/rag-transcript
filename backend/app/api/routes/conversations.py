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
import textwrap
import uuid
from typing import Optional, List, Dict, Set
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import Conversation, Video, User, Collection, CollectionVideo, ConversationSource
from app.schemas import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationDetail,
    ConversationList,
    ConversationWithMessages,
    MessageSendRequest,
    MessageResponse,
    ConversationSourcesResponse,
    ConversationSourcesUpdateRequest,
    ConversationSource as ConversationSourceSchema,
    MessageWithReferences,
    ChunkReference,
    Message as MessageSchema,
)
from app.api.routes.videos import get_current_user

router = APIRouter()


def _format_timestamp_display(start: float, end: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    start_h, start_rem = divmod(int(start), 3600)
    start_m, start_s = divmod(start_rem, 60)
    end_h, end_rem = divmod(int(end), 3600)
    end_m, end_s = divmod(end_rem, 60)

    if start_h or end_h:
        return f"{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}"
    return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"


def _validate_videos(
    db: Session, current_user: User, video_ids: List[uuid.UUID]
) -> List[Video]:
    """Validate that videos exist, belong to the user, are not deleted, and are completed."""
    if not video_ids:
        raise HTTPException(
            status_code=400,
            detail="Must specify at least one video.",
        )

    videos = (
        db.query(Video)
        .filter(
            Video.id.in_(video_ids),
            Video.user_id == current_user.id,
            Video.is_deleted == False,  # noqa: E712
            Video.status == "completed",
        )
        .all()
    )

    if len(videos) != len(set(video_ids)):
        raise HTTPException(
            status_code=400,
            detail="One or more videos not found or not completed processing",
        )
    return videos


def _sync_collection_sources(
    db: Session, conversation: Conversation, current_user: User
) -> None:
    """
    If the conversation is tied to a collection, attach any new collection videos as sources.
    Newly attached sources default to selected.
    """
    if not conversation.collection_id:
        return

    collection = (
        db.query(Collection)
        .filter(
            Collection.id == conversation.collection_id,
            Collection.user_id == current_user.id,
        )
        .first()
    )
    if not collection:
        return

    collection_video_ids = [
        cv.video_id
        for cv in db.query(CollectionVideo).filter(
            CollectionVideo.collection_id == conversation.collection_id
        )
    ]

    if not collection_video_ids:
        return

    existing_sources = {
        src.video_id
        for src in db.query(ConversationSource).filter(
            ConversationSource.conversation_id == conversation.id
        )
    }
    new_video_ids = [vid for vid in collection_video_ids if vid not in existing_sources]

    for vid in new_video_ids:
        db.add(
            ConversationSource(
                conversation_id=conversation.id,
                video_id=vid,
                is_selected=True,
                added_via="collection",
            )
        )

    if new_video_ids:
        _refresh_selected_video_ids(db, conversation)


def _refresh_selected_video_ids(db: Session, conversation: Conversation) -> None:
    """Sync the conversation.selected_video_ids array from selected ConversationSource rows."""
    selected_ids = [
        src.video_id
        for src in db.query(ConversationSource).filter(
            ConversationSource.conversation_id == conversation.id,
            ConversationSource.is_selected == True,  # noqa: E712
        )
    ]
    conversation.selected_video_ids = [uuid.UUID(str(v)) for v in selected_ids]
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)


def _ensure_conversation_owned(
    db: Session, conversation_id: uuid.UUID, current_user: User
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _set_sources_selection(
    db: Session,
    conversation: Conversation,
    selected_video_ids: Optional[List[uuid.UUID]],
    add_video_ids: Optional[List[uuid.UUID]],
    current_user: User,
) -> None:
    """
    Update conversation_sources selection state and optionally attach new videos.
    """
    add_video_ids = add_video_ids or []

    if add_video_ids:
        _validate_videos(db, current_user, add_video_ids)
        for vid in add_video_ids:
            existing = (
                db.query(ConversationSource)
                .filter(
                    ConversationSource.conversation_id == conversation.id,
                    ConversationSource.video_id == vid,
                )
                .first()
            )
            if existing:
                existing.is_selected = True
            else:
                db.add(
                    ConversationSource(
                        conversation_id=conversation.id,
                        video_id=vid,
                        is_selected=True,
                        added_via="manual",
                    )
                )

    if selected_video_ids is not None:
        selected_set: Set[uuid.UUID] = set(selected_video_ids)
        sources = db.query(ConversationSource).filter(
            ConversationSource.conversation_id == conversation.id
        )
        for src in sources:
            src.is_selected = src.video_id in selected_set

    _refresh_selected_video_ids(db, conversation)
@router.post("", response_model=ConversationDetail)
async def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new conversation.

    Can be created from:
    - A collection (collection_id): Uses all videos from the collection
    - Individual videos (selected_video_ids): Uses specified videos

    Args:
        request: Conversation creation request with title and collection_id OR video IDs

    Returns:
        ConversationDetail with created conversation
    """
    # Determine video IDs based on collection or direct selection
    if request.collection_id and request.selected_video_ids:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both collection_id and selected_video_ids. Choose one."
        )

    if not request.collection_id and not request.selected_video_ids:
        raise HTTPException(
            status_code=400,
            detail="Must specify either collection_id or selected_video_ids"
        )

    video_ids = []
    auto_sync_collection = request.auto_sync_collection if request.auto_sync_collection is not None else True

    if request.collection_id:
        # Get all videos from collection
        collection = db.query(Collection).filter(
            Collection.id == request.collection_id,
            Collection.user_id == current_user.id
        ).first()

        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Get video IDs from collection
        collection_videos = db.query(CollectionVideo.video_id).filter(
            CollectionVideo.collection_id == request.collection_id
        ).all()
        video_ids = [str(cv[0]) for cv in collection_videos]

        if not video_ids:
            raise HTTPException(
                status_code=400,
                detail="Collection has no videos"
            )
    else:
        video_ids = [str(vid) for vid in request.selected_video_ids]

    # Validate that all videos exist and belong to user
    videos = _validate_videos(db, current_user, [uuid.UUID(v) for v in video_ids])

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
        total_tokens_used=0,
        collection_id=request.collection_id if auto_sync_collection else None,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # Attach conversation sources
    for vid in videos:
        db.add(
            ConversationSource(
                conversation_id=conversation.id,
                video_id=vid.id,
                is_selected=True,
                added_via="collection" if request.collection_id else "manual",
            )
        )
    _refresh_selected_video_ids(db, conversation)

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

    # Sync any collection-backed conversations to include new videos
    for conv in conversations:
        _sync_collection_sources(db, conv, current_user)

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
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    # Load messages for this conversation
    from app.models import Message as MessageModel, MessageChunkReference, Chunk

    messages = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.asc())
        .all()
    )

    assistant_message_ids = [msg.id for msg in messages if msg.role == "assistant"]
    chunk_refs_map: Dict[uuid.UUID, List[ChunkReference]] = {}

    if assistant_message_ids:
        chunk_refs = (
            db.query(MessageChunkReference, Chunk, Video)
            .join(Chunk, MessageChunkReference.chunk_id == Chunk.id)
            .join(Video, Chunk.video_id == Video.id)
            .filter(MessageChunkReference.message_id.in_(assistant_message_ids))
            .order_by(MessageChunkReference.rank.asc())
            .all()
        )

        for ref, chunk, video in chunk_refs:
            chunk_refs_map.setdefault(ref.message_id, [])
            chunk_refs_map[ref.message_id].append(
                ChunkReference(
                    chunk_id=chunk.id,
                    video_id=chunk.video_id,
                    video_title=video.title if video else "Unknown",
                    start_timestamp=chunk.start_timestamp,
                    end_timestamp=chunk.end_timestamp,
                    text_snippet=chunk.text[:200]
                    + ("..." if len(chunk.text) > 200 else ""),
                    relevance_score=ref.relevance_score,
                    timestamp_display=_format_timestamp_display(
                        chunk.start_timestamp, chunk.end_timestamp
                    ),
                    rank=ref.rank,
                )
            )

    # Convert to response models
    message_details: List[MessageWithReferences] = []
    for msg in messages:
        base = MessageSchema.model_validate(msg).model_dump()
        message_details.append(
            MessageWithReferences(
                **base,
                chunk_references=chunk_refs_map.get(msg.id, []),
            )
        )

    return ConversationWithMessages(
        **ConversationDetail.model_validate(conversation).model_dump(),
        messages=message_details,
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
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    selection_change = request.selected_video_ids is not None or request.add_video_ids is not None
    title_change = request.title is not None

    # Update title if provided
    if title_change:
        conversation.title = request.title

    if selection_change:
        # Validate selected_video_ids if provided
        if request.selected_video_ids is not None:
            _validate_videos(db, current_user, request.selected_video_ids)
        _set_sources_selection(
            db=db,
            conversation=conversation,
            selected_video_ids=request.selected_video_ids,
            add_video_ids=request.add_video_ids,
            current_user=current_user,
        )
    elif title_change:
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


@router.get("/{conversation_id}/sources", response_model=ConversationSourcesResponse)
async def list_conversation_sources(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all sources attached to a conversation with their selection state.
    """
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    records = (
        db.query(ConversationSource, Video)
        .join(Video, ConversationSource.video_id == Video.id)
        .filter(ConversationSource.conversation_id == conversation_id)
        .order_by(ConversationSource.added_at.asc())
        .all()
    )

    sources = [
        ConversationSourceSchema(
            conversation_id=conversation_id,
            video_id=source.video_id,
            is_selected=source.is_selected,
            added_at=source.added_at,
            added_via=source.added_via,
            title=video.title if video else None,
            status=video.status if video else None,
            duration_seconds=video.duration_seconds if video else None,
            thumbnail_url=video.thumbnail_url if video else None,
            youtube_id=video.youtube_id if video else None,
        )
        for source, video in records
    ]

    selected_count = len([src for src in sources if src.is_selected])

    return ConversationSourcesResponse(
        total=len(sources),
        selected=selected_count,
        sources=sources,
    )


@router.patch("/{conversation_id}/sources", response_model=ConversationSourcesResponse)
async def update_conversation_sources(
    conversation_id: uuid.UUID,
    request: ConversationSourcesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update selection state for conversation sources and optionally attach new videos.
    """
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    if request.selected_video_ids is None and request.add_video_ids is None:
        raise HTTPException(
            status_code=400,
            detail="Provide selected_video_ids or add_video_ids to update sources.",
        )

    if request.selected_video_ids is not None:
        _validate_videos(db, current_user, request.selected_video_ids)

    if request.add_video_ids:
        _validate_videos(db, current_user, request.add_video_ids)

    _set_sources_selection(
        db=db,
        conversation=conversation,
        selected_video_ids=request.selected_video_ids,
        add_video_ids=request.add_video_ids,
        current_user=current_user,
    )

    return await list_conversation_sources(conversation_id, db, current_user)  # type: ignore[arg-type]


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
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    selected_sources = db.query(ConversationSource).filter(
        ConversationSource.conversation_id == conversation_id,
        ConversationSource.is_selected == True,  # noqa: E712
    ).all()

    if not selected_sources:
        raise HTTPException(
            status_code=400,
            detail="No sources are selected for this conversation. Please select at least one video/transcript.",
        )

    selected_video_ids = [src.video_id for src in selected_sources]

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
        video_ids=selected_video_ids,
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
    system_prompt = textwrap.dedent(
        """
        You will always receive a user question and a `mode` value that indicates how to structure your response. Supported modes: summarize, deep_dive, compare_sources, timeline, extract_actions, quiz_me.
        You are **InsightGuide**, a precise, transcript-grounded AI assistant designed to help users deeply explore and extract intelligence from video content. Your role is not just to answer but to *illuminate*, *connect*, and *invite further inquiry* - all strictly within the boundaries of the provided transcript.

        **Core Principles**
         **Fidelity First**: Use *only* the provided transcript. Never hallucinate, assume, or supplement with external knowledge.
         **Cite Rigorously**: Always reference by source (e.g., `Source 3`) and speaker (e.g., `Dr. Lee (Source 2)`).
         **Clarity & Conciseness**: Aim for <=150 words. Expand only when explicitly asked for analysis.
         **User Agency**: Prioritize questions that empower deeper exploration - not just facts, but *understanding*.

        **Response Protocol**
        1. ? **Answer directly** - grounded, cited, speaker-identified.
        2. If info is absent: "This is not mentioned in the provided transcript."
        3. ? If the request is ambiguous, ask one focused clarifying question (e.g., "Were you referring to the budget discussion in Source 1, or the timeline in Source 4?").
        4. **Follow-up Catalysts**: Offer exactly 2 actionable, transcript-supported next steps framed as open invitations:
           > "Based on Source 2, would you like to...
           > - "...see all proposed metrics for success?"
           > - "...explore how risk mitigation was discussed?"

        **Formatting**
        - Use **bold** for key terms, `inline code` for sources/speaker IDs
        - Use bullet points, headers (`###`), and emojis only to signal structure or emphasis (e.g., ?? for caveats)
        - Never be decorative - every emoji must serve cognition or navigation.

        You are a thinking deep thinking partner - not a search engine.
        """
    ).strip()


    llm_messages = [LLMMessage(role="system", content=system_prompt)]

    # Add conversation history (excluding the message we just added)
    for msg in history_messages[:-1]:
        llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

    # Add current user message with context
    user_message_with_context = (
        f"Mode: {request.mode}\n"
        f"Context from video transcripts:\n\n{context}\n\n"
        f"---\n\nUser question: {request.message}"
    )
    llm_messages.append(LLMMessage(role="user", content=user_message_with_context))


    # 8. Generate LLM response (honor optional per-request model override)
    try:
        llm_response = llm_service.complete(
            llm_messages,
            model=request.model,
        )
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
        response_time_seconds=time.time() - start_time,
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
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
        timestamp_display = _format_timestamp_display(
            scored_chunk.start_timestamp, scored_chunk.end_timestamp
        )
        chunk_refs_response.append({
            "chunk_id": ref.chunk_id,
            "video_id": scored_chunk.video_id,
            "video_title": video.title if video else "Unknown",
            "start_timestamp": scored_chunk.start_timestamp,
            "end_timestamp": scored_chunk.end_timestamp,
            "text_snippet": scored_chunk.text[:200] + "..." if len(scored_chunk.text) > 200 else scored_chunk.text,
            "relevance_score": scored_chunk.score,
            "timestamp_display": timestamp_display,
            "rank": ref.rank,
        })

    return MessageResponse(
        message_id=assistant_message.id,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        chunk_references=chunk_refs_response,
        token_count=token_count,
        response_time_seconds=response_time,
        model=llm_response.model if hasattr(llm_response, "model") else None,
    )
