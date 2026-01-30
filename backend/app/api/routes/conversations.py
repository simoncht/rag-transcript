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
from typing import Any, Optional, List, Dict, Set, Sequence, AsyncGenerator
from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.nextauth import get_current_user
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
from app.services.query_expansion import get_query_expansion_service
from app.services.query_rewriter import get_query_rewriter_service
from app.services.query_router import get_query_router_service, RetrievalStrategy
from app.services.intent_classifier import get_intent_classifier, QueryIntent
from app.services.two_level_retriever import get_two_level_retriever
from app.services.audit_logger import log_chat_message
from app.core.rate_limit import limiter
from app.core.pricing import resolve_model, get_model_info_for_tier

router = APIRouter()

SYSTEM_ROLE = "system"
MAX_CHUNK_REFERENCES = 4
CONTEXT_CHUNK_LIMIT = MAX_CHUNK_REFERENCES
SNIPPET_PREVIEW_MAX_CHARS = 240
REFERENCE_DEDUP_BUCKET_SECONDS = 30

# Diversity-aware retrieval constants
DEFAULT_DIVERSITY = 0.4
MAX_DIVERSITY = 0.7
DEFAULT_CHUNK_LIMIT = 4
MAX_CHUNK_LIMIT = 12
MMR_PREFETCH_LIMIT = 100


def _get_diversity_factor(num_videos: int, mode: str) -> float:
    """
    Calculate diversity factor based on video count and conversation mode.

    Higher diversity for:
    - More videos (need cross-video representation)
    - Synthesis modes (summarize, compare_sources)

    Args:
        num_videos: Number of videos selected for the conversation
        mode: Conversation mode (summarize, deep_dive, etc.)

    Returns:
        Diversity factor between 0.0 (relevance only) and 0.7 (max diversity)
    """
    # Base diversity by mode
    mode_diversity = {
        "summarize": 0.5,
        "compare_sources": 0.6,
        "deep_dive": 0.3,
        "timeline": 0.5,
        "extract_actions": 0.4,
        "quiz_me": 0.5,
    }
    base = mode_diversity.get(mode, DEFAULT_DIVERSITY)

    # Scale up for multi-video (add 0.05 per video beyond 3, cap at MAX_DIVERSITY)
    if num_videos > 3:
        base = min(base + (num_videos - 3) * 0.05, MAX_DIVERSITY)

    return base


def _get_chunk_limit(num_videos: int, mode: str) -> int:
    """
    Calculate chunk limit based on video count and conversation mode.

    More videos and synthesis modes get higher limits to ensure
    adequate representation across sources.

    Args:
        num_videos: Number of videos selected for the conversation
        mode: Conversation mode (summarize, deep_dive, etc.)

    Returns:
        Chunk limit between DEFAULT_CHUNK_LIMIT and MAX_CHUNK_LIMIT
    """
    # Base limits by mode
    base_limits = {
        "summarize": 6,
        "compare_sources": 8,
        "deep_dive": 4,
        "timeline": 6,
        "extract_actions": 5,
        "quiz_me": 6,
    }
    base = base_limits.get(mode, DEFAULT_CHUNK_LIMIT)

    # Scale up for multi-video (max MAX_CHUNK_LIMIT)
    if num_videos > 3:
        return min(base + (num_videos - 3), MAX_CHUNK_LIMIT)

    return base


def _build_context_from_summaries(
    db: Session,
    video_ids: List[uuid.UUID],
    max_videos: int = 50,
) -> tuple[str, List[Video], bool]:
    """
    Build context from video-level summaries for coverage queries.

    This implements the NotebookLM-style approach where high-level queries
    use pre-computed source summaries instead of chunk retrieval.

    Args:
        db: Database session
        video_ids: List of selected video IDs
        max_videos: Maximum number of video summaries to include

    Returns:
        Tuple of (context_string, videos_used, had_missing_summaries)
    """
    # Fetch videos with summaries
    videos = (
        db.query(Video)
        .filter(Video.id.in_(video_ids))
        .order_by(Video.created_at.desc())
        .limit(max_videos)
        .all()
    )

    context_parts = []
    videos_with_summaries = []
    missing_summaries = 0

    for i, video in enumerate(videos, 1):
        if video.summary:
            # Use video-level summary
            topics_str = ""
            if video.key_topics:
                topics_str = f"\nKey Topics: {', '.join(video.key_topics[:5])}"

            context_parts.append(
                f'[Source {i}] "{video.title}"\n'
                f"Channel: {video.channel_name or 'Unknown'}{topics_str}\n"
                f"---\n{video.summary}\n"
            )
            videos_with_summaries.append(video)
        else:
            missing_summaries += 1

    had_missing = missing_summaries > 0

    if not context_parts:
        return "No video summaries available.", [], True

    context = "\n---\n".join(context_parts)

    # Add note if some summaries were missing
    if had_missing:
        context = (
            f"NOTE: {missing_summaries} video(s) don't have summaries yet and are not included.\n\n"
            + context
        )

    return context, videos_with_summaries, had_missing


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


def _truncate_snippet(text: str, *, limit: int = SNIPPET_PREVIEW_MAX_CHARS) -> str:
    """Trim long snippets while keeping citations compact."""
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 3].rstrip()
    return f"{trimmed}..."


def _build_video_url(video: Video | None) -> str | None:
    """Prefer stored YouTube URL, otherwise derive from youtube_id."""
    if not video:
        return None
    if video.youtube_url:
        return video.youtube_url
    if video.youtube_id:
        return f"https://youtu.be/{video.youtube_id}"
    return None


