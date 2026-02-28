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
import logging
import re
import textwrap
import uuid
from typing import Any, Optional, List, Dict, Set, Sequence, AsyncGenerator
from datetime import datetime
import json

logger = logging.getLogger(__name__)
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
from app.api.utils import truncate_history_messages as _truncate_history_messages, format_timestamp_display as _format_timestamp_display
from app.services.intent_classifier import QueryIntent
from app.services.two_level_retriever import get_two_level_retriever, RetrievalConfig
from app.services.audit_logger import log_chat_message
from app.core.rate_limit import limiter
from app.core.pricing import resolve_model, get_model_info_for_tier

router = APIRouter()

SYSTEM_ROLE = "system"
MAX_CHUNK_REFERENCES = 4
CONTEXT_CHUNK_LIMIT = MAX_CHUNK_REFERENCES
SNIPPET_PREVIEW_MAX_CHARS = 240
REFERENCE_DEDUP_BUCKET_SECONDS = 30


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


def _get_best_chunk_for_videos(db: Session, video_ids: list, query: str = "") -> dict:
    """Get the best chunk per video for summary-level citations.

    Uses vector similarity to find the most relevant chunk per video when a query
    is provided. Falls back to the first DB chunk otherwise.

    Returns {video_id: object} where object has start_timestamp, end_timestamp,
    and optionally id, speakers, chapter_title, page_number, section_heading.
    """
    from app.models.chunk import Chunk
    if not video_ids:
        return {}

    if query:
        try:
            import numpy as np
            from app.services.embeddings import embedding_service
            from app.services.vector_store import vector_store_service
            raw_embedding = embedding_service.embed_text(query, is_query=True)
            query_embedding = np.array(raw_embedding) if isinstance(raw_embedding, tuple) else raw_embedding
            results = vector_store_service.vector_store.search(
                query_embedding, video_ids=video_ids, top_k=len(video_ids) * 3
            )
            # ScoredChunk objects have start_timestamp, end_timestamp, chunk_id, etc.
            best_per_video = {}
            for r in results:
                if r.video_id not in best_per_video:
                    best_per_video[r.video_id] = r
            if best_per_video:
                return best_per_video
        except Exception:
            pass  # Fall through to simple lookup

    # Fallback: first chunk per video from DB
    result = {}
    chunks = (
        db.query(Chunk)
        .filter(Chunk.video_id.in_(video_ids))
        .order_by(Chunk.video_id, Chunk.chunk_index)
        .all()
    )
    for chunk in chunks:
        if chunk.video_id not in result:
            result[chunk.video_id] = chunk
    return result


def _build_video_url(video: Optional[Video]) -> Optional[str]:
    """Prefer stored YouTube URL, otherwise derive from youtube_id."""
    if not video:
        return None
    if video.youtube_url:
        return video.youtube_url
    if video.youtube_id:
        return f"https://youtu.be/{video.youtube_id}"
    return None


def _build_youtube_jump_url(video: Optional[Video], start_seconds: float) -> Optional[str]:
    """Create a timestamped YouTube link for jump actions."""
    base_url = _build_video_url(video)
    if not base_url:
        return None
    start_int = max(0, int(start_seconds))
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}t={start_int}s"


def _build_source_url(video: Optional[Video]) -> Optional[str]:
    """Build URL for any content type."""
    if not video:
        return None
    if video.content_type == "youtube":
        return _build_video_url(video)
    # For documents, return a relative URL to the document viewer
    if video.source_url:
        return video.source_url
    return f"/documents/{video.id}"


def _build_jump_url(video: Optional[Video], scored_chunk) -> Optional[str]:
    """Build jump URL based on content type - timestamp for videos, page for documents."""
    if not video:
        return None
    if video.content_type == "youtube":
        return _build_youtube_jump_url(video, scored_chunk.start_timestamp)
    # For documents, jump to page
    page = getattr(scored_chunk, "page_number", None)
    if page is not None:
        return f"/documents/{video.id}?page={page}"
    return f"/documents/{video.id}"


def _format_location_display(scored_chunk) -> str:
    """Format location display based on content type."""
    content_type = getattr(scored_chunk, "content_type", "youtube")
    if content_type != "youtube":
        page = getattr(scored_chunk, "page_number", None)
        if page:
            end_page = getattr(scored_chunk, "end_page_number", None)
            if end_page and end_page != page:
                return f"Pages {page}-{end_page}"
            return f"Page {page}"
        return "Document"
    return _format_timestamp_display(scored_chunk.start_timestamp, scored_chunk.end_timestamp)


_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _extract_used_markers(response_text: str, num_sources: int) -> set[int]:
    """Extract valid [N] citation markers from LLM response (CIT-001).

    Returns set of 1-indexed source numbers that appear in the response and are
    within bounds. Used to set was_used_in_response on MessageChunkReference.
    """
    markers = {int(m) for m in _CITATION_MARKER_RE.findall(response_text)}
    return {m for m in markers if 1 <= m <= num_sources}


def _validate_citation_markers(response_text: str, num_sources: int) -> list[int]:
    """Check that [N] citation markers in LLM response don't exceed source count.

    Returns list of out-of-bounds marker numbers (empty = all valid).
    Logs a warning for any markers that reference non-existent sources.
    """
    markers = [int(m) for m in _CITATION_MARKER_RE.findall(response_text)]
    if not markers:
        return []

    out_of_bounds = sorted({m for m in markers if m < 1 or m > num_sources})
    if out_of_bounds:
        logger.warning(
            f"[Citation] Out-of-bounds markers {out_of_bounds} in response "
            f"(valid range: [1]-[{num_sources}]). "
            f"LLM hallucinated {len(out_of_bounds)} citation(s)."
        )
    return out_of_bounds


def _get_content_types_in_conversation(video_map: dict) -> set:
    """Get the set of content types present in a conversation's sources."""
    types = set()
    for video in video_map.values():
        if video:
            types.add(getattr(video, "content_type", "youtube"))
    return types


def _build_content_type_aware_system_prompt(mode: str, facts_section: str, content_types: set) -> str:
    """Build system prompt that adapts to the content types present."""
    has_videos = "youtube" in content_types
    has_documents = any(ct != "youtube" for ct in content_types)

    if has_videos and has_documents:
        source_desc = "provided sources (video transcripts and documents)"
        source_noun = "sources"
    elif has_documents:
        source_desc = "provided documents"
        source_noun = "documents"
    else:
        source_desc = "provided video transcripts"
        source_noun = "transcripts"

    return textwrap.dedent(
        f"""
    You are InsightGuide, an AI assistant that answers questions using ONLY information from {source_desc}.{{facts}}

    **Core Rules**:
    1. Use ONLY the provided source {source_noun} - never add external knowledge
    2. If information is not in the {source_noun}, say: "This is not mentioned in the provided {source_noun}"
    3. Be concise but thorough - prioritize accuracy over length

    **Citation Rules** (IMPORTANT - follow exactly):
    - Place citation markers at the END of claims, not mid-sentence
    - Use simple format: [1], [2], [3] (just the number in brackets)
    - Multiple sources for one claim: [1][2] or [1, 2]
    - Do NOT write "According to Source 1" - just add [N] after the claim

    **Mode Handling** (mode={mode}):
    - summarize: Brief overview with key points
    - deep_dive: Detailed analysis with all relevant details
    - compare_sources: Compare information across different sources
    - timeline: Present information chronologically
    - extract_actions: List actionable items or takeaways
    - quiz_me: Generate questions to test understanding
    """
    ).strip().format(mode=mode, facts=facts_section)


