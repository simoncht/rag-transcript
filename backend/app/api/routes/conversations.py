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
from typing import Any, Optional, List, Dict, Set, Sequence
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models import (
    Conversation,
    Video,
    User,
    Collection,
    CollectionVideo,
    ConversationSource,
    Message as MessageModel,
)
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

router = APIRouter()

SYSTEM_ROLE = "system"


def _format_timestamp_display(start: float, end: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    start_h, start_rem = divmod(int(start), 3600)
    start_m, start_s = divmod(start_rem, 60)
    end_h, end_rem = divmod(int(end), 3600)
    end_m, end_s = divmod(end_rem, 60)

    if start_h or end_h:
        return f"{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}"
    return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"


def _format_list_preview(items: Sequence[str], *, limit: int = 3) -> str:
    if len(items) <= limit:
        return ", ".join(items)
    remaining = len(items) - limit
    return f"{', '.join(items[:limit])} (+{remaining} more)"


def _create_system_message(
    *,
    conversation_id: uuid.UUID,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> MessageModel:
    return MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=SYSTEM_ROLE,
        content=content,
        token_count=0,
        message_metadata=metadata or None,
        created_at=datetime.utcnow(),
    )


def _mode_label(mode_id: str) -> str:
    return mode_id.replace("_", " ").title()


def _validate_videos(
    db: Session, current_user: User, video_ids: List[uuid.UUID]
) -> List[Video]:
    """Validate that videos exist, belong to the user, are not deleted, and are completed."""
    if not video_ids:
        raise HTTPException(
            status_code=400,
            detail="Must specify at least one video.",
        )

    unique_ids = list(dict.fromkeys(video_ids))
    videos_owned = (
        db.query(Video)
        .filter(Video.id.in_(unique_ids), Video.user_id == current_user.id)
        .all()
    )
    owned_by_id = {v.id: v for v in videos_owned}

    invalid_reasons: List[str] = []
    for vid in unique_ids:
        video = owned_by_id.get(vid)
        if not video:
            invalid_reasons.append(f"{vid} not found")
            continue
        if video.is_deleted:
            invalid_reasons.append(f"{video.title} ({vid}) is deleted")
            continue
        normalized_status = (video.status or "").strip().lower()
        if normalized_status != "completed":
            invalid_reasons.append(f"{video.title} ({vid}) status={video.status!r}")

    if invalid_reasons:
        preview = "; ".join(invalid_reasons[:3])
        suffix = (
            f" (+{len(invalid_reasons) - 3} more)" if len(invalid_reasons) > 3 else ""
        )
        raise HTTPException(
            status_code=400,
            detail=f"One or more videos not found or not completed processing: {preview}{suffix}",
        )

    videos = [owned_by_id[vid] for vid in unique_ids]

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
        for cv in (
            db.query(CollectionVideo.video_id)
            .join(Video, Video.id == CollectionVideo.video_id)
            .filter(
                CollectionVideo.collection_id == conversation.collection_id,
                Video.user_id == current_user.id,
                Video.is_deleted == False,  # noqa: E712
                func.lower(func.trim(Video.status)) == "completed",
            )
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
        .filter(
            Conversation.id == conversation_id, Conversation.user_id == current_user.id
        )
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
    current_user: User = Depends(get_current_user),
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
            detail="Cannot specify both collection_id and selected_video_ids. Choose one.",
        )

    if not request.collection_id and not request.selected_video_ids:
        raise HTTPException(
            status_code=400,
            detail="Must specify either collection_id or selected_video_ids",
        )

    video_ids = []
    auto_sync_collection = (
        request.auto_sync_collection
        if request.auto_sync_collection is not None
        else True
    )

    if request.collection_id:
        # Get all videos from collection
        collection = (
            db.query(Collection)
            .filter(
                Collection.id == request.collection_id,
                Collection.user_id == current_user.id,
            )
            .first()
        )

        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Get video IDs from collection (only include user's completed, non-deleted videos)
        collection_videos = (
            db.query(CollectionVideo.video_id)
            .join(Video, Video.id == CollectionVideo.video_id)
            .filter(
                CollectionVideo.collection_id == request.collection_id,
                Video.user_id == current_user.id,
                Video.is_deleted == False,  # noqa: E712
                func.lower(func.trim(Video.status)) == "completed",
            )
            .all()
        )
        video_ids = [str(cv[0]) for cv in collection_videos]

        if not video_ids:
            raise HTTPException(
                status_code=400, detail="Collection has no completed videos"
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
    current_user: User = Depends(get_current_user),
):
    """
    List user's conversations with pagination.

    Args:
        skip: Number of records to skip
        limit: Number of records to return

    Returns:
        ConversationList with conversations and total count
    """
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)

    total = query.count()

    conversations = (
        query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()
    )

    # Sync any collection-backed conversations to include new videos
    for conv in conversations:
        _sync_collection_sources(db, conv, current_user)

    return ConversationList(
        total=total,
        conversations=[ConversationDetail.model_validate(c) for c in conversations],
    )


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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

    selection_change = (
        request.selected_video_ids is not None or request.add_video_ids is not None
    )
    title_change = request.title is not None

    # Update title if provided
    if title_change:
        conversation.title = request.title

    if selection_change:
        # Validate selected_video_ids if provided
        if (
            request.selected_video_ids is not None
            and len(request.selected_video_ids) > 0
        ):
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
    current_user: User = Depends(get_current_user),
):
    """
    Delete a conversation.

    Args:
        conversation_id: Conversation UUID

    Returns:
        Success message
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id, Conversation.user_id == current_user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {
        "message": "Conversation deleted successfully",
        "conversation_id": str(conversation_id),
    }


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
            is_deleted=video.is_deleted if video else None,
            selectable=(
                False
                if not video
                else (
                    not video.is_deleted
                    and (video.status or "").strip().lower() == "completed"
                )
            ),
            selectable_reason=(
                "Video not found"
                if not video
                else (
                    "Video deleted"
                    if video.is_deleted
                    else (
                        None
                        if (video.status or "").strip().lower() == "completed"
                        else f"Not completed (status={video.status})"
                    )
                )
            ),
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

    before_selected_ids = {
        src.video_id
        for src in db.query(ConversationSource).filter(
            ConversationSource.conversation_id == conversation.id,
            ConversationSource.is_selected == True,  # noqa: E712
        )
    }

    if request.selected_video_ids is None and request.add_video_ids is None:
        raise HTTPException(
            status_code=400,
            detail="Provide selected_video_ids or add_video_ids to update sources.",
        )

    if request.selected_video_ids is not None and len(request.selected_video_ids) > 0:
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

    after_selected_ids = {
        src.video_id
        for src in db.query(ConversationSource).filter(
            ConversationSource.conversation_id == conversation.id,
            ConversationSource.is_selected == True,  # noqa: E712
        )
    }

    added_ids = sorted(after_selected_ids - before_selected_ids)
    removed_ids = sorted(before_selected_ids - after_selected_ids)

    if added_ids or removed_ids:
        changed_ids = list(dict.fromkeys([*added_ids, *removed_ids]))
        title_by_id = {
            video.id: video.title
            for video in db.query(Video).filter(
                Video.user_id == current_user.id,
                Video.id.in_(changed_ids),
            )
        }

        if added_ids:
            added_titles = [title_by_id.get(vid, str(vid)) for vid in added_ids]
            db.add(
                _create_system_message(
                    conversation_id=conversation.id,
                    content=f"FYI: Added to active sources: {_format_list_preview(added_titles)}",
                    metadata={
                        "event": "sources_added",
                        "video_ids": [str(v) for v in added_ids],
                    },
                )
            )

        if removed_ids:
            removed_titles = [title_by_id.get(vid, str(vid)) for vid in removed_ids]
            db.add(
                _create_system_message(
                    conversation_id=conversation.id,
                    content=f"FYI: Removed from active sources: {_format_list_preview(removed_titles)}",
                    metadata={
                        "event": "sources_removed",
                        "video_ids": [str(v) for v in removed_ids],
                    },
                )
            )

        db.commit()

    return await list_conversation_sources(conversation_id, db, current_user)  # type: ignore[arg-type]


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    from app.models import MessageChunkReference, Chunk, Video
    from app.core.config import settings

    start_time = time.time()

    # 1. Verify conversation exists and belongs to user
    conversation = _ensure_conversation_owned(db, conversation_id, current_user)
    _sync_collection_sources(db, conversation, current_user)

    selected_sources = (
        db.query(ConversationSource)
        .filter(
            ConversationSource.conversation_id == conversation_id,
            ConversationSource.is_selected == True,  # noqa: E712
        )
        .all()
    )

    if not selected_sources:
        raise HTTPException(
            status_code=400,
            detail="No sources are selected for this conversation. Please select at least one video/transcript.",
        )

    selected_video_ids = [src.video_id for src in selected_sources]

    previous_user_message = (
        db.query(MessageModel)
        .filter(
            MessageModel.conversation_id == conversation_id,
            MessageModel.role == "user",
        )
        .order_by(MessageModel.created_at.desc())
        .first()
    )
    previous_mode = None
    previous_model = None
    if previous_user_message and isinstance(
        previous_user_message.message_metadata, dict
    ):
        previous_mode = previous_user_message.message_metadata.get("mode")
        previous_model = previous_user_message.message_metadata.get("model")

    if previous_mode is not None and previous_mode != request.mode:
        db.add(
            _create_system_message(
                conversation_id=conversation_id,
                content=f"FYI: Mode changed to {_mode_label(request.mode)}",
                metadata={
                    "event": "mode_changed",
                    "previous": previous_mode,
                    "next": request.mode,
                },
            )
        )

    if previous_model is not None and previous_model != request.model:
        next_model = request.model or "default"
        db.add(
            _create_system_message(
                conversation_id=conversation_id,
                content=f"FYI: Model changed to {next_model}",
                metadata={
                    "event": "model_changed",
                    "previous": previous_model,
                    "next": request.model,
                },
            )
        )

    # 2. Save user message
    user_message = MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=request.message,
        token_count=len(request.message.split()),  # Simple approximation
        message_metadata={
            "mode": request.mode,
            "model": request.model,
        },
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
        top_k=settings.retrieval_top_k,
    )

    # 4a. Re-rank chunks if enabled (Phase 2 improvement)
    import logging

    logger = logging.getLogger(__name__)

    if settings.enable_reranking and scored_chunks:
        from app.services.reranker import reranker_service

        logger.info(f"Re-ranking: enabled, processing {len(scored_chunks)} chunks")
        reranked_chunks = reranker_service.rerank_chunks(
            query=request.message, chunks=scored_chunks, top_k=settings.reranking_top_k
        )
        logger.info(f"Re-ranking: returned {len(reranked_chunks)} chunks")
        scored_chunks = reranked_chunks
    else:
        logger.info("Re-ranking: disabled or no chunks to rank")

    # 4b. Apply relevance threshold filtering (Phase 1 improvement)
    high_quality_chunks = [
        c for c in scored_chunks if c.score >= settings.min_relevance_score
    ]

    # Log filtering statistics
    logger.info(
        f"Retrieval: {len(scored_chunks)} total chunks, {len(high_quality_chunks)} above threshold ({settings.min_relevance_score})"
    )

    # 4c. Check if we have sufficient context
    if not high_quality_chunks:
        # Fallback: use lower threshold if no high-quality chunks
        high_quality_chunks = [
            c for c in scored_chunks if c.score >= settings.fallback_relevance_score
        ]
        logger.warning(
            f"No chunks above {settings.min_relevance_score}, using fallback threshold {settings.fallback_relevance_score}: {len(high_quality_chunks)} chunks"
        )

    # Determine context quality for warning
    max_score = (
        max([c.score for c in high_quality_chunks]) if high_quality_chunks else 0.0
    )
    context_is_weak = max_score < settings.weak_context_threshold

    # 5. Build enhanced context from retrieved chunks (Phase 1 improvement)
    context_parts = []
    top_chunks = high_quality_chunks[:5]
    video_map: Dict[uuid.UUID, Video] = {}
    if top_chunks:
        unique_video_ids = list({c.video_id for c in top_chunks})
        if unique_video_ids:
            video_rows = db.query(Video).filter(Video.id.in_(unique_video_ids)).all()
            video_map = {v.id: v for v in video_rows}

    if not high_quality_chunks:
        # No relevant context found - explicit warning
        context = "WARNING: No relevant content found in the selected transcripts for this query."
        logger.warning("No chunks found for query, even with fallback threshold")
    else:
        # Build enhanced context with metadata
        for i, chunk in enumerate(top_chunks, 1):  # Use top 5 for context
            # Get video for title
            video = video_map.get(chunk.video_id)
            video_title = video.title if video else "Unknown Video"

            # Format timestamps as HH:MM:SS or MM:SS
            timestamp_display = _format_timestamp_display(
                chunk.start_timestamp, chunk.end_timestamp
            )

            # Extract speaker and topic information
            speaker = chunk.speakers[0] if chunk.speakers else "Unknown"
            topic = chunk.chapter_title or chunk.title or "General"

            # Build enhanced context entry
            context_parts.append(
                f'[Source {i}] from "{video_title}"\n'
                f"Speaker: {speaker}\n"
                f"Topic: {topic}\n"
                f"Time: {timestamp_display}\n"
                f"Relevance: {(chunk.score * 100):.0f}%\n"
                f"---\n"
                f"{chunk.text}\n"
            )

        context = "\n---\n".join(context_parts)

        # Add warning prefix if context quality is weak
        if context_is_weak:
            context = (
                f"NOTE: Retrieved context has low relevance (max {(max_score * 100):.0f}%). "
                f"The response may be speculative.\n\n{context}"
            )

    # 6. Get conversation history (last 10 messages) - Phase 1 improvement
    history_messages = (
        db.query(MessageModel)
        .filter(
            MessageModel.conversation_id == conversation_id,
            MessageModel.role != SYSTEM_ROLE,
        )
        .order_by(MessageModel.created_at.desc())
        .limit(10)
        .all()
    )
    history_messages.reverse()  # Oldest first

    # NEW: Phase 2 - Load conversation facts (only for conversations with 15+ messages)
    facts_section = ""
    if conversation.message_count >= 15:
        from app.models.conversation_fact import ConversationFact
        conversation_facts = (
            db.query(ConversationFact)
            .filter(ConversationFact.conversation_id == conversation_id)
            .order_by(ConversationFact.confidence_score.desc())
            .limit(10)  # Top 10 facts only
            .all()
        )

        # Build compressed facts section
        if conversation_facts:
            # Compressed format: key=value(T1), key2=value2(T2)
            facts_items = [
                f"{fact.fact_key}={fact.fact_value}(T{fact.source_turn})"
                for fact in conversation_facts
            ]
            facts_section = f"\n\n**Known Facts**: {', '.join(facts_items)}"

    # 7. Build LLM messages (streamlined prompt - Phase 2)
    system_prompt = (
        textwrap.dedent(
            """
        You are InsightGuide, an AI assistant that answers questions using ONLY information from provided video transcripts.{facts}

        **Core Rules**:
        1. Use ONLY the provided source transcripts - never add external knowledge
        2. Always cite sources by number and speaker (e.g., "According to Source 2, Dr. Smith states...")
        3. If information is not in the transcripts, say: "This is not mentioned in the provided transcripts"
        4. Be concise but thorough - aim for clear, direct answers
        5. Include speaker names and video titles when citing

        **Response Format**:
        - Answer the question directly with citations
        - If ambiguous, ask ONE clarifying question
        - Suggest up to 2 related follow-up questions that are explicitly answerable from the provided transcripts
          - Each follow-up must be grounded in a specific cited point from the transcripts
          - Append the supporting citations to each follow-up question (e.g., "(Source 1)")
          - Do NOT suggest follow-ups whose best answer would be: "This is not mentioned in the provided transcripts"
          - If you cannot find 2 that meet these rules, suggest fewer (or none)

        **Mode Handling** (mode={mode}):
        - summarize: Brief overview with key points
        - deep_dive: Detailed analysis with all relevant details
        - compare_sources: Compare information across different sources
        - timeline: Present information chronologically
        - extract_actions: List action items or recommendations
        - quiz_me: Ask the user questions to test understanding

        Be helpful, accurate, and honest about the limits of the provided information.
        """
        )
        .strip()
        .format(mode=request.mode, facts=facts_section)
    )

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
        token_count = (
            llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # 9. Save assistant message
    assistant_message = MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_count=token_count,
        chunks_retrieved_count=len(high_quality_chunks),  # Track filtered chunks
        response_time_seconds=time.time() - start_time,
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
    )
    db.add(assistant_message)

    # 10. Save chunk references (use filtered high-quality chunks)
    chunk_references = []
    resolved_entries = []

    chunk_ids = [c.chunk_id for c in top_chunks if c.chunk_id]
    chunk_indices = [
        (c.video_id, c.chunk_index)
        for c in top_chunks
        if c.chunk_id is None and c.chunk_index is not None
    ]

    chunk_by_id = {}
    if chunk_ids:
        for chunk in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all():
            chunk_by_id[chunk.id] = chunk

    chunk_by_video_index = {}
    if chunk_indices:
        video_ids_for_index = list({vid for vid, _ in chunk_indices})
        index_set = {(vid, idx) for vid, idx in chunk_indices}
        candidate_chunks = (
            db.query(Chunk)
            .filter(Chunk.video_id.in_(video_ids_for_index))
            .filter(Chunk.chunk_index.in_({idx for _, idx in chunk_indices}))
            .all()
        )
        for chunk in candidate_chunks:
            key = (chunk.video_id, chunk.chunk_index)
            if key in index_set:
                chunk_by_video_index[key] = chunk

    for rank, scored_chunk in enumerate(top_chunks, 1):  # Save top 5 references
        chunk_db = None
        if scored_chunk.chunk_id and scored_chunk.chunk_id in chunk_by_id:
            chunk_db = chunk_by_id[scored_chunk.chunk_id]
        elif scored_chunk.chunk_index is not None:
            chunk_db = chunk_by_video_index.get(
                (scored_chunk.video_id, scored_chunk.chunk_index)
            )

        if not chunk_db:
            continue

        ref = MessageChunkReference(
            id=uuid.uuid4(),
            message_id=assistant_message.id,
            chunk_id=chunk_db.id,
            relevance_score=scored_chunk.score,
            rank=rank,
        )
        db.add(ref)
        chunk_references.append(ref)
        resolved_entries.append((rank, scored_chunk, chunk_db))

    # 11. Update conversation metadata
    conversation.message_count = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .count()
    )
    conversation.total_tokens_used += token_count
    conversation.last_message_at = assistant_message.created_at

    db.commit()
    db.refresh(assistant_message)

    # NEW: Phase 2 - Extract facts from conversation turn
    try:
        from app.services.fact_extraction import fact_extraction_service

        extracted_facts = fact_extraction_service.extract_facts(
            db=db,
            message=assistant_message,
            conversation=conversation,
            user_query=request.message
        )

        # Save facts to database
        for fact in extracted_facts:
            db.add(fact)

        if extracted_facts:
            db.commit()
            logger.info(f"Saved {len(extracted_facts)} facts for conversation {conversation_id}")

    except Exception as e:
        logger.warning(f"Fact extraction failed: {e}")
        # Continue without facts (graceful degradation)

    # 12. Build response with chunk references
    response_time = time.time() - start_time

    chunk_refs_response = []
    for rank, scored_chunk, chunk_db in resolved_entries:
        video = video_map.get(scored_chunk.video_id)

        timestamp_display = _format_timestamp_display(
            scored_chunk.start_timestamp, scored_chunk.end_timestamp
        )
        chunk_refs_response.append(
            {
                "chunk_id": chunk_db.id,
                "video_id": scored_chunk.video_id,
                "video_title": video.title if video else "Unknown",
                "start_timestamp": scored_chunk.start_timestamp,
                "end_timestamp": scored_chunk.end_timestamp,
                "text_snippet": scored_chunk.text[:200] + "..."
                if len(scored_chunk.text) > 200
                else scored_chunk.text,
                "relevance_score": scored_chunk.score,
                "timestamp_display": timestamp_display,
                "rank": rank,
            }
        )

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
