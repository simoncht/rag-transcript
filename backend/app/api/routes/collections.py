"""
API endpoints for collection management.

Endpoints:
- POST /collections - Create new collection
- GET /collections - List user's collections
- GET /collections/{collection_id} - Get collection details with videos
- PATCH /collections/{collection_id} - Update collection
- DELETE /collections/{collection_id} - Delete collection
- POST /collections/{collection_id}/videos - Add videos to collection
- DELETE /collections/{collection_id}/videos/{video_id} - Remove video from collection
"""
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.nextauth import get_current_user
from app.db.base import get_db
from app.models import Collection, CollectionVideo, Video, User
from app.schemas import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    CollectionAddVideosRequest,
    CollectionDetail,
    CollectionList,
    CollectionSummary,
    CollectionVideoInfo,
    CollectionThemesResponse,
    ClusteredThemesResponse,
    CollectionInsightsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=CollectionDetail)
async def create_collection(
    request: CollectionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new collection.

    Args:
        request: Collection creation request with name, description, and metadata

    Returns:
        CollectionDetail with created collection
    """
    # Note: Duplicate collection names are allowed per user
    collection = Collection(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        meta=request.metadata or {},
        is_default=False,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)

    # Return with video count
    return CollectionDetail(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        metadata=collection.meta,
        is_default=collection.is_default,
        video_count=0,
        total_duration_seconds=0,
        videos=[],
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get("", response_model=CollectionList)
async def list_collections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user's collections with pagination.

    Args:
        skip: Number of records to skip
        limit: Number of records to return

    Returns:
        CollectionList with collections and total count
    """
    query = db.query(Collection).filter(
        Collection.user_id == current_user.id,
        Collection.is_deleted.is_(False),
    )

    total = query.count()

    collections = (
        query.order_by(
            Collection.is_default.desc(),  # Default collection first
            Collection.name.asc(),  # Then alphabetically by name
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Build summaries with video counts
    summaries = []
    for collection in collections:
        # Get video count and total duration
        video_stats = (
            db.query(
                func.count(CollectionVideo.video_id).label("count"),
                func.sum(Video.duration_seconds).label("total_duration"),
            )
            .join(Video, CollectionVideo.video_id == Video.id)
            .filter(
                CollectionVideo.collection_id == collection.id,
                Video.is_deleted.is_(False),
            )
            .first()
        )

        video_count = video_stats.count or 0
        total_duration = int(video_stats.total_duration or 0)

        summaries.append(
            CollectionSummary(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                metadata=collection.meta,
                is_default=collection.is_default,
                video_count=video_count,
                total_duration_seconds=total_duration,
                created_at=collection.created_at,
                updated_at=collection.updated_at,
            )
        )

    return CollectionList(total=total, collections=summaries)


@router.get("/{collection_id}", response_model=CollectionDetail)
async def get_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get collection details with all videos.

    Args:
        collection_id: Collection UUID

    Returns:
        CollectionDetail including all videos in the collection
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get all videos in this collection
    collection_videos = (
        db.query(CollectionVideo, Video)
        .join(Video, CollectionVideo.video_id == Video.id)
        .filter(
            CollectionVideo.collection_id == collection_id, Video.is_deleted.is_(False)
        )
        .order_by(CollectionVideo.position.nullslast(), CollectionVideo.added_at.desc())
        .all()
    )

    # Build video info list
    videos = []
    total_duration = 0
    for cv, video in collection_videos:
        videos.append(
            CollectionVideoInfo(
                id=video.id,
                title=video.title,
                youtube_id=video.youtube_id,
                content_type=getattr(video, "content_type", "youtube"),
                duration_seconds=video.duration_seconds,
                status=video.status,
                thumbnail_url=video.thumbnail_url,
                tags=video.tags or [],
                added_at=cv.added_at,
                position=cv.position,
            )
        )
        if video.duration_seconds:
            total_duration += video.duration_seconds

    return CollectionDetail(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        metadata=collection.meta,
        is_default=collection.is_default,
        video_count=len(videos),
        total_duration_seconds=total_duration,
        videos=videos,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.patch("/{collection_id}", response_model=CollectionDetail)
async def update_collection(
    collection_id: uuid.UUID,
    request: CollectionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update collection (name, description, or metadata).

    Args:
        collection_id: Collection UUID
        request: Update request with optional name, description, metadata

    Returns:
        CollectionDetail with updated collection
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Cannot rename default collection
    if collection.is_default and request.name is not None:
        raise HTTPException(
            status_code=400, detail="Cannot rename default 'Uncategorized' collection"
        )

    # Update fields
    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description
    if request.metadata is not None:
        collection.meta = request.metadata

    collection.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(collection)

    # Return full details (reuse get_collection logic)
    return await get_collection(collection_id, db, current_user)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a collection (soft delete - videos are kept).

    Args:
        collection_id: Collection UUID

    Returns:
        Success message
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Cannot delete default collection
    if collection.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default 'Uncategorized' collection"
        )

    # Soft delete instead of hard delete
    collection.is_deleted = True
    collection.deleted_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Collection deleted successfully",
        "collection_id": str(collection_id),
    }


@router.post("/{collection_id}/videos", response_model=CollectionDetail)
async def add_videos_to_collection(
    collection_id: uuid.UUID,
    request: CollectionAddVideosRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add videos to a collection.

    Args:
        collection_id: Collection UUID
        request: Request with video IDs to add

    Returns:
        CollectionDetail with updated collection
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Validate that all videos exist and belong to user
    videos = (
        db.query(Video)
        .filter(
            Video.id.in_(request.video_ids),
            Video.user_id == current_user.id,
            Video.is_deleted.is_(False),
        )
        .all()
    )

    if len(videos) != len(request.video_ids):
        raise HTTPException(status_code=400, detail="One or more videos not found")

    # Add videos to collection (skip if already exists)
    added_count = 0
    for video in videos:
        existing = (
            db.query(CollectionVideo)
            .filter(
                CollectionVideo.collection_id == collection_id,
                CollectionVideo.video_id == video.id,
            )
            .first()
        )

        if not existing:
            cv = CollectionVideo(
                collection_id=collection_id,
                video_id=video.id,
                added_by_user_id=current_user.id,
            )
            db.add(cv)
            added_count += 1

    if added_count > 0:
        collection.updated_at = datetime.utcnow()
        db.commit()

    # Return full details
    return await get_collection(collection_id, db, current_user)


@router.delete("/{collection_id}/videos/{video_id}")
async def remove_video_from_collection(
    collection_id: uuid.UUID,
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a video from a collection.

    Args:
        collection_id: Collection UUID
        video_id: Video UUID

    Returns:
        Success message
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Find the collection_video relationship
    cv = (
        db.query(CollectionVideo)
        .filter(
            CollectionVideo.collection_id == collection_id,
            CollectionVideo.video_id == video_id,
        )
        .first()
    )

    if not cv:
        raise HTTPException(
            status_code=404, detail="Video not found in this collection"
        )

    db.delete(cv)
    collection.updated_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Video removed from collection successfully",
        "collection_id": str(collection_id),
        "video_id": str(video_id),
    }


@router.get("/{collection_id}/themes", response_model=CollectionThemesResponse)
async def get_collection_themes(
    collection_id: uuid.UUID,
    refresh: bool = Query(False, description="Force regenerate themes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated themes/topics for a collection.

    Aggregates key_topics from all videos in the collection,
    ranked by frequency. Results are cached for 1 hour.

    Args:
        collection_id: Collection UUID
        refresh: Force regenerate instead of using cache

    Returns:
        CollectionThemesResponse with ranked themes
    """
    # Verify collection exists and belongs to user
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    from app.services.theme_service import get_theme_service

    theme_service = get_theme_service()
    themes = theme_service.aggregate_collection_themes(
        db=db,
        collection_id=collection_id,
        user_id=current_user.id,
        force_refresh=refresh,
    )

    # Count total videos and those with topics
    total_videos = (
        db.query(func.count(CollectionVideo.video_id))
        .join(Video, CollectionVideo.video_id == Video.id)
        .filter(
            CollectionVideo.collection_id == collection_id,
            Video.is_deleted.is_(False),
        )
        .scalar()
        or 0
    )

    videos_with_topics = (
        db.query(func.count(CollectionVideo.video_id))
        .join(Video, CollectionVideo.video_id == Video.id)
        .filter(
            CollectionVideo.collection_id == collection_id,
            Video.is_deleted.is_(False),
            Video.key_topics.isnot(None),
        )
        .scalar()
        or 0
    )

    # Determine if result was cached (themes list matches what's in meta)
    meta = collection.meta or {}
    cached = not refresh and meta.get("cached_themes") is not None

    return CollectionThemesResponse(
        collection_id=collection_id,
        themes=themes,
        total_videos=total_videos,
        videos_with_topics=videos_with_topics,
        cached=cached,
    )


@router.get("/{collection_id}/themes/clustered", response_model=ClusteredThemesResponse)
async def get_clustered_themes(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get LLM-clustered themes for a collection.

    Returns previously generated clustered themes from the database.
    Use POST /themes/regenerate to generate or refresh.

    Args:
        collection_id: Collection UUID

    Returns:
        ClusteredThemesResponse with clustered themes
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    from app.models.collection_theme import CollectionTheme

    themes = (
        db.query(CollectionTheme)
        .filter(CollectionTheme.collection_id == collection_id)
        .order_by(CollectionTheme.relevance_score.desc().nullslast())
        .all()
    )

    return ClusteredThemesResponse(
        collection_id=collection_id,
        themes=[
            {
                "theme_label": t.theme_label,
                "theme_description": t.theme_description,
                "video_ids": t.video_ids or [],
                "relevance_score": t.relevance_score,
                "topic_keywords": t.topic_keywords or [],
            }
            for t in themes
        ],
    )


@router.post("/{collection_id}/themes/regenerate")
async def regenerate_themes(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger async regeneration of clustered themes for a collection.

    Uses embedding-based clustering + LLM labeling.
    Runs as a Celery background task.

    Args:
        collection_id: Collection UUID

    Returns:
        Task ID for tracking progress
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    from app.tasks.video_tasks import regenerate_collection_themes

    task = regenerate_collection_themes.delay(
        str(collection_id), str(current_user.id)
    )

    return {
        "message": "Theme regeneration started",
        "task_id": task.id,
        "collection_id": str(collection_id),
    }


@router.get("/{collection_id}/insights", response_model=CollectionInsightsResponse)
async def get_collection_insights(
    collection_id: uuid.UUID,
    refresh: bool = Query(False, description="Force regenerate insights"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get topic map insights for a collection.

    Generates a mind-map style topic graph across all videos in the collection.
    Results are cached and reused until the video set changes or refresh is requested.
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_deleted.is_(False),
        )
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    from app.services.collection_insights import collection_insights_service

    try:
        insight, was_cached = collection_insights_service.get_or_generate_insights(
            db=db,
            collection_id=collection_id,
            user_id=current_user.id,
            force_regenerate=refresh,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate collection insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Failed to generate topic map. The LLM service may be temporarily unavailable.",
        )

    return CollectionInsightsResponse(
        collection_id=collection_id,
        graph={
            "nodes": (insight.graph_data or {}).get("nodes", []),
            "edges": (insight.graph_data or {}).get("edges", []),
        },
        metadata={
            "topics_count": insight.topics_count,
            "total_chunks_analyzed": insight.total_chunks_analyzed,
            "generation_time_seconds": insight.generation_time_seconds,
            "cached": was_cached,
            "created_at": insight.created_at,
            "llm_provider": insight.llm_provider,
            "llm_model": insight.llm_model,
            "extraction_prompt_version": insight.extraction_prompt_version,
        },
    )