def _build_cross_source_section(intent: "QueryIntent", mode: str, num_videos: int) -> str:
    """Return cross-source synthesis guidance when applicable, empty string otherwise."""
    should_inject = (
        num_videos > 1
        and (
            intent in (QueryIntent.COVERAGE, QueryIntent.HYBRID)
            or mode == "compare_sources"
        )
    )
    if not should_inject:
        return ""
    return textwrap.dedent("""\
        **Cross-Source Analysis**:
        - Identify common themes, ideas, or arguments across multiple sources
        - Note contrasting perspectives or different approaches to similar topics
        - Highlight how sources complement or build upon each other
        - Synthesize connections you can infer from the content provided
        - Cite which sources support each connection you identify""")


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
            Collection.is_deleted.is_(False),
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
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted.is_(False),
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
                Collection.is_deleted.is_(False),
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
    video_id: Optional[uuid.UUID] = Query(None),
    collection_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user's conversations with pagination.

    Args:
        skip: Number of records to skip
        limit: Number of records to return
        video_id: Filter to direct conversations containing this video
        collection_id: Filter to conversations for this collection

    Returns:
        ConversationList with conversations and total count
    """
    if video_id and collection_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot filter by both video_id and collection_id simultaneously.",
        )
    # Subquery: count messages per conversation
    msg_count_subq = (
        db.query(
            MessageModel.conversation_id,
            func.count(MessageModel.id).label("msg_count"),
        )
        .group_by(MessageModel.conversation_id)
        .subquery()
    )

    # Subquery: aggregate selected video IDs per conversation
    video_ids_subq = (
        db.query(
            ConversationSource.conversation_id,
            func.array_agg(ConversationSource.video_id).label("selected_ids"),
        )
        .filter(ConversationSource.is_selected == True)  # noqa: E712
        .group_by(ConversationSource.conversation_id)
        .subquery()
    )

    # Subquery: last message preview (most recent non-system message, truncated to 120 chars)
    last_msg_subq = (
        db.query(
            MessageModel.conversation_id,
            func.left(MessageModel.content, 120).label("preview"),
        )
        .filter(MessageModel.role != "system")
        .distinct(MessageModel.conversation_id)
        .order_by(MessageModel.conversation_id, MessageModel.created_at.desc())
        .subquery()
    )

    # Main query with LEFT JOINs to subqueries
    query = (
        db.query(
            Conversation,
            func.coalesce(msg_count_subq.c.msg_count, 0).label("computed_msg_count"),
            video_ids_subq.c.selected_ids.label("computed_video_ids"),
            last_msg_subq.c.preview.label("last_msg_preview"),
        )
        .outerjoin(msg_count_subq, Conversation.id == msg_count_subq.c.conversation_id)
        .outerjoin(video_ids_subq, Conversation.id == video_ids_subq.c.conversation_id)
        .outerjoin(last_msg_subq, Conversation.id == last_msg_subq.c.conversation_id)
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.is_deleted.is_(False),
        )
    )

    # Apply source filters
    base_filters = [
        Conversation.user_id == current_user.id,
        Conversation.is_deleted.is_(False),
    ]
    if video_id:
        # Direct conversations only (not collection conversations containing this video)
        vid_subq = (
            db.query(ConversationSource.conversation_id)
            .filter(ConversationSource.video_id == video_id)
            .subquery()
        )
        query = query.filter(
            Conversation.collection_id.is_(None),
            Conversation.id.in_(vid_subq),
        )
        base_filters.extend([
            Conversation.collection_id.is_(None),
            Conversation.id.in_(vid_subq),
        ])
    elif collection_id:
        query = query.filter(Conversation.collection_id == collection_id)
        base_filters.append(Conversation.collection_id == collection_id)

    total = db.query(Conversation).filter(*base_filters).count()

    results = (
        query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()
    )

    # Build response with computed values
    conversations = []
    for conv, msg_count, video_ids, last_msg_preview in results:
        # Sync collection sources (adds new videos if any)
        _sync_collection_sources(db, conv, current_user)

        # Override cached values with computed values
        conv.message_count = msg_count
        conv.selected_video_ids = video_ids or []
        conv.last_message_preview = last_msg_preview

        conversations.append(ConversationDetail.model_validate(conv))

    return ConversationList(total=total, conversations=conversations)


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
            content_type = getattr(video, "content_type", "youtube") if video else "youtube"
            is_doc = content_type != "youtube"
            location = _format_location_display(chunk) if is_doc else _format_timestamp_display(
                chunk.start_timestamp, chunk.end_timestamp
            )
            chunk_refs_map[ref.message_id].append(
                ChunkReference(
                    chunk_id=chunk.id,
                    video_id=chunk.video_id,
                    video_title=video.title if video else "Unknown",
                    youtube_id=video.youtube_id if video else None,
                    video_url=_build_source_url(video),
                    jump_url=_build_jump_url(video, chunk),
                    start_timestamp=chunk.start_timestamp or 0,
                    end_timestamp=chunk.end_timestamp or 0,
                    text_snippet=_truncate_snippet(
                        chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS
                    ),
                    relevance_score=ref.relevance_score,
                    timestamp_display=location,
                    rank=ref.rank,
                    # Phase 1 enhancement: contextual metadata
                    speakers=chunk.speakers if chunk.speakers else None,
                    chapter_title=chunk.chapter_title if chunk.chapter_title else None,
                    channel_name=video.channel_name
                    if video and video.channel_name
                    else None,
                    # Document support
                    content_type=content_type,
                    page_number=getattr(chunk, "page_number", None),
                    section_heading=getattr(chunk, "section_heading", None),
                    location_display=location,
                )
            )

    # Pre-compute first-chunk lookup for summary_sources that need jump URL recomputation
    summary_video_ids: Set[uuid.UUID] = set()
    for msg in messages:
        if (
            msg.role == "assistant"
            and msg.id not in chunk_refs_map
            and isinstance(msg.message_metadata, dict)
            and "summary_sources" in msg.message_metadata
        ):
            for src in msg.message_metadata["summary_sources"]:
                vid = src.get("video_id")
                if vid:
                    try:
                        summary_video_ids.add(uuid.UUID(vid) if isinstance(vid, str) else vid)
                    except (ValueError, AttributeError):
                        pass
    # Find user query for each assistant message with summary_sources (for vector search)
    summary_query = ""
    for i, msg in enumerate(messages):
        if (
            msg.role == "assistant"
            and msg.id not in chunk_refs_map
            and isinstance(msg.message_metadata, dict)
            and "summary_sources" in msg.message_metadata
        ):
            # Use stored original_query or find preceding user message
            rm = msg.message_metadata.get("retrieval_metadata")
            if rm and rm.get("original_query"):
                summary_query = rm["original_query"]
            elif i > 0 and messages[i - 1].role == "user":
                summary_query = messages[i - 1].content[:200]
            break  # Use first match — usually all summary messages share the same conversation context
    first_chunks_for_summaries = _get_best_chunk_for_videos(db, list(summary_video_ids), query=summary_query) if summary_video_ids else {}
    # Also need video objects for URL building
    summary_video_objs: Dict[uuid.UUID, Video] = {}
    if summary_video_ids:
        for v in db.query(Video).filter(Video.id.in_(list(summary_video_ids))).all():
            summary_video_objs[v.id] = v

    # Convert to response models
    message_details: List[MessageWithReferences] = []
    for msg in messages:
        base = MessageSchema.model_validate(msg).model_dump()

        # Use DB-persisted chunk refs first; fall back to summary_sources
        # stored in message_metadata for summary-level retrieval results.
        refs = chunk_refs_map.get(msg.id, [])
        if (
            not refs
            and msg.role == "assistant"
            and isinstance(msg.message_metadata, dict)
            and "summary_sources" in msg.message_metadata
        ):
            for src in msg.message_metadata["summary_sources"]:
                try:
                    vid_str = src["video_id"]
                    vid_uuid = uuid.UUID(vid_str) if isinstance(vid_str, str) else vid_str
                    video = summary_video_objs.get(vid_uuid)
                    first_chunk = first_chunks_for_summaries.get(vid_uuid)
                    content_type = src.get("content_type", "youtube")
                    is_doc = content_type != "youtube"

                    # Recompute jump_url from first chunk instead of using stale stored value
                    if first_chunk and not is_doc:
                        jump_url = _build_youtube_jump_url(video, first_chunk.start_timestamp)
                        start_ts = first_chunk.start_timestamp
                        end_ts = first_chunk.end_timestamp
                        ts_display = _format_timestamp_display(start_ts, end_ts)
                    elif first_chunk and is_doc:
                        page = getattr(first_chunk, "page_number", None)
                        jump_url = f"/documents/{vid_str}?page={page or 1}"
                        start_ts = src.get("start_timestamp", 0)
                        end_ts = src.get("end_timestamp", 0)
                        ts_display = f"Page {page}" if page else src.get("timestamp_display", "")
                    else:
                        jump_url = src.get("jump_url")
                        start_ts = src.get("start_timestamp", 0)
                        end_ts = src.get("end_timestamp", 0)
                        ts_display = src.get("timestamp_display", "")

                    refs.append(
                        ChunkReference(
                            chunk_id=src.get("chunk_id"),
                            video_id=vid_str,
                            video_title=src.get("video_title", "Unknown"),
                            youtube_id=src.get("youtube_id"),
                            video_url=src.get("video_url"),
                            jump_url=jump_url,
                            start_timestamp=start_ts,
                            end_timestamp=end_ts,
                            text_snippet=src.get("text_snippet", ""),
                            relevance_score=src.get("relevance_score", 1.0),
                            timestamp_display=ts_display,
                            rank=src.get("rank", 0),
                            speakers=first_chunk.speakers if first_chunk and first_chunk.speakers else src.get("speakers"),
                            chapter_title=first_chunk.chapter_title if first_chunk and first_chunk.chapter_title else src.get("chapter_title"),
                            channel_name=src.get("channel_name"),
                            content_type=content_type,
                            page_number=src.get("page_number"),
                            section_heading=src.get("section_heading"),
                            location_display=ts_display,
                        )
                    )
                except Exception:
                    pass  # Skip malformed entries

        # Extract RAG intelligence metadata from message_metadata JSONB
        extra_fields = {}
        if msg.role == "assistant" and isinstance(msg.message_metadata, dict):
            mm = msg.message_metadata
            if "confidence" in mm:
                extra_fields["confidence"] = mm["confidence"]
            if "retrieval_metadata" in mm:
                extra_fields["retrieval_metadata"] = mm["retrieval_metadata"]
            if "reasoning_content" in mm:
                extra_fields["reasoning_content"] = mm["reasoning_content"]
            if "reasoning_tokens" in mm:
                extra_fields["reasoning_tokens"] = mm["reasoning_tokens"]

        # Remove keys from base that are overridden by extra_fields to avoid duplicates
        for key in extra_fields:
            base.pop(key, None)

        message_details.append(
            MessageWithReferences(
                **base,
                chunk_references=refs,
                **extra_fields,
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
    Delete a conversation (soft delete).

    Args:
        conversation_id: Conversation UUID

    Returns:
        Success message
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted.is_(False),
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Soft delete instead of hard delete
    conversation.is_deleted = True
    conversation.deleted_at = datetime.utcnow()
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
            content_type=getattr(video, "content_type", "youtube") if video else None,
            page_count=getattr(video, "page_count", None) if video else None,
            original_filename=getattr(video, "original_filename", None) if video else None,
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
    from app.services.llm_providers import llm_service, Message as LLMMessage
    from app.models import MessageChunkReference, Chunk
    from app.core.config import settings
    from app.services.usage_collector import LLMUsageCollector

    start_time = time.time()

    # Create usage collector for tracking all LLM costs in this request
    usage_collector = LLMUsageCollector(
        user_id=current_user.id, conversation_id=conversation_id
    )

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

    num_videos = len(selected_video_ids)

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
        {"role": msg.role, "content": msg.content} for msg in history_messages_raw
    ]

    # Classify query intent using LLM-based classifier
    from app.services.intent_classifier import IntentClassifier
    intent_classifier = IntentClassifier(usage_collector=usage_collector)
    intent_classification = intent_classifier.classify_sync(
        query=message_request.message,
        mode=message_request.mode,
        num_videos=num_videos,
        recent_messages=history_for_classifier[:-1] if history_for_classifier else None,
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

    # 3. Configure RAG pipeline
    import time

    logger.info(
        f"[RAG Pipeline] Starting retrieval for query: '{message_request.message[:100]}...'"
    )
    logger.info(
        f"[Intent Classifier] Intent: {intent_classification.intent.value}, "
        f"Confidence: {intent_classification.confidence:.2f}, "
        f"Reason: {intent_classification.reasoning}"
    )

    # 3a. Query Rewriting: Transform follow-up queries into standalone questions
    history_for_rewriter = history_for_classifier[:-1] if history_for_classifier else []
    from app.services.query_rewriter import QueryRewriterService
    query_rewriter_service = QueryRewriterService(usage_collector=usage_collector)
    rewrite_start = time.time()
    effective_query = query_rewriter_service.rewrite_query(
        query=message_request.message,
        conversation_history=history_for_rewriter,
    )
    rewrite_time = time.time() - rewrite_start

    if effective_query != message_request.message:
        logger.info(f"[Query Rewriter] Rewritten in {rewrite_time:.3f}s: '{effective_query[:80]}...'")

    # 3b. Two-Level Retrieval (replaces inline pipeline)
    # Gate expensive LLM-based features to Pro/Enterprise tiers
    is_paid = (current_user.subscription_tier or "free") in ("pro", "enterprise")
    retrieval_config = RetrievalConfig.from_settings()
    if not is_paid:
        retrieval_config.enable_query_expansion = False
        retrieval_config.enable_relevance_grading = False
        retrieval_config.enable_hyde = False
        logger.info("[Feature Gating] Free tier: disabled query expansion, relevance grading, HyDE")

    retriever = get_two_level_retriever()
    retrieval_start = time.time()
    retrieval_result = retriever.retrieve(
        db=db,
        query=effective_query,
        video_ids=selected_video_ids,
        user_id=current_user.id,
        mode=message_request.mode,
        intent=intent_classification,
        config=retrieval_config,
        usage_collector=usage_collector,
    )
    retrieval_time = time.time() - retrieval_start
    logger.info(
        f"[Two-Level Retrieval] type={retrieval_result.retrieval_type}, "
        f"chunks={len(retrieval_result.chunks)}, "
        f"summaries={len(retrieval_result.video_summaries)}, "
        f"time={retrieval_time:.3f}s"
    )

    context = retrieval_result.context
    context_is_weak = retrieval_result.context_is_weak
    top_chunks = retrieval_result.chunks
    video_map = retrieval_result.video_map

    # Build citation references for summary-only results
    chunk_refs_response = []
    if retrieval_result.retrieval_type == "summaries":
        summary_video_ids = [vs.video_id for vs in retrieval_result.video_summaries]
        first_chunks = _get_best_chunk_for_videos(db, summary_video_ids, query=effective_query)
        for idx, vs in enumerate(retrieval_result.video_summaries, 1):
            video = video_map.get(vs.video_id)
            is_doc = vs.content_type != "youtube"
            first_chunk = first_chunks.get(vs.video_id)
            if is_doc:
                page = getattr(first_chunk, "page_number", None) if first_chunk else None
                location = f"Page {page}" if page else ("Page 1" if vs.page_count else "Document")
                jump = f"/documents/{vs.video_id}?page={page or 1}"
            else:
                start_ts = first_chunk.start_timestamp if first_chunk else 0
                location = _format_timestamp_display(start_ts, first_chunk.end_timestamp if first_chunk else 0) if first_chunk else "Full video"
                jump = _build_youtube_jump_url(video, start_ts) if video else None
            chunk_refs_response.append({
                "chunk_id": str(getattr(first_chunk, 'chunk_id', None) or getattr(first_chunk, 'id', None)) if first_chunk else None,
                "video_id": str(vs.video_id),
                "video_title": vs.title,
                "youtube_id": video.youtube_id if video and not is_doc else None,
                "video_url": _build_source_url(video),
                "jump_url": jump,
                "start_timestamp": first_chunk.start_timestamp if first_chunk else 0,
                "end_timestamp": first_chunk.end_timestamp if first_chunk else (vs.duration_seconds or 0),
                "text_snippet": _truncate_snippet(vs.summary, limit=SNIPPET_PREVIEW_MAX_CHARS),
                "relevance_score": 1.0,
                "timestamp_display": location,
                "rank": idx,
                "speakers": first_chunk.speakers if first_chunk and first_chunk.speakers else None,
                "chapter_title": first_chunk.chapter_title if first_chunk and first_chunk.chapter_title else None,
                "channel_name": vs.channel_name if not is_doc else None,
                "content_type": vs.content_type,
                "page_number": getattr(first_chunk, "page_number", None) if first_chunk else (1 if is_doc else None),
                "section_heading": getattr(first_chunk, "section_heading", None) if first_chunk else None,
                "location_display": location,
            })

    # 6. Reuse conversation history loaded earlier (for query rewriting)
    # history_messages_raw was loaded before query expansion
    history_messages = history_messages_raw
    logger.debug(
        f"[Conversation History] Reusing {len(history_messages)} messages from earlier load"
    )

    # NEW: Phase 2 - Load conversation facts with multi-factor scoring
    # (only for conversations with 10+ messages — lowered from 15 to close MEM-001 dead zone)
    facts_start = time.time()
    facts_section = ""
    selected_fact_ids = []  # Track for access reinforcement
    if conversation.message_count >= 10:
        from app.services.memory_scoring import (
            select_facts_multifactor,
            format_facts_for_prompt,
            update_fact_access,
        )
        from app.services.embeddings import embedding_service as _emb_svc

        # Use multi-factor scoring (importance + query_relevance + recency + category + source_turn)
        scored_facts = select_facts_multifactor(
            db=db,
            conversation_id=conversation_id,
            limit=15,  # Increased from 10 for better coverage
            user_query=message_request.message,
            embedding_service=_emb_svc,  # Enable query-aware retrieval
        )

        # Build formatted facts section (grouped by category)
        if scored_facts:
            facts_section = format_facts_for_prompt(scored_facts)
            selected_fact_ids = [str(fact.id) for fact, _ in scored_facts]

            facts_time = time.time() - facts_start
            # Log scoring details
            top_scores = [
                (f.fact_key, f.category, score) for f, score in scored_facts[:3]
            ]
            logger.info(
                f"[Conversation Facts] Selected {len(scored_facts)} facts in {facts_time:.3f}s "
                f"(top: {top_scores})"
            )
        else:
            logger.info("[Conversation Facts] No facts found for this conversation")
    else:
        logger.debug(
            f"[Conversation Facts] Skipped (message count {conversation.message_count} < 10)"
        )

    # 7. Build LLM messages (streamlined prompt - Phase 2)
    # Determine content types present in conversation for adaptive prompting
    content_types = _get_content_types_in_conversation(video_map)
    has_documents = any(ct != "youtube" for ct in content_types)
    has_videos = "youtube" in content_types

    if has_videos and has_documents:
        source_noun = "sources"
    elif has_documents:
        source_noun = "documents"
    else:
        source_noun = "transcripts"

    system_prompt = (
        textwrap.dedent(
            """
        You are InsightGuide, an AI assistant that answers questions using ONLY information from provided {source_noun}.{{facts}}

        **Core Rules**:
        1. Use ONLY the provided source {source_noun} - never add external knowledge
        2. If information is not in the {source_noun}, say: "This is not mentioned in the provided {source_noun}"
        3. Be concise but thorough - aim for clear, direct answers

        **Citation Rules** (IMPORTANT - follow exactly):
        - Write clean, readable prose - let the answer flow naturally
        - Place citation markers at the END of claims, not mid-sentence
        - Use simple format: [1], [2], [3] (just the number in brackets)
        - Multiple sources for one claim: [1][2] or [1, 2]
        - Do NOT write "According to Source 1" or "Source 2 states" - just add [N] after the claim

        **Good citation examples:**
        - "The study found significant improvements. [1]"
        - "Both sources confirm this finding. [1][2]"
        - "The key recommendation is to proceed gradually. [1]"

        **Bad citation examples (AVOID):**
        - "According to Source 1, the study states..."
        - "Source 2 mentions that..."
        - "As stated in Source 1..."

        **Response Format**:
        - Answer the question directly with inline [N] citations at sentence ends
        - Keep citations at natural sentence boundaries
        - If ambiguous, ask ONE clarifying question
        - Suggest up to 2 related follow-up questions that are explicitly answerable from the provided {source_noun}
          - Each follow-up must be grounded in a specific cited point
          - Append the supporting citations to each follow-up question (e.g., "[1]")
          - If you cannot find 2 valid follow-ups, suggest fewer (or none)

        **Mode Handling** (mode={{mode}}):
        - summarize: Brief overview with key points
        - deep_dive: Detailed analysis with all relevant details
        - compare_sources: Compare information across different sources
        - timeline: Present information chronologically
        - extract_actions: List action items or recommendations
        - quiz_me: Ask the user questions to test understanding

        {{cross_source_section}}

        Be helpful, accurate, and honest about the limits of the provided information.
        """
        )
        .strip()
        .format(source_noun=source_noun)
        .format(
            mode=message_request.mode,
            facts=facts_section,
            cross_source_section=_build_cross_source_section(
                intent_classification.intent, message_request.mode, num_videos,
            ),
        )
    )

    llm_messages = [LLMMessage(role="system", content=system_prompt)]

    # Add conversation history (excluding the message we just added)
    # Truncate old assistant messages to reduce token usage
    truncated_history = _truncate_history_messages(
        history_messages[:-1],
        truncate_chars=settings.history_assistant_truncate_chars,
    )
    for role, content in truncated_history:
        llm_messages.append(LLMMessage(role=role, content=content))

    # Add current user message with context
    context_label = f"Context from {source_noun}"
    user_message_with_context = (
        f"Mode: {message_request.mode}\n"
        f"{context_label}:\n\n{context}\n\n"
        f"---\n\nUser question: {message_request.message}"
    )
    llm_messages.append(LLMMessage(role="user", content=user_message_with_context))

    # Log prompt statistics
    total_prompt_tokens = sum(len(msg.content.split()) * 1.3 for msg in llm_messages)
    logger.info(
        f"[LLM Prompt] {len(llm_messages)} messages, ~{int(total_prompt_tokens)} tokens"
    )
    logger.debug(f"[LLM Prompt] System prompt: {len(system_prompt)} chars")
    logger.debug(
        f"[LLM Prompt] User message with context: {len(user_message_with_context)} chars"
    )

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
        logger.info(
            f"[LLM Generation] Response: {len(assistant_content)} chars, {token_count} tokens"
        )
        logger.info(
            f"[LLM Generation] Provider: {llm_response.provider}, Model: {llm_response.model}"
        )

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

    # 8b. Validate citation markers (CIT-002) and extract used markers (CIT-001)
    _validate_citation_markers(assistant_content, len(top_chunks))
    used_markers = _extract_used_markers(assistant_content, len(top_chunks))

    # 8c. Update fact access reinforcement (facts used in this turn get stronger)
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
        chunks_retrieved_count=len(top_chunks),
        response_time_seconds=time.time() - start_time,
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
    )
    db.add(assistant_message)

    # Persist summary-level citations in message_metadata (since
    # MessageChunkReference requires a chunk_id FK and summaries
    # reference whole videos, not individual chunks).
    if retrieval_result.retrieval_type == "summaries" and chunk_refs_response:
        assistant_message.message_metadata = {
            "summary_sources": chunk_refs_response,
        }

    db.flush()  # Ensure message is in DB before referencing in LLM usage

    # 9a. Track LLM usage for cost monitoring
    if llm_response.usage:
        from app.models.llm_usage import LLMUsageEvent, CallType

        llm_usage = LLMUsageEvent.create_from_response(
            user_id=current_user.id,
            model=llm_response.model,
            provider=llm_response.provider,
            usage=llm_response.usage,
            conversation_id=conversation_id,
            message_id=assistant_message.id,
            response_time_seconds=llm_response.response_time_seconds,
            call_type=CallType.CHAT,
        )
        db.add(llm_usage)
        logger.info(f"[Cost Tracking] Recorded chat usage: ${float(llm_usage.cost_usd):.6f}")

    # 9b. Flush auxiliary LLM usage events (query expansion, rewriting, etc.)
    aux_count = usage_collector.flush(db)
    if aux_count > 0:
        logger.info(f"[Cost Tracking] Recorded {aux_count} auxiliary LLM usage events")

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
            was_used_in_response=(rank in used_markers),
        )
        db.add(ref)
        resolved_entries.append((rank, scored_chunk, chunk_db))

    # CIT-001: Set chunks_used_count based on actual citation markers
    assistant_message.chunks_used_count = len(used_markers)

    # Build user-facing chunk reference payload
    chunk_refs_response = []
    for rank, scored_chunk, chunk_db in resolved_entries:
        video = video_map.get(scored_chunk.video_id)
        location_display = _format_location_display(scored_chunk)
        snippet = _truncate_snippet(scored_chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS)
        content_type = getattr(video, "content_type", "youtube") if video else "youtube"
        is_doc = content_type != "youtube"
        chunk_ref = {
            "chunk_id": chunk_db.id,
            "video_id": scored_chunk.video_id,
            "video_title": video.title if video else "Unknown",
            "youtube_id": video.youtube_id if video and not is_doc else None,
            "video_url": _build_source_url(video),
            "jump_url": _build_jump_url(video, scored_chunk),
            "start_timestamp": scored_chunk.start_timestamp or 0,
            "end_timestamp": scored_chunk.end_timestamp or 0,
            "text_snippet": snippet,
            "relevance_score": scored_chunk.score,
            "timestamp_display": location_display,
            "rank": rank,
            # Contextual metadata
            "speakers": chunk_db.speakers if chunk_db.speakers else None,
            "chapter_title": chunk_db.chapter_title
            if chunk_db.chapter_title
            else None,
            "channel_name": video.channel_name
            if video and video.channel_name and not is_doc
            else None,
            # Content type and document fields
            "content_type": content_type,
            "page_number": getattr(scored_chunk, "page_number", None) or getattr(chunk_db, "page_number", None),
            "section_heading": getattr(scored_chunk, "section_heading", None) or getattr(chunk_db, "section_heading", None),
            "location_display": location_display,
        }
        chunk_refs_response.append(chunk_ref)

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
        from app.services.fact_extraction import FactExtractionService

        fact_service = FactExtractionService(usage_collector=usage_collector)
        extracted_facts = fact_service.extract_facts(
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

    # Flush any remaining usage events (e.g. from fact extraction)
    if len(usage_collector) > 0:
        try:
            remaining = usage_collector.flush(db)
            db.commit()
            if remaining:
                logger.info(f"[LLM Usage] Flushed {remaining} post-pipeline events")
        except Exception as e:
            logger.warning(f"[LLM Usage] Post-pipeline flush failed: {e}")

    # 12. Build response with chunk references
    response_time = time.time() - start_time

    # Final pipeline summary logging
    logger.info("=" * 80)
    logger.info("[RAG Pipeline Complete]")
    logger.info(f"  Total Time: {response_time:.3f}s")
    logger.info(
        f"  Intent: {intent_classification.intent.value} (confidence={intent_classification.confidence:.2f})"
    )
    logger.info(f"  Retrieval: type={retrieval_result.retrieval_type}, time={retrieval_time:.3f}s")
    logger.info(f"  Chunks Used: {len(top_chunks)}, Stats: {retrieval_result.retrieval_stats}")
    logger.info(f"  LLM Generation: {llm_time:.3f}s")
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
    - Status updates as pipeline progresses
    - Content chunks as they are generated
    - Final metadata (sources, token count) at the end

    SSE format:
    - data: {"type": "status", "stage": "...", "message": "..."}
    - data: {"type": "content", "content": "..."}
    - data: {"type": "done", "message_id": "...", "sources": [...], "token_count": N}
    - data: {"type": "error", "error": "..."}
    """
    import asyncio
    import time
    from app.services.llm_providers import llm_service, Message as LLMMessage
    from app.core.config import settings
    from app.services.usage_collector import LLMUsageCollector

    # Create usage collector for tracking all LLM costs in this request
    usage_collector = LLMUsageCollector(
        user_id=current_user.id, conversation_id=conversation_id
    )
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
    num_videos = len(selected_video_ids)

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

    # Classify query intent
    from app.services.intent_classifier import IntentClassifier
    intent_classifier = IntentClassifier(usage_collector=usage_collector)
    intent_classification = intent_classifier.classify_sync(
        query=message_request.message,
        mode=message_request.mode,
        num_videos=num_videos,
        recent_messages=history_for_classifier[:-1]
        if len(history_for_classifier) > 1
        else None,
    )
    logger.info(
        f"[Stream] Intent: {intent_classification.intent.value} "
        f"(confidence={intent_classification.confidence:.2f})"
    )

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

    # Eagerly extract history into plain tuples while db session is still alive.
    # The db session (from get_db) closes when the route handler returns, BEFORE
    # the StreamingResponse generator starts consuming. Any ORM objects accessed
    # after that point would raise DetachedInstanceError.
    history_messages = [
        (msg.role, msg.content) for msg in history_messages_for_intent
    ]

    # Count messages for fact loading (done before generator to use request db)
    actual_message_count = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .count()
    )

    # Resolve model early (no I/O needed)
    user_tier = current_user.subscription_tier or "free"
    resolved_model = resolve_model(
        user_tier=user_tier,
        requested_model=message_request.model,
        allow_upgrade=current_user.is_superuser,
    )

    # Gate expensive LLM-based features to Pro/Enterprise tiers
    is_paid = user_tier in ("pro", "enterprise")
    _retrieval_config = RetrievalConfig.from_settings()
    if not is_paid:
        _retrieval_config.enable_query_expansion = False
        _retrieval_config.enable_relevance_grading = False
        _retrieval_config.enable_hyde = False

    # Capture values needed by generator (avoid accessing request db inside threads)
    _conv_id = conversation_id
    _user_id = current_user.id
    _user_message_text = message_request.message
    _mode = message_request.mode
    _is_superuser = current_user.is_superuser
    _is_paid = is_paid
    _history_for_rewriter = history_for_classifier[:-1] if history_for_classifier else []

    # Stream generator — all heavy work happens inside, enabling immediate SSE response
    async def generate_stream() -> AsyncGenerator[str, None]:
        from app.db.base import SessionLocal

        full_content = []
        message_id = uuid.uuid4()
        pipeline_timing = {}

        try:
            # === Status: Analyzing ===
            yield f"data: {json.dumps({'type': 'status', 'stage': 'analyzing', 'message': 'Analyzing your question...'})}\n\n"

            # --- Query Rewriting (runs in thread with no DB needed) ---
            rewrite_start = time.time()

            def _do_rewrite():
                from app.services.query_rewriter import QueryRewriterService
                rewriter = QueryRewriterService(usage_collector=usage_collector)
                return rewriter.rewrite_query(
                    query=_user_message_text,
                    conversation_history=_history_for_rewriter,
                )

            effective_query = await asyncio.to_thread(_do_rewrite)
            pipeline_timing["rewrite_ms"] = round((time.time() - rewrite_start) * 1000)

            if effective_query != _user_message_text:
                logger.info(
                    f"[Stream] Query rewritten: '{_user_message_text[:50]}...' -> '{effective_query[:50]}...'"
                )

            # === Status: Searching ===
            yield f"data: {json.dumps({'type': 'status', 'stage': 'searching', 'message': 'Searching knowledge base...'})}\n\n"

            # --- Retrieval + Fact Loading (parallel, each with own DB session) ---
            retrieval_start = time.time()

            def _do_retrieval():
                thread_db = SessionLocal()
                try:
                    retriever = get_two_level_retriever()
                    return retriever.retrieve(
                        db=thread_db,
                        query=effective_query,
                        video_ids=selected_video_ids,
                        user_id=_user_id,
                        mode=_mode,
                        intent=intent_classification,
                        config=_retrieval_config,
                        usage_collector=usage_collector,
                    )
                finally:
                    thread_db.close()

            def _do_load_facts():
                if actual_message_count < 10:
                    return "", []
                thread_db = SessionLocal()
                try:
                    from app.services.memory_scoring import (
                        select_facts_multifactor,
                        format_facts_for_prompt,
                    )
                    from app.services.embeddings import embedding_service as _emb_svc

                    scored_facts = select_facts_multifactor(
                        db=thread_db,
                        conversation_id=_conv_id,
                        limit=15,
                        user_query=_user_message_text,
                        embedding_service=_emb_svc,
                    )

                    if scored_facts:
                        section = format_facts_for_prompt(scored_facts)
                        fact_ids = [str(fact.id) for fact, _ in scored_facts]
                        logger.info(
                            f"[Stream Facts] Selected {len(scored_facts)} facts for conversation"
                        )
                        return section, fact_ids
                    return "", []
                except Exception as e:
                    logger.warning(f"[Stream Facts] Failed to load facts: {e}")
                    return "", []
                finally:
                    thread_db.close()

            # Run retrieval and fact loading concurrently
            retrieval_result, (facts_section, selected_fact_ids) = await asyncio.gather(
                asyncio.to_thread(_do_retrieval),
                asyncio.to_thread(_do_load_facts),
            )

            pipeline_timing["retrieval_ms"] = round((time.time() - retrieval_start) * 1000)

            context = retrieval_result.context
            top_chunks = retrieval_result.chunks
            video_map = retrieval_result.video_map

            logger.info(
                f"[Stream] Retrieval: type={retrieval_result.retrieval_type}, "
                f"chunks={len(top_chunks)}, summaries={len(retrieval_result.video_summaries)}"
            )

            # Determine content types for adaptive prompt
            stream_content_types = _get_content_types_in_conversation(video_map)
            has_docs_stream = any(ct != "youtube" for ct in stream_content_types)
            has_vids_stream = "youtube" in stream_content_types
            if has_vids_stream and has_docs_stream:
                stream_source_noun = "sources"
            elif has_docs_stream:
                stream_source_noun = "documents"
            else:
                stream_source_noun = "transcripts"

            # Build LLM messages
            system_prompt = (
                textwrap.dedent(
                    """
                You are InsightGuide, an AI assistant that answers questions using ONLY information from provided {source_noun}.{facts}

                **Core Rules**:
                1. Use ONLY the provided source {source_noun} - never add external knowledge
                2. If information is not in the {source_noun}, say: "This is not mentioned in the provided {source_noun}"
                3. Be concise but thorough - aim for clear, direct answers

                **Citation Rules**:
                - Use simple format: [1], [2], [3] at the end of claims
                - Do NOT write "According to Source 1" - just add [N] after the claim

                **Mode Handling** (mode={mode}):
                - summarize: Brief overview with key points
                - deep_dive: Detailed analysis with all relevant details
                - compare_sources: Compare information across different sources
                - timeline: Present information chronologically
                - extract_actions: List action items or recommendations
                - quiz_me: Ask the user questions to test understanding

                {cross_source_section}
            """
                )
                .strip()
                .format(
                    source_noun=stream_source_noun,
                    facts=facts_section,
                    mode=_mode,
                    cross_source_section=_build_cross_source_section(
                        intent_classification.intent, _mode, num_videos,
                    ),
                )
            )

            llm_messages = [LLMMessage(role="system", content=system_prompt)]
            truncated_history = _truncate_history_messages(
                history_messages[:-1],
                truncate_chars=settings.history_assistant_truncate_chars,
            )
            for role, content in truncated_history:
                llm_messages.append(LLMMessage(role=role, content=content))

            context_label = "Context from sources" if has_docs_stream else "Context from video transcripts"
            user_message_with_context = (
                f"Mode: {_mode}\n"
                f"{context_label}:\n\n{context}\n\n"
                f"---\n\nUser question: {_user_message_text}"
            )
            llm_messages.append(LLMMessage(role="user", content=user_message_with_context))

            # Capture retrieval timing
            retrieval_time = time.time() - start_time

            # === Status: Generating ===
            yield f"data: {json.dumps({'type': 'status', 'stage': 'generating', 'message': 'Generating response...'})}\n\n"

            # --- Stream LLM response (async wrapper to avoid blocking event loop) ---
            llm_start = time.time()

            _STREAM_DONE = object()  # sentinel – StopIteration cannot cross executor boundary

            async def _async_stream_llm():
                """Wrap sync iterator in async generator via run_in_executor."""
                loop = asyncio.get_event_loop()
                # Reasoner models need higher max_tokens because reasoning
                # tokens count against the same budget as content tokens
                if "reasoner" in resolved_model:
                    stream_max_tokens = settings.llm_max_tokens_reasoner
                else:
                    stream_max_tokens = settings.llm_max_tokens

                gen = llm_service.stream_complete(
                    llm_messages,
                    model=resolved_model,
                    max_tokens=stream_max_tokens,
                )

                def _next_chunk():
                    try:
                        return next(gen)
                    except StopIteration:
                        return _STREAM_DONE

                while True:
                    chunk = await loop.run_in_executor(None, _next_chunk)
                    if chunk is _STREAM_DONE:
                        break
                    yield chunk

            async for chunk in _async_stream_llm():
                full_content.append(chunk)
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

            llm_time = time.time() - llm_start
            pipeline_timing["llm_ms"] = round(llm_time * 1000)

            # Capture reasoning content from DeepSeek Reasoner (if available)
            reasoning_content = llm_service.get_last_stream_reasoning_content()

            # === Post-streaming persistence (use fresh DB session for thread safety) ===
            persist_db = SessionLocal()
            try:
                assistant_content = "".join(full_content)

                # Validate citation markers (CIT-002) and extract used markers (CIT-001)
                _validate_citation_markers(assistant_content, len(top_chunks))
                used_markers = _extract_used_markers(assistant_content, len(top_chunks))

                assistant_message = MessageModel(
                    id=message_id,
                    conversation_id=_conv_id,
                    role="assistant",
                    content=assistant_content,
                    token_count=len(assistant_content.split()),
                    chunks_retrieved_count=len(top_chunks),
                    chunks_used_count=len(used_markers),
                    response_time_seconds=time.time() - start_time,
                    llm_provider="deepseek",
                    llm_model=resolved_model,
                )
                persist_db.add(assistant_message)

                # Look up Chunk DB objects for MessageChunkReference persistence + metadata
                from app.models import MessageChunkReference, Chunk

                chunk_by_id = {}
                chunk_by_video_index = {}
                if retrieval_result.retrieval_type != "summaries":
                    chunk_ids = [c.chunk_id for c in top_chunks if c.chunk_id]
                    video_index_pairs = [
                        (c.video_id, c.chunk_index) for c in top_chunks if c.chunk_index is not None
                    ]
                    if chunk_ids:
                        for chunk in persist_db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all():
                            chunk_by_id[chunk.id] = chunk
                    if video_index_pairs:
                        video_ids_for_index = list({vid for vid, _ in video_index_pairs})
                        chunk_indices_for_query = list({idx for _, idx in video_index_pairs})
                        candidate_chunks = (
                            persist_db.query(Chunk)
                            .filter(Chunk.video_id.in_(video_ids_for_index))
                            .filter(Chunk.chunk_index.in_(chunk_indices_for_query))
                            .all()
                        )
                        for chunk in candidate_chunks:
                            key = (chunk.video_id, chunk.chunk_index)
                            chunk_by_video_index[key] = chunk

                # Build chunk references for citations
                chunk_refs_response = []
                if retrieval_result.retrieval_type == "summaries":
                    # Summary-level references — attach first chunk timestamp for jump URLs
                    summary_video_ids = [vs.video_id for vs in retrieval_result.video_summaries]
                    first_chunks = _get_best_chunk_for_videos(persist_db, summary_video_ids, query=_user_message_text)
                    for idx, vs in enumerate(retrieval_result.video_summaries, 1):
                        video = video_map.get(vs.video_id)
                        is_doc = vs.content_type != "youtube"
                        first_chunk = first_chunks.get(vs.video_id)
                        if is_doc:
                            page = getattr(first_chunk, "page_number", None) if first_chunk else None
                            location = f"Page {page}" if page else ("Page 1" if vs.page_count else "Document")
                            jump = f"/documents/{vs.video_id}?page={page or 1}"
                        else:
                            start_ts = first_chunk.start_timestamp if first_chunk else 0
                            location = _format_timestamp_display(start_ts, first_chunk.end_timestamp if first_chunk else 0) if first_chunk else "Full video"
                            jump = _build_youtube_jump_url(video, start_ts) if video else None
                        chunk_refs_response.append({
                            "chunk_id": str(getattr(first_chunk, 'chunk_id', None) or getattr(first_chunk, 'id', None)) if first_chunk else None,
                            "video_id": str(vs.video_id),
                            "video_title": vs.title,
                            "youtube_id": video.youtube_id if video and not is_doc else None,
                            "video_url": _build_source_url(video),
                            "jump_url": jump,
                            "start_timestamp": first_chunk.start_timestamp if first_chunk else 0,
                            "end_timestamp": first_chunk.end_timestamp if first_chunk else (vs.duration_seconds or 0),
                            "text_snippet": _truncate_snippet(vs.summary, limit=SNIPPET_PREVIEW_MAX_CHARS),
                            "relevance_score": 1.0,
                            "timestamp_display": location,
                            "rank": idx,
                            "speakers": first_chunk.speakers if first_chunk and first_chunk.speakers else None,
                            "chapter_title": first_chunk.chapter_title if first_chunk and first_chunk.chapter_title else None,
                            "channel_name": vs.channel_name if not is_doc else None,
                            "content_type": vs.content_type,
                            "page_number": getattr(first_chunk, "page_number", None) if first_chunk else (1 if is_doc else None),
                            "section_heading": getattr(first_chunk, "section_heading", None) if first_chunk else None,
                            "location_display": location,
                        })
                else:
                    # Chunk-level references
                    for rank, scored_chunk in enumerate(top_chunks, 1):
                        video = video_map.get(scored_chunk.video_id)

                        # Look up Chunk DB object for persistence + metadata
                        chunk_db = None
                        if scored_chunk.chunk_id and scored_chunk.chunk_id in chunk_by_id:
                            chunk_db = chunk_by_id[scored_chunk.chunk_id]
                        if not chunk_db and scored_chunk.chunk_index is not None:
                            chunk_db = chunk_by_video_index.get(
                                (scored_chunk.video_id, scored_chunk.chunk_index)
                            )

                        # Save MessageChunkReference for citation persistence on reload
                        if chunk_db:
                            ref = MessageChunkReference(
                                id=uuid.uuid4(),
                                message_id=message_id,
                                chunk_id=chunk_db.id,
                                relevance_score=scored_chunk.score,
                                rank=rank,
                                was_used_in_response=(rank in used_markers),
                            )
                            persist_db.add(ref)

                        location_display = _format_location_display(scored_chunk)
                        snippet = _truncate_snippet(
                            scored_chunk.text, limit=SNIPPET_PREVIEW_MAX_CHARS
                        )
                        s_content_type = getattr(video, "content_type", "youtube") if video else "youtube"
                        s_is_doc = s_content_type != "youtube"
                        chunk_refs_response.append({
                            "chunk_id": str(scored_chunk.chunk_id) if scored_chunk.chunk_id else None,
                            "video_id": str(scored_chunk.video_id),
                            "video_title": video.title if video else "Unknown",
                            "youtube_id": video.youtube_id if video and not s_is_doc else None,
                            "video_url": _build_source_url(video),
                            "jump_url": _build_jump_url(video, scored_chunk),
                            "start_timestamp": scored_chunk.start_timestamp or 0,
                            "end_timestamp": scored_chunk.end_timestamp or 0,
                            "text_snippet": snippet,
                            "relevance_score": scored_chunk.score,
                            "timestamp_display": location_display,
                            "rank": rank,
                            "speakers": chunk_db.speakers if chunk_db and chunk_db.speakers else None,
                            "chapter_title": chunk_db.chapter_title if chunk_db and chunk_db.chapter_title else None,
                            "channel_name": video.channel_name if video and video.channel_name and not s_is_doc else None,
                            "content_type": s_content_type,
                            "page_number": getattr(scored_chunk, "page_number", None) or (getattr(chunk_db, "page_number", None) if chunk_db else None),
                            "section_heading": getattr(scored_chunk, "section_heading", None) or (getattr(chunk_db, "section_heading", None) if chunk_db else None),
                            "location_display": location_display,
                        })

                # --- Answer Confidence (computed from retrieval signals, NOT LLM self-report) ---
                chunk_count = len(chunk_refs_response)
                if chunk_count > 0:
                    avg_relevance = sum(
                        r.get("relevance_score", 0) for r in chunk_refs_response
                    ) / chunk_count
                    unique_videos = len(set(
                        r.get("video_id") for r in chunk_refs_response if r.get("video_id")
                    ))
                else:
                    avg_relevance = 0.0
                    unique_videos = 0

                if avg_relevance >= 0.75 and chunk_count >= 2:
                    confidence_level = "strong"
                elif avg_relevance >= 0.50 and chunk_count >= 1:
                    confidence_level = "moderate"
                else:
                    confidence_level = "limited"

                confidence = {
                    "level": confidence_level,
                    "avg_relevance": round(avg_relevance, 3),
                    "chunk_count": chunk_count,
                    "unique_videos": unique_videos,
                }

                # --- Retrieval Transparency Metadata ---
                retrieval_stats = retrieval_result.retrieval_stats or {}
                retrieval_metadata = {
                    "original_query": _user_message_text,
                    "effective_query": effective_query if effective_query != _user_message_text else None,
                    "retrieval_type": retrieval_result.retrieval_type,
                    "total_retrieved": retrieval_stats.get("total_retrieved", len(top_chunks)),
                    "total_after_filter": retrieval_stats.get("after_filter", len(top_chunks)),
                    "total_after_rerank": retrieval_stats.get("after_rerank", len(top_chunks)),
                    "final_chunks": chunk_count,
                    "unique_videos": unique_videos,
                    "timing": {
                        "retrieval_ms": pipeline_timing.get("retrieval_ms", 0),
                        "rewrite_ms": pipeline_timing.get("rewrite_ms", 0),
                        "llm_ms": pipeline_timing.get("llm_ms", 0),
                        "total_ms": round((time.time() - start_time) * 1000),
                    },
                }

                # --- Store metadata in message_metadata JSONB ---
                msg_metadata = {}
                if retrieval_result.retrieval_type == "summaries" and chunk_refs_response:
                    msg_metadata["summary_sources"] = chunk_refs_response
                msg_metadata["confidence"] = confidence
                msg_metadata["retrieval_metadata"] = retrieval_metadata
                if reasoning_content:
                    msg_metadata["reasoning_content"] = reasoning_content
                    msg_metadata["reasoning_tokens"] = len(reasoning_content.split())
                assistant_message.message_metadata = msg_metadata if msg_metadata else None

                # Update conversation metadata
                conversation_obj = persist_db.query(Conversation).filter(Conversation.id == _conv_id).first()
                if conversation_obj:
                    conversation_obj.message_count = (
                        persist_db.query(MessageModel)
                        .filter(MessageModel.conversation_id == _conv_id)
                        .count()
                    )
                    conversation_obj.last_message_at = assistant_message.created_at

                persist_db.commit()

                # Track chat message for usage quota
                from app.services.usage_tracker import UsageTracker

                usage_tracker = UsageTracker(persist_db)
                estimated_input_tokens = int(len(user_message_with_context.split()) * 1.3)
                estimated_output_tokens = int(len(assistant_content.split()) * 1.3)
                usage_tracker.track_chat_message(
                    user_id=_user_id,
                    conversation_id=_conv_id,
                    message_id=message_id,
                    tokens_in=estimated_input_tokens,
                    tokens_out=estimated_output_tokens,
                    chunks_retrieved=len(chunk_refs_response),
                )

                # Track streaming LLM usage (estimated — stream API doesn't return usage)
                from app.models.llm_usage import LLMUsageEvent, CallType
                streaming_usage = {
                    "input_tokens": estimated_input_tokens,
                    "output_tokens": estimated_output_tokens,
                    "total_tokens": estimated_input_tokens + estimated_output_tokens,
                }
                streaming_event = LLMUsageEvent.create_from_response(
                    user_id=_user_id,
                    model=resolved_model,
                    provider="deepseek",
                    usage=streaming_usage,
                    conversation_id=_conv_id,
                    message_id=message_id,
                    response_time_seconds=llm_time,
                    call_type=CallType.CHAT_STREAMING,
                )
                persist_db.add(streaming_event)

                # Flush auxiliary LLM usage events (query expansion, rewriting, etc.)
                aux_count = usage_collector.flush(persist_db)
                persist_db.commit()
                if aux_count > 0:
                    logger.info(f"[Stream Cost] Recorded {aux_count} auxiliary + 1 streaming LLM events")

                # Fact access reinforcement (facts used in this turn get stronger)
                if selected_fact_ids:
                    try:
                        from app.services.memory_scoring import update_fact_access

                        update_fact_access(persist_db, selected_fact_ids)
                        logger.debug(f"[Stream Memory] Reinforced {len(selected_fact_ids)} facts")
                    except Exception as e:
                        logger.warning(f"[Stream Memory] Failed to update fact access: {e}")

                # Extract facts from this conversation turn
                new_facts_count = 0
                try:
                    from app.services.fact_extraction import FactExtractionService

                    fact_service = FactExtractionService(usage_collector=usage_collector)
                    msg_refreshed = persist_db.query(MessageModel).filter(MessageModel.id == message_id).first()
                    conv_refreshed = persist_db.query(Conversation).filter(Conversation.id == _conv_id).first()

                    extracted_facts = fact_service.extract_facts(
                        db=persist_db,
                        message=msg_refreshed or assistant_message,
                        conversation=conv_refreshed or conversation_obj,
                        user_query=_user_message_text,
                    )

                    for fact in extracted_facts:
                        persist_db.add(fact)

                    if extracted_facts:
                        new_facts_count = len(extracted_facts)
                        persist_db.commit()
                        logger.info(
                            f"[Stream Facts] Saved {new_facts_count} facts for conversation {_conv_id}"
                        )
                except Exception as e:
                    logger.warning(f"[Stream Facts] Fact extraction failed: {e}")

            finally:
                persist_db.close()

            # Send final metadata (enriched with confidence, retrieval, reasoning)
            done_payload = {
                "type": "done",
                "message_id": str(message_id),
                "sources": chunk_refs_response,
                "token_count": len(assistant_content.split()),
                "response_time_seconds": time.time() - start_time,
                "confidence": confidence,
                "retrieval_metadata": retrieval_metadata,
                "new_facts_count": new_facts_count,
                "pipeline_timing": pipeline_timing,
            }
            if reasoning_content:
                done_payload["reasoning_content"] = reasoning_content
                done_payload["reasoning_tokens"] = len(reasoning_content.split())
            yield f"data: {json.dumps(done_payload)}\n\n"

            # --- Follow-up Questions (Pro/Enterprise only — LLM cost per message) ---
            if _is_paid:
                try:
                    from app.services.followup_questions import generate_followup_questions

                    followup_questions = await asyncio.to_thread(
                        generate_followup_questions,
                        query=_user_message_text,
                        response=assistant_content,
                        chunks=top_chunks,
                        mode=_mode,
                        num_videos=num_videos,
                        usage_collector=usage_collector,
                    )
                    if followup_questions:
                        yield f"data: {json.dumps({'type': 'followup_questions', 'questions': followup_questions})}\n\n"

                    # Flush any remaining usage events (followup, late fact extraction)
                    if len(usage_collector) > 0:
                        flush_db = SessionLocal()
                        try:
                            usage_collector.flush(flush_db)
                            flush_db.commit()
                        finally:
                            flush_db.close()
                except Exception as e:
                    logger.warning(f"[Follow-up Questions] Failed: {e}")

        except Exception as e:
            logger.error(f"[Streaming] Error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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


# ---- Memory Visibility API Endpoints ----


@router.get("/{conversation_id}/facts")
async def get_conversation_facts(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all facts for a conversation, grouped by category."""
    _ensure_conversation_owned(db, conversation_id, current_user)

    from app.models.conversation_fact import ConversationFact

    facts = (
        db.query(ConversationFact)
        .filter(ConversationFact.conversation_id == conversation_id)
        .order_by(ConversationFact.category, ConversationFact.created_at.desc())
        .all()
    )

    # Group by category
    grouped: Dict[str, list] = {}
    for fact in facts:
        category = fact.category or "topic"
        if category not in grouped:
            grouped[category] = []
        grouped[category].append({
            "id": str(fact.id),
            "fact_key": fact.fact_key,
            "fact_value": fact.fact_value,
            "confidence_score": fact.confidence_score,
            "importance": fact.importance,
            "category": fact.category,
            "access_count": fact.access_count,
            "source_turn": fact.source_turn,
            "created_at": fact.created_at.isoformat() if fact.created_at else None,
            "last_accessed": fact.last_accessed.isoformat() if fact.last_accessed else None,
        })

    return {
        "total": len(facts),
        "facts_by_category": grouped,
    }


@router.delete("/{conversation_id}/facts/{fact_id}")
async def delete_conversation_fact(
    conversation_id: uuid.UUID,
    fact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a single fact from conversation memory."""
    _ensure_conversation_owned(db, conversation_id, current_user)

    from app.models.conversation_fact import ConversationFact

    fact = (
        db.query(ConversationFact)
        .filter(
            ConversationFact.id == fact_id,
            ConversationFact.conversation_id == conversation_id,
        )
        .first()
    )
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    db.delete(fact)
    db.commit()

    return {"message": "Fact deleted", "fact_id": str(fact_id)}


@router.delete("/{conversation_id}/facts")
async def clear_conversation_facts(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all facts from conversation memory."""
    _ensure_conversation_owned(db, conversation_id, current_user)

    from app.models.conversation_fact import ConversationFact

    count = (
        db.query(ConversationFact)
        .filter(ConversationFact.conversation_id == conversation_id)
        .delete()
    )
    db.commit()

    return {"message": f"Cleared {count} facts", "deleted_count": count}


# ---- Export API Endpoint (Pro/Enterprise only) ----


@router.get("/{conversation_id}/export")
async def export_conversation(
    conversation_id: uuid.UUID,
    format: str = Query("markdown", pattern="^(markdown)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export a conversation as markdown. Pro/Enterprise only.

    Args:
        conversation_id: Conversation UUID
        format: Export format (currently only "markdown")

    Returns:
        Markdown text of the conversation
    """
    user_tier = current_user.subscription_tier or "free"
    if user_tier not in ("pro", "enterprise"):
        raise HTTPException(
            status_code=403,
            detail="Conversation export is a Pro feature. Upgrade to access.",
        )

    conversation = _ensure_conversation_owned(db, conversation_id, current_user)

    messages = (
        db.query(MessageModel)
        .filter(
            MessageModel.conversation_id == conversation_id,
            MessageModel.role != SYSTEM_ROLE,
        )
        .order_by(MessageModel.created_at.asc())
        .all()
    )

    # Build markdown
    lines = [
        f"# {conversation.title or 'Untitled Conversation'}",
        "",
        f"*Exported on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        f"*{len(messages)} messages*",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role_label = "You" if msg.role == "user" else "Assistant"
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M") if msg.created_at else ""
        lines.append(f"### {role_label} ({timestamp})")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

    markdown_content = "\n".join(lines)

    from fastapi.responses import Response

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.md"',
        },
    )