def _build_youtube_jump_url(video: Video | None, start_seconds: float) -> str | None:
    """Create a timestamped YouTube link for jump actions."""
    base_url = _build_video_url(video)
    if not base_url:
        return None
    start_int = max(0, int(start_seconds))
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}t={start_int}"


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
                Video.is_deleted.is_(False),  # noqa: E712
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
                Video.is_deleted.is_(False),  # noqa: E712
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
                    youtube_id=video.youtube_id if video else None,
                    video_url=_build_video_url(video),
                    jump_url=_build_youtube_jump_url(video, chunk.start_timestamp),
                    start_timestamp=chunk.start_timestamp,
                    end_timestamp=chunk.end_timestamp,
                    text_snippet=_truncate_snippet(
                        chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS
                    ),
                    relevance_score=ref.relevance_score,
                    timestamp_display=_format_timestamp_display(
                        chunk.start_timestamp, chunk.end_timestamp
                    ),
                    rank=ref.rank,
                    # Phase 1 enhancement: contextual metadata
                    speakers=chunk.speakers if chunk.speakers else None,
                    chapter_title=chunk.chapter_title if chunk.chapter_title else None,
                    channel_name=video.channel_name if video and video.channel_name else None,
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
@limiter.limit("50/hour")
async def send_message(
    conversation_id: uuid.UUID,
    request: Request,
    message_request: MessageSendRequest,
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

    # Check message quota
    from app.core.quota import check_message_quota
    await check_message_quota(current_user, db)

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

    # Calculate adaptive diversity and chunk limit based on video count and mode
    num_videos = len(selected_video_ids)
    diversity_factor = _get_diversity_factor(num_videos, message_request.mode)
    adaptive_chunk_limit = _get_chunk_limit(num_videos, message_request.mode)

    # Check if videos have summaries for two-level retrieval
    videos_with_summaries = (
        db.query(Video)
        .filter(Video.id.in_(selected_video_ids), Video.summary.isnot(None))
        .count()
    )
    has_summaries = videos_with_summaries > 0
    summary_coverage = videos_with_summaries / num_videos if num_videos > 0 else 0

    # Load conversation history EARLY for intent classification
    history_messages_raw = (
        db.query(MessageModel)
        .filter(
            MessageModel.conversation_id == conversation_id,
            MessageModel.role != SYSTEM_ROLE,
        )
        .order_by(MessageModel.created_at.desc())
        .limit(10)
        .all()
    )
    history_messages_raw.reverse()  # Oldest first

    # Convert to dict format for intent classifier and query rewriter
    history_for_classifier = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages_raw
    ]

    # Classify query intent using LLM-based classifier
    intent_classifier = get_intent_classifier()
    intent_classification = intent_classifier.classify_sync(
        query=message_request.message,
        mode=message_request.mode,
        num_videos=num_videos,
        recent_messages=history_for_classifier[:-1] if history_for_classifier else None,
    )

    # Route query using legacy router for backward compatibility (fallback stats)
    query_router = get_query_router_service()
    routing_decision = query_router.route_query(
        query=message_request.message,
        num_videos=num_videos,
        mode=message_request.mode,
        videos_have_summaries=has_summaries and summary_coverage > 0.5,
    )

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

    if previous_mode is not None and previous_mode != message_request.mode:
        db.add(
            _create_system_message(
                conversation_id=conversation_id,
                content=f"FYI: Mode changed to {_mode_label(message_request.mode)}",
                metadata={
                    "event": "mode_changed",
                    "previous": previous_mode,
                    "next": message_request.mode,
                },
            )
        )

    if previous_model is not None and previous_model != message_request.model:
        next_model = message_request.model or "default"
        db.add(
            _create_system_message(
                conversation_id=conversation_id,
                content=f"FYI: Model changed to {next_model}",
                metadata={
                    "event": "model_changed",
                    "previous": previous_model,
                    "next": message_request.model,
                },
            )
        )

    # 2. Save user message
    user_message = MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=message_request.message,
        token_count=len(message_request.message.split()),  # Simple approximation
        message_metadata={
            "mode": message_request.mode,
            "model": message_request.model,
        },
    )
    db.add(user_message)
    log_chat_message(
        db,
        request=request,
        user_id=current_user.id,
        conversation_id=conversation_id,
        message=user_message,
        event_type="chat_message",
        extra_metadata={"path": str(request.url.path)},
    )
    db.commit()

    # 3. Configure logging and RAG pipeline
    import logging
    import time

    logger = logging.getLogger(__name__)

    logger.info(f"[RAG Pipeline] Starting retrieval for query: '{message_request.message[:100]}...'")
    logger.info(f"[RAG Config] retrieval_top_k={settings.retrieval_top_k}, reranking_enabled={settings.enable_reranking}, reranking_top_k={settings.reranking_top_k}")
    logger.info(f"[RAG Config] min_relevance_score={settings.min_relevance_score}, query_expansion_enabled={settings.enable_query_expansion}, query_rewriting_enabled={settings.enable_query_rewriting}")
    logger.info(f"[RAG Config] Diversity: num_videos={num_videos}, diversity_factor={diversity_factor:.2f}, chunk_limit={adaptive_chunk_limit}")
    logger.info(f"[Intent Classifier] Intent: {intent_classification.intent.value}, Confidence: {intent_classification.confidence:.2f}, Reason: {intent_classification.reasoning}")
    logger.info(f"[Query Router] Strategy: {routing_decision.strategy.value}, Reason: {routing_decision.reason}, Confidence: {routing_decision.confidence:.2f}")
    logger.info(f"[Query Router] Summary coverage: {videos_with_summaries}/{num_videos} videos ({summary_coverage:.0%})")

    # Initialize variables that may be set by either branch
    context = ""
    context_is_weak = False
    top_chunks = []
    video_map: Dict[uuid.UUID, Video] = {}
    chunk_refs_response = []
    rerank_time = 0.0

    # Determine query intent from the LLM-based classifier
    # COVERAGE: Use video summaries for "summarize all", "key themes" queries
    # PRECISION: Use chunk retrieval for "what did X say", "why" queries
    # HYBRID: Use both for "summarize with quotes" queries
    is_coverage_query = intent_classification.intent == QueryIntent.COVERAGE
    is_hybrid_query = intent_classification.intent == QueryIntent.HYBRID

    logger.info(f"[Intent] is_coverage={is_coverage_query}, is_hybrid={is_hybrid_query}")

    # Convert to dict format for query rewriter (history already loaded above)
    history_for_rewriter = history_for_classifier[:-1] if history_for_classifier else []

    # 3a. Query Rewriting: Transform follow-up queries into standalone questions
    query_rewriter_service = get_query_rewriter_service()
    rewrite_start = time.time()
    effective_query = query_rewriter_service.rewrite_query(
        query=message_request.message,
        conversation_history=history_for_rewriter,
    )
    rewrite_time = time.time() - rewrite_start

    if effective_query != message_request.message:
        logger.info(f"[Query Rewriter] Query rewritten in {rewrite_time:.3f}s")
        logger.info(f"[Query Rewriter] Original: '{message_request.message[:80]}...'")
        logger.info(f"[Query Rewriter] Rewritten: '{effective_query[:80]}...'")
    else:
        logger.debug(f"[Query Rewriter] No rewriting needed ({rewrite_time:.3f}s)")

    # 3b. Query Expansion and Chunk Retrieval (based on intent classification)
    expansion_time = 0.0
    embedding_time = 0.0
    query_variants = []
    scored_chunks = []
    high_quality_chunks = []
    deduped_chunks = []
    video_distribution = {}

    # Use chunk retrieval path based on intent:
    # - PRECISION: Always use chunks (let relevance determine sources)
    # - HYBRID: Use chunks for evidence
    # - COVERAGE: Use video summaries unless unavailable, then fall back to video-guarantee chunks
    use_chunk_retrieval = (
        intent_classification.intent == QueryIntent.PRECISION or
        intent_classification.intent == QueryIntent.HYBRID or
        (intent_classification.intent == QueryIntent.COVERAGE and summary_coverage < 0.5)
    )

    if use_chunk_retrieval:
        # ========== CHUNK RETRIEVAL PATH ==========
        if is_coverage_query:
            path_reason = "coverage query with video guarantee (summaries unavailable)"
        elif is_hybrid_query:
            path_reason = "hybrid query (chunks for evidence)"
        else:
            path_reason = "precision query"
        logger.info(f"[Two-Level Retrieval] Using chunk retrieval for {path_reason}")

        query_expansion_service = get_query_expansion_service()
        expansion_start = time.time()
        query_variants = query_expansion_service.expand_query(effective_query)  # Use rewritten query
        expansion_time = time.time() - expansion_start

        logger.info(f"[Query Expansion] Generated {len(query_variants)} query variants in {expansion_time:.3f}s")
        for idx, variant in enumerate(query_variants):
            logger.debug(f"[Query Expansion] Variant {idx}: '{variant[:100]}...'")

        # 4. Multi-Query Retrieval: Embed and search with each query variant
        embedding_start = time.time()
        all_scored_chunks: Dict[uuid.UUID, Any] = {}  # chunk_id -> best ScoredChunk

        for idx, query_text in enumerate(query_variants):
            variant_embed_start = time.time()
            query_embedding = embedding_service.embed_text(query_text)
            if isinstance(query_embedding, tuple):
                query_embedding = np.array(query_embedding, dtype=np.float32)
            variant_embed_time = time.time() - variant_embed_start

        logger.debug(f"[Embedding] Query variant {idx} embedded in {variant_embed_time:.3f}s")

        # Search with appropriate strategy based on intent
        variant_search_start = time.time()

        if is_coverage_query and num_videos > 1:
            # Use video guarantee search for coverage queries with multiple videos
            # This ensures at least 1 chunk per video is included
            logger.info(f"[Video Guarantee] Using guaranteed video representation for {num_videos} videos")
            variant_chunks = vector_store_service.search_with_video_guarantee(
                query_embedding=query_embedding,
                video_ids=selected_video_ids,
                user_id=current_user.id,
                top_k=adaptive_chunk_limit,
                prefetch_limit=MMR_PREFETCH_LIMIT,
            )
            search_type = "video guarantee"
        else:
            # Standard diversity-aware search for precision and hybrid queries
            # Let relevance determine which videos are represented
            variant_chunks = vector_store_service.search_with_diversity(
                query_embedding=query_embedding,
                user_id=current_user.id,
                video_ids=selected_video_ids,
                top_k=settings.retrieval_top_k,
                diversity=diversity_factor,
                prefetch_limit=MMR_PREFETCH_LIMIT,
            )
            search_type = f"diversity={diversity_factor:.2f}"
        variant_search_time = time.time() - variant_search_start
        logger.info(f"[Vector Search] Query variant {idx} retrieved {len(variant_chunks)} chunks ({search_type}) in {variant_search_time:.3f}s")
        logger.debug(f"[Vector Search] Query variant {idx} score range: {variant_chunks[0].score:.4f} to {variant_chunks[-1].score:.4f}" if variant_chunks else "No chunks")

        # Merge results: Keep highest score for each chunk
        for chunk in variant_chunks:
            chunk_id = chunk.chunk_id
            if chunk_id is None:
                # Skip chunks without IDs (shouldn't happen in normal operation)
                logger.warning(f"[Vector Search] Found chunk without ID, skipping: video_id={chunk.video_id}, timestamp={chunk.start_timestamp}")
                continue

            if chunk_id not in all_scored_chunks or chunk.score > all_scored_chunks[chunk_id].score:
                all_scored_chunks[chunk_id] = chunk

        embedding_time = time.time() - embedding_start

        # Convert merged results back to list, sorted by score
        scored_chunks = sorted(all_scored_chunks.values(), key=lambda c: c.score, reverse=True)

        logger.info(f"[Multi-Query Retrieval] Total embedding + search time: {embedding_time:.3f}s")
        logger.info(f"[Multi-Query Retrieval] Merged results: {len(scored_chunks)} unique chunks from {len(query_variants)} queries")
        if scored_chunks:
            logger.info(f"[Multi-Query Retrieval] Score range: {scored_chunks[0].score:.4f} to {scored_chunks[-1].score:.4f}")

        # 4a. Re-rank chunks if enabled (Phase 2 improvement)
        if settings.enable_reranking and scored_chunks:
            from app.services.reranker import reranker_service

            rerank_start = time.time()
            logger.info(f"[Reranking] Starting reranking of {len(scored_chunks)} chunks (top_k={settings.reranking_top_k})")
            logger.debug(f"[Reranking] Pre-rerank score range: {scored_chunks[0].score:.4f} to {scored_chunks[-1].score:.4f}")

            reranked_chunks = reranker_service.rerank_chunks(
                query=message_request.message, chunks=scored_chunks, top_k=settings.reranking_top_k
            )
            rerank_time = time.time() - rerank_start

            logger.info(f"[Reranking] Completed in {rerank_time:.3f}s, returned {len(reranked_chunks)} chunks")
            if reranked_chunks:
                logger.debug(f"[Reranking] Post-rerank score range: {reranked_chunks[0].score:.4f} to {reranked_chunks[-1].score:.4f}")
            scored_chunks = reranked_chunks
        else:
            logger.info("[Reranking] Disabled or no chunks to rank")

        # 4b. Apply relevance threshold filtering (Phase 1 improvement)
        # For coverage queries, skip strict filtering - video guarantee already selected best per video
        filter_start = time.time()
        if is_coverage_query:
            high_quality_chunks = scored_chunks
            logger.info(
                f"[Relevance Filter] Coverage query - skipping threshold filtering, keeping all {len(scored_chunks)} chunks"
            )
        else:
            high_quality_chunks = [
                c for c in scored_chunks if c.score >= settings.min_relevance_score
            ]
            filter_time = time.time() - filter_start

            logger.info(
                f"[Relevance Filter] Processed {len(scored_chunks)} chunks in {filter_time:.3f}s"
            )
            logger.info(
                f"[Relevance Filter] {len(high_quality_chunks)} chunks above primary threshold ({settings.min_relevance_score}), "
                f"{len(scored_chunks) - len(high_quality_chunks)} filtered out"
            )

            # 4c. Check if we have sufficient context
            if not high_quality_chunks:
                # Fallback: use lower threshold if no high-quality chunks
                high_quality_chunks = [
                    c for c in scored_chunks if c.score >= settings.fallback_relevance_score
                ]
                logger.warning(
                    f"[Relevance Filter] No chunks above primary threshold ({settings.min_relevance_score})"
                )
                logger.warning(
                    f"[Relevance Filter] Using fallback threshold ({settings.fallback_relevance_score}): {len(high_quality_chunks)} chunks"
                )
                if not high_quality_chunks:
                    logger.error("[Relevance Filter] No chunks even with fallback threshold - no context available")

        # Determine context quality for warning
        max_score = (
            max([c.score for c in high_quality_chunks]) if high_quality_chunks else 0.0
        )
        context_is_weak = max_score < settings.weak_context_threshold

        logger.info(
            f"[Context Quality] Max relevance score: {max_score:.4f}, "
            f"weak_threshold: {settings.weak_context_threshold}, "
            f"context_is_weak: {context_is_weak}"
        )

        # 4d. Deduplicate nearby chunks from the same video to avoid redundant citations
        # For coverage queries, dedupe by video_id only (keep 1 chunk per video)
        dedup_start = time.time()
        deduped_chunks = []
        seen_context_keys: Set = set()
        for chunk in high_quality_chunks:
            if is_coverage_query:
                # For coverage queries, dedupe by video_id only (keep 1 chunk per video)
                key = chunk.video_id
            else:
                bucket = int(chunk.start_timestamp // REFERENCE_DEDUP_BUCKET_SECONDS)
                key = (chunk.video_id, bucket)
            if key in seen_context_keys:
                continue
            seen_context_keys.add(key)
            deduped_chunks.append(chunk)
        dedup_time = time.time() - dedup_start

        logger.info(
            f"[Deduplication] Processed {len(high_quality_chunks)} chunks in {dedup_time:.3f}s"
        )
        logger.info(
            f"[Deduplication] Removed {len(high_quality_chunks) - len(deduped_chunks)} duplicate chunks, "
            f"{len(deduped_chunks)} remaining"
        )

        # 5. Build enhanced context from retrieved chunks (Phase 1 improvement)
        # Use adaptive chunk limit based on video count and mode
        context_build_start = time.time()
        context_parts = []
        top_chunks = deduped_chunks[:adaptive_chunk_limit]
        video_map: Dict[uuid.UUID, Video] = {}
        if top_chunks:
            unique_video_ids = list({c.video_id for c in top_chunks})
            if unique_video_ids:
                video_rows = db.query(Video).filter(Video.id.in_(unique_video_ids)).all()
                video_map = {v.id: v for v in video_rows}

        # Log video diversity in retrieved chunks
        video_distribution = {}
        for chunk in top_chunks:
            video_distribution[chunk.video_id] = video_distribution.get(chunk.video_id, 0) + 1
        logger.info(f"[Context Building] Using top {len(top_chunks)} chunks (adaptive limit: {adaptive_chunk_limit})")
        logger.info(f"[Context Building] Video diversity: {len(video_distribution)} unique videos from {num_videos} selected")

        if not high_quality_chunks:
            # No relevant context found - explicit warning
            context = "WARNING: No relevant content found in the selected transcripts for this query."
            context_is_weak = True
            max_score = 0.0
            logger.warning("[Context Building] No chunks found for query, even with fallback threshold")
        else:
            # Build enhanced context with metadata
            for i, chunk in enumerate(top_chunks, 1):
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

        context_build_time = time.time() - context_build_start
        context_token_estimate = len(context.split()) * 1.3  # Rough token estimate

        logger.info(f"[Context Building] Completed in {context_build_time:.3f}s")
        logger.info(f"[Context Building] Context length: {len(context)} chars, ~{int(context_token_estimate)} tokens")
        logger.info(f"[Context Building] Context quality: {'WEAK' if context_is_weak else 'GOOD'} (max score: {max_score:.4f})")

    else:
        # ========== VIDEO SUMMARIES PATH ==========
        # For coverage queries, use pre-computed video summaries
        logger.info(f"[Two-Level Retrieval] Using video summaries for coverage query (intent={intent_classification.intent.value})")

        context_build_start = time.time()
        context, videos_used, had_missing = _build_context_from_summaries(
            db=db,
            video_ids=selected_video_ids,
            max_videos=50,
        )
        context_build_time = time.time() - context_build_start

        # Log summary usage
        logger.info(f"[Video Summaries] Built context from {len(videos_used)} video summaries in {context_build_time:.3f}s")
        if had_missing:
            logger.warning(f"[Video Summaries] Some videos missing summaries, falling back to available summaries")

        # Set context quality indicators for summary path
        context_is_weak = len(videos_used) == 0
        max_score = 1.0 if videos_used else 0.0  # Summaries are always "relevant" when available
        context_token_estimate = len(context.split()) * 1.3

        # Update video distribution for logging
        video_distribution = {v.id: 1 for v in videos_used}

        logger.info(f"[Context Building] Context length: {len(context)} chars, ~{int(context_token_estimate)} tokens")
        logger.info(f"[Context Building] Videos with summaries: {len(videos_used)} / {num_videos} selected")

    # 6. Reuse conversation history loaded earlier (for query rewriting)
    # history_messages_raw was loaded before query expansion
    history_messages = history_messages_raw
    logger.debug(f"[Conversation History] Reusing {len(history_messages)} messages from earlier load")

    # NEW: Phase 2 - Load conversation facts with multi-factor scoring
    # (only for conversations with 15+ messages)
    facts_start = time.time()
    facts_section = ""
    selected_fact_ids = []  # Track for access reinforcement
    if conversation.message_count >= 15:
        from app.services.memory_scoring import (
            select_facts_multifactor,
            format_facts_for_prompt,
            update_fact_access,
        )
        from app.services.embeddings import EmbeddingService

        # Create embedding service for query-aware fact retrieval
        try:
            embedding_service = EmbeddingService()
        except Exception as e:
            logger.warning(f"[Conversation Facts] Failed to init embedding service: {e}")
            embedding_service = None

        # Use multi-factor scoring (importance + query_relevance + recency + category + source_turn)
        scored_facts = select_facts_multifactor(
            db=db,
            conversation_id=conversation_id,
            limit=15,  # Increased from 10 for better coverage
            user_query=message_request.message,
            embedding_service=embedding_service,  # Enable query-aware retrieval
        )

        # Build formatted facts section (grouped by category)
        if scored_facts:
            facts_section = format_facts_for_prompt(scored_facts)
            selected_fact_ids = [str(fact.id) for fact, _ in scored_facts]

            facts_time = time.time() - facts_start
            # Log scoring details
            top_scores = [(f.fact_key, f.category, score) for f, score in scored_facts[:3]]
            logger.info(
                f"[Conversation Facts] Selected {len(scored_facts)} facts in {facts_time:.3f}s "
                f"(top: {top_scores})"
            )
        else:
            logger.info("[Conversation Facts] No facts found for this conversation")
    else:
        logger.debug(f"[Conversation Facts] Skipped (message count {conversation.message_count} < 15)")

    # 7. Build LLM messages (streamlined prompt - Phase 2)
    system_prompt = (
        textwrap.dedent(
            """
        You are InsightGuide, an AI assistant that answers questions using ONLY information from provided video transcripts.{facts}

        **Core Rules**:
        1. Use ONLY the provided source transcripts - never add external knowledge
        2. If information is not in the transcripts, say: "This is not mentioned in the provided transcripts"
        3. Be concise but thorough - aim for clear, direct answers

        **Citation Rules** (IMPORTANT - follow exactly):
        - Write clean, readable prose - let the answer flow naturally
        - Place citation markers at the END of claims, not mid-sentence
        - Use simple format: [1], [2], [3] (just the number in brackets)
        - Multiple sources for one claim: [1][2] or [1, 2]
        - Do NOT write "According to Source 1" or "Source 2 states" - just add [N] after the claim

        **Good citation examples:**
        - "Bashar did not present physical evidence. [1]"
        - "The disclosure is metaphysical and behavioral. [1][2]"
        - "ET contact requires vibrational alignment. [1]"

        **Bad citation examples (AVOID):**
        - "According to Source 1, Bashar states..."
        - "Source 2 mentions that..."
        - "As stated in Source 1..."

        **Response Format**:
        - Answer the question directly with inline [N] citations at sentence ends
        - Keep citations at natural sentence boundaries
        - If ambiguous, ask ONE clarifying question
        - Suggest up to 2 related follow-up questions that are explicitly answerable from the provided transcripts
          - Each follow-up must be grounded in a specific cited point
          - Append the supporting citations to each follow-up question (e.g., "[1]")
          - If you cannot find 2 valid follow-ups, suggest fewer (or none)

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
        .format(mode=message_request.mode, facts=facts_section)
    )

    llm_messages = [LLMMessage(role="system", content=system_prompt)]

    # Add conversation history (excluding the message we just added)
    for msg in history_messages[:-1]:
        llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

    # Add current user message with context
    user_message_with_context = (
        f"Mode: {message_request.mode}\n"
        f"Context from video transcripts:\n\n{context}\n\n"
        f"---\n\nUser question: {message_request.message}"
    )
    llm_messages.append(LLMMessage(role="user", content=user_message_with_context))

    # Log prompt statistics
    total_prompt_tokens = sum(len(msg.content.split()) * 1.3 for msg in llm_messages)
    logger.info(f"[LLM Prompt] {len(llm_messages)} messages, ~{int(total_prompt_tokens)} tokens")
    logger.debug(f"[LLM Prompt] System prompt: {len(system_prompt)} chars")
    logger.debug(f"[LLM Prompt] User message with context: {len(user_message_with_context)} chars")

    # 8. Generate LLM response (use tier-based model with optional override)
    llm_start = time.time()

    # Resolve model based on user's subscription tier and optional request override
    user_tier = current_user.subscription_tier or "free"
    resolved_model = resolve_model(
        user_tier=user_tier,
        requested_model=message_request.model,
        allow_upgrade=current_user.is_superuser,  # Admins can use any model
    )
    tier_model_info = get_model_info_for_tier(user_tier)

    try:
        logger.info(
            f"[LLM Generation] User tier: {user_tier}, "
            f"Tier model: {tier_model_info.get('display_name', 'Unknown')}, "
            f"Resolved model: {resolved_model}"
        )

        llm_response = llm_service.complete(
            llm_messages,
            model=resolved_model,
        )
        assistant_content = llm_response.content
        prompt_tokens = (
            llm_response.usage.get("prompt_tokens") if llm_response.usage else None
        )
        completion_tokens = (
            llm_response.usage.get("completion_tokens") if llm_response.usage else None
        )
        token_count = (
            llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0
        )

        llm_time = time.time() - llm_start
        logger.info(f"[LLM Generation] Completed in {llm_time:.3f}s")
        logger.info(f"[LLM Generation] Response: {len(assistant_content)} chars, {token_count} tokens")
        logger.info(f"[LLM Generation] Provider: {llm_response.provider}, Model: {llm_response.model}")

        # Log DeepSeek cache performance if available
        if llm_response.usage:
            cache_hit = llm_response.usage.get("prompt_cache_hit_tokens", 0)
            cache_miss = llm_response.usage.get("prompt_cache_miss_tokens", 0)
            if cache_hit > 0 or cache_miss > 0:
                total_prompt = cache_hit + cache_miss
                hit_rate = cache_hit / total_prompt if total_prompt > 0 else 0
                logger.info(
                    f"[DeepSeek Cache] Hit: {cache_hit} tokens ({hit_rate:.1%}), "
                    f"Miss: {cache_miss} tokens"
                )

        # Log reasoning content if present (deepseek-reasoner)
        if llm_response.reasoning_content:
            logger.info(
                f"[DeepSeek Reasoner] Generated {len(llm_response.reasoning_content)} chars of chain-of-thought"
            )

    except Exception as e:
        llm_time = time.time() - llm_start
        logger.error(f"[LLM Generation] Failed after {llm_time:.3f}s: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # 8b. Update fact access reinforcement (facts used in this turn get stronger)
    if selected_fact_ids:
        try:
            from app.services.memory_scoring import update_fact_access
            update_fact_access(db, selected_fact_ids)
            logger.debug(f"[Memory Scoring] Reinforced {len(selected_fact_ids)} facts")
        except Exception as e:
            logger.warning(f"[Memory Scoring] Failed to update fact access: {e}")

    # 9. Save assistant message
    assistant_message = MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_count=token_count,
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        chunks_retrieved_count=len(high_quality_chunks),  # Track filtered chunks
        response_time_seconds=time.time() - start_time,
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
    )
    db.add(assistant_message)
    db.flush()  # Ensure message is in DB before referencing in LLM usage

    # 9a. Track LLM usage for cost monitoring
    if llm_response.usage:
        from app.models.llm_usage import LLMUsageEvent

        llm_usage = LLMUsageEvent.create_from_response(
            user_id=current_user.id,
            model=llm_response.model,
            provider=llm_response.provider,
            usage=llm_response.usage,
            conversation_id=conversation_id,
            message_id=assistant_message.id,
            response_time_seconds=llm_response.response_time_seconds,
        )
        db.add(llm_usage)
        logger.info(f"[Cost Tracking] Recorded usage: ${float(llm_usage.cost_usd):.6f}")

    # 10. Save chunk references (use filtered high-quality chunks)
    resolved_entries = []

    # Build lookup dictionaries for chunks
    chunk_by_id = {}
    chunk_by_video_index = {}

    # Collect all possible lookup keys
    chunk_ids = [c.chunk_id for c in top_chunks if c.chunk_id]
    video_index_pairs = [
        (c.video_id, c.chunk_index) for c in top_chunks if c.chunk_index is not None
    ]

    # Query chunks by ID
    if chunk_ids:
        for chunk in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all():
            chunk_by_id[chunk.id] = chunk

    # Query chunks by (video_id, chunk_index) - needed because Qdrant doesn't store chunk_db_id
    if video_index_pairs:
        video_ids_for_index = list({vid for vid, _ in video_index_pairs})
        chunk_indices_for_query = list({idx for _, idx in video_index_pairs})
        candidate_chunks = (
            db.query(Chunk)
            .filter(Chunk.video_id.in_(video_ids_for_index))
            .filter(Chunk.chunk_index.in_(chunk_indices_for_query))
            .all()
        )
        for chunk in candidate_chunks:
            key = (chunk.video_id, chunk.chunk_index)
            chunk_by_video_index[key] = chunk

    for rank, scored_chunk in enumerate(top_chunks, 1):  # Save top 5 references
        chunk_db = None

        # Try lookup by ID first
        if scored_chunk.chunk_id and scored_chunk.chunk_id in chunk_by_id:
            chunk_db = chunk_by_id[scored_chunk.chunk_id]

        # Always try fallback lookup by (video_id, chunk_index) if ID lookup failed
        if not chunk_db and scored_chunk.chunk_index is not None:
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
        resolved_entries.append((rank, scored_chunk, chunk_db))

    # Build user-facing chunk reference payload (capped to match adaptive context limit)
    chunk_refs_response = []
    for rank, scored_chunk, chunk_db in resolved_entries[:adaptive_chunk_limit]:
        video = video_map.get(scored_chunk.video_id)
        timestamp_display = _format_timestamp_display(
            scored_chunk.start_timestamp, scored_chunk.end_timestamp
        )
        snippet = _truncate_snippet(scored_chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS)
        chunk_refs_response.append(
            {
                "chunk_id": chunk_db.id,
                "video_id": scored_chunk.video_id,
                "video_title": video.title if video else "Unknown",
                "youtube_id": video.youtube_id if video else None,
                "video_url": _build_video_url(video),
                "jump_url": _build_youtube_jump_url(
                    video, scored_chunk.start_timestamp
                ),
                "start_timestamp": scored_chunk.start_timestamp,
                "end_timestamp": scored_chunk.end_timestamp,
                "text_snippet": snippet,
                "relevance_score": scored_chunk.score,
                "timestamp_display": timestamp_display,
                "rank": rank,
                # Phase 1 enhancement: contextual metadata
                "speakers": chunk_db.speakers if chunk_db.speakers else None,
                "chapter_title": chunk_db.chapter_title if chunk_db.chapter_title else None,
                "channel_name": video.channel_name if video and video.channel_name else None,
            }
        )

    # Update tracked source count to match what the user sees
    assistant_message.chunks_retrieved_count = len(chunk_refs_response)

    # 11. Update conversation metadata
    conversation.message_count = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .count()
    )
    conversation.total_tokens_used += token_count
    conversation.last_message_at = assistant_message.created_at

    log_chat_message(
        db,
        request=request,
        user_id=current_user.id,
        conversation_id=conversation_id,
        message=assistant_message,
        event_type="chat_message",
        extra_metadata={
            "provider": llm_response.provider,
            "model": llm_response.model,
            "response_time_seconds": assistant_message.response_time_seconds,
            "chunks_retrieved_count": assistant_message.chunks_retrieved_count,
        },
    )

    db.commit()
    db.refresh(assistant_message)

    # Track chat message for usage quota
    from app.services.usage_tracker import UsageTracker
    usage_tracker = UsageTracker(db)
    usage_tracker.track_chat_message(
        user_id=current_user.id,
        conversation_id=conversation_id,
        message_id=assistant_message.id,
        tokens_in=prompt_tokens or 0,
        tokens_out=completion_tokens or 0,
        chunks_retrieved=len(chunk_refs_response),
    )

    # NEW: Phase 2 - Extract facts from conversation turn
    try:
        from app.services.fact_extraction import fact_extraction_service

        extracted_facts = fact_extraction_service.extract_facts(
            db=db,
            message=assistant_message,
            conversation=conversation,
            user_query=message_request.message,
        )

        # Save facts to database
        for fact in extracted_facts:
            db.add(fact)

        if extracted_facts:
            db.commit()
            logger.info(
                f"Saved {len(extracted_facts)} facts for conversation {conversation_id}"
            )

    except Exception as e:
        logger.warning(f"Fact extraction failed: {e}")
        # Continue without facts (graceful degradation)

    # 12. Build response with chunk references
    response_time = time.time() - start_time

    # Final pipeline summary logging
    logger.info("=" * 80)
    logger.info("[RAG Pipeline Complete]")
    logger.info(f"  Total Time: {response_time:.3f}s")
    logger.info(f"  Intent: {intent_classification.intent.value} (confidence={intent_classification.confidence:.2f})")
    if effective_query != message_request.message:
        logger.info(f"  Query Rewriting: {rewrite_time:.3f}s (rewrote query)")
    logger.info(f"  Query Expansion: {expansion_time:.3f}s ({len(query_variants)} variants)")
    # Determine search mode based on intent
    if is_coverage_query and num_videos > 1:
        search_mode = "video_guarantee"
    elif not use_chunk_retrieval:
        search_mode = "video_summaries"
    else:
        search_mode = f"diversity={diversity_factor:.2f}"
    logger.info(f"  Embedding + Search: {embedding_time:.3f}s ({search_mode})")
    if settings.enable_reranking:
        logger.info(f"  Reranking: {rerank_time:.3f}s")
    logger.info(f"  Context Building: {context_build_time:.3f}s")
    logger.info(f"  LLM Generation: {llm_time:.3f}s")
    logger.info(f"  Retrieved Chunks: {len(scored_chunks)} → {len(high_quality_chunks)} filtered → {len(deduped_chunks)} deduped → {len(top_chunks)} used (limit={adaptive_chunk_limit})")
    logger.info(f"  Video Diversity: {len(video_distribution)} unique videos from {num_videos} selected")
    logger.info(f"  Response Tokens: {token_count}")
    logger.info(f"  Citations Returned: {len(chunk_refs_response)}")
    logger.info("=" * 80)

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


@router.post("/{conversation_id}/messages/stream")
@limiter.limit("50/hour")
async def send_message_stream(
    conversation_id: uuid.UUID,
    request: Request,
    message_request: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message in a conversation with streaming response.

    Returns Server-Sent Events (SSE) stream with:
    - Content chunks as they are generated
    - Final metadata (sources, token count) at the end

    SSE format:
    - data: {"type": "content", "content": "..."}
    - data: {"type": "done", "message_id": "...", "sources": [...], "token_count": N}
    - data: {"type": "error", "error": "..."}
    """
    import time
    import numpy as np
    import logging
    from app.services.embeddings import embedding_service
    from app.services.vector_store import vector_store_service
    from app.services.llm_providers import llm_service, Message as LLMMessage
    from app.models import MessageChunkReference, Chunk, Video
    from app.core.config import settings

    logger = logging.getLogger(__name__)
    start_time = time.time()

    # Check message quota
    from app.core.quota import check_message_quota
    await check_message_quota(current_user, db)

    # Verify conversation exists and belongs to user
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
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'error': 'No sources selected'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    selected_video_ids = [src.video_id for src in selected_sources]

    # Calculate adaptive diversity and chunk limit based on video count and mode
    num_videos = len(selected_video_ids)
    diversity_factor = _get_diversity_factor(num_videos, message_request.mode)
    adaptive_chunk_limit = _get_chunk_limit(num_videos, message_request.mode)

    logger.info(f"[Stream] Diversity config: num_videos={num_videos}, diversity={diversity_factor:.2f}, chunk_limit={adaptive_chunk_limit}")

    # Load history for intent classification
    history_messages_for_intent = (
        db.query(MessageModel)
        .filter(
            MessageModel.conversation_id == conversation_id,
            MessageModel.role != SYSTEM_ROLE,
        )
        .order_by(MessageModel.created_at.desc())
        .limit(10)
        .all()
    )
    history_messages_for_intent.reverse()

    history_for_classifier = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages_for_intent
    ]

    # Classify query intent using LLM-based classifier
    intent_classifier = get_intent_classifier()
    intent_classification = intent_classifier.classify_sync(
        query=message_request.message,
        mode=message_request.mode,
        num_videos=num_videos,
        recent_messages=history_for_classifier[:-1] if len(history_for_classifier) > 1 else None,
    )
    logger.info(f"[Stream] Intent: {intent_classification.intent.value} (confidence={intent_classification.confidence:.2f})")

    # Save user message
    user_message = MessageModel(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=message_request.message,
        token_count=len(message_request.message.split()),
        message_metadata={
            "mode": message_request.mode,
            "model": message_request.model,
            "stream": True,
        },
    )
    db.add(user_message)
    db.commit()

    # Reuse history already loaded for intent classification
    history_messages = history_messages_for_intent

    # Query rewriting: Transform follow-up queries into standalone questions
    query_rewriter_service = get_query_rewriter_service()
    history_for_rewriter = history_for_classifier[:-1] if history_for_classifier else []
    effective_query = query_rewriter_service.rewrite_query(
        query=message_request.message,
        conversation_history=history_for_rewriter,
    )

    if effective_query != message_request.message:
        logger.info(f"[Stream] Query rewritten: '{message_request.message[:50]}...' -> '{effective_query[:50]}...'")

    # Prepare context using rewritten query
    query_embedding = embedding_service.embed_text(effective_query)  # Use rewritten query
    if isinstance(query_embedding, tuple):
        query_embedding = np.array(query_embedding, dtype=np.float32)

    # Determine query intent from the LLM-based classifier
    is_coverage_query = intent_classification.intent == QueryIntent.COVERAGE
    is_hybrid_query = intent_classification.intent == QueryIntent.HYBRID

    if is_coverage_query and num_videos > 1:
        # Use video guarantee search for coverage queries with multiple videos
        logger.info(f"[Stream] Using video guarantee search for {num_videos} videos (coverage query)")
        scored_chunks = vector_store_service.search_with_video_guarantee(
            query_embedding=query_embedding,
            video_ids=selected_video_ids,
            user_id=current_user.id,
            top_k=adaptive_chunk_limit,
            prefetch_limit=MMR_PREFETCH_LIMIT,
        )
    else:
        # Standard diversity-aware search for precision/hybrid queries
        # Let relevance determine which videos are represented
        scored_chunks = vector_store_service.search_with_diversity(
            query_embedding=query_embedding,
            user_id=current_user.id,
            video_ids=selected_video_ids,
            top_k=settings.retrieval_top_k,
            diversity=diversity_factor,
            prefetch_limit=MMR_PREFETCH_LIMIT,
        )

    # Filter and dedupe chunks
    # For coverage queries, use lower threshold since we want representation from all videos
    if is_coverage_query:
        # Skip strict relevance filtering for coverage queries - the video guarantee
        # already selected the best chunk from each video
        high_quality_chunks = scored_chunks
    else:
        high_quality_chunks = [c for c in scored_chunks if c.score >= settings.min_relevance_score]
        if not high_quality_chunks:
            high_quality_chunks = [c for c in scored_chunks if c.score >= settings.fallback_relevance_score]

    # Dedupe (but for coverage queries, keep one per video not per time bucket)
    deduped_chunks = []
    seen_keys = set()
    for chunk in high_quality_chunks:
        if is_coverage_query:
            # For coverage queries, dedupe by video_id only (keep 1 chunk per video)
            key = chunk.video_id
        else:
            bucket = int(chunk.start_timestamp // REFERENCE_DEDUP_BUCKET_SECONDS)
            key = (chunk.video_id, bucket)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_chunks.append(chunk)

    # Use adaptive chunk limit based on video count and mode
    top_chunks = deduped_chunks[:adaptive_chunk_limit]

    # Build context
    video_map = {}
    if top_chunks:
        unique_video_ids = list({c.video_id for c in top_chunks})
        video_rows = db.query(Video).filter(Video.id.in_(unique_video_ids)).all()
        video_map = {v.id: v for v in video_rows}

    context_parts = []
    for i, chunk in enumerate(top_chunks, 1):
        video = video_map.get(chunk.video_id)
        video_title = video.title if video else "Unknown Video"
        timestamp_display = _format_timestamp_display(chunk.start_timestamp, chunk.end_timestamp)
        speaker = chunk.speakers[0] if chunk.speakers else "Unknown"
        topic = chunk.chapter_title or chunk.title or "General"
        context_parts.append(
            f'[Source {i}] from "{video_title}"\n'
            f"Speaker: {speaker}\nTopic: {topic}\nTime: {timestamp_display}\n"
            f"---\n{chunk.text}\n"
        )
    context = "\n---\n".join(context_parts) if context_parts else "No relevant context found."

    # history_messages already loaded above for query rewriting

    # Build LLM messages
    system_prompt = textwrap.dedent("""
        You are InsightGuide, an AI assistant that answers questions using ONLY information from provided video transcripts.

        **Core Rules**:
        1. Use ONLY the provided source transcripts - never add external knowledge
        2. If information is not in the transcripts, say: "This is not mentioned in the provided transcripts"
        3. Be concise but thorough - aim for clear, direct answers

        **Citation Rules**:
        - Use simple format: [1], [2], [3] at the end of claims
        - Do NOT write "According to Source 1" - just add [N] after the claim
    """).strip()

    llm_messages = [LLMMessage(role="system", content=system_prompt)]
    for msg in history_messages[:-1]:
        llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

    user_message_with_context = (
        f"Mode: {message_request.mode}\n"
        f"Context from video transcripts:\n\n{context}\n\n"
        f"---\n\nUser question: {message_request.message}"
    )
    llm_messages.append(LLMMessage(role="user", content=user_message_with_context))

    # Resolve model
    user_tier = current_user.subscription_tier or "free"
    resolved_model = resolve_model(
        user_tier=user_tier,
        requested_model=message_request.model,
        allow_upgrade=current_user.is_superuser,
    )

    # Stream generator
    async def generate_stream() -> AsyncGenerator[str, None]:
        full_content = []
        message_id = uuid.uuid4()

        try:
            # Stream LLM response
            for chunk in llm_service.stream_complete(
                llm_messages,
                model=resolved_model,
            ):
                full_content.append(chunk)
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

            # Save assistant message after streaming completes
            assistant_content = "".join(full_content)
            assistant_message = MessageModel(
                id=message_id,
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                token_count=len(assistant_content.split()),
                chunks_retrieved_count=len(top_chunks),
                response_time_seconds=time.time() - start_time,
                llm_provider="deepseek",
                llm_model=resolved_model,
            )
            db.add(assistant_message)

            # Save chunk references
            chunk_refs_response = []
            for rank, scored_chunk in enumerate(top_chunks, 1):
                video = video_map.get(scored_chunk.video_id)
                timestamp_display = _format_timestamp_display(
                    scored_chunk.start_timestamp, scored_chunk.end_timestamp
                )
                snippet = _truncate_snippet(scored_chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS)
                chunk_refs_response.append({
                    "chunk_id": str(scored_chunk.chunk_id) if scored_chunk.chunk_id else None,
                    "video_id": str(scored_chunk.video_id),
                    "video_title": video.title if video else "Unknown",
                    "youtube_id": video.youtube_id if video else None,
                    "jump_url": _build_youtube_jump_url(video, scored_chunk.start_timestamp),
                    "start_timestamp": scored_chunk.start_timestamp,
                    "end_timestamp": scored_chunk.end_timestamp,
                    "text_snippet": snippet,
                    "relevance_score": scored_chunk.score,
                    "timestamp_display": timestamp_display,
                    "rank": rank,
                })

            # Update conversation metadata
            conversation.message_count = (
                db.query(MessageModel)
                .filter(MessageModel.conversation_id == conversation_id)
                .count()
            )
            conversation.last_message_at = assistant_message.created_at

            db.commit()

            # Track chat message for usage quota
            from app.services.usage_tracker import UsageTracker
            usage_tracker = UsageTracker(db)
            usage_tracker.track_chat_message(
                user_id=current_user.id,
                conversation_id=conversation_id,
                message_id=message_id,
                tokens_in=len(user_message_with_context.split()),  # Approximate
                tokens_out=len(assistant_content.split()),  # Approximate
                chunks_retrieved=len(chunk_refs_response),
            )

            # Send final metadata
            yield f"data: {json.dumps({'type': 'done', 'message_id': str(message_id), 'sources': chunk_refs_response, 'token_count': len(assistant_content.split()), 'response_time_seconds': time.time() - start_time})}\n\n"

        except Exception as e:
            logger.error(f"[Streaming] Error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
