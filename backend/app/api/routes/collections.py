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
)

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
    # Check if name already exists for this user (optional - we allow duplicates for now)
    # You can uncomment this if you want unique names per user
    # existing = db.query(Collection).filter(
    #     Collection.user_id == current_user.id,
    #     Collection.name == request.name
    # ).first()
    # if existing:
    #     raise HTTPException(status_code=400, detail="Collection with this name already exists")

    # Create collection
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
    query = db.query(Collection).filter(Collection.user_id == current_user.id)

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
        .filter(Collection.id == collection_id, Collection.user_id == current_user.id)
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
        .filter(Collection.id == collection_id, Collection.user_id == current_user.id)
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
    Delete a collection (videos are kept, just the collection is removed).

    Args:
        collection_id: Collection UUID

    Returns:
        Success message
    """
    collection = (
        db.query(Collection)
        .filter(Collection.id == collection_id, Collection.user_id == current_user.id)
        .first()
    )

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Cannot delete default collection
    if collection.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default 'Uncategorized' collection"
        )

    db.delete(collection)
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
        .filter(Collection.id == collection_id, Collection.user_id == current_user.id)
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
        .filter(Collection.id == collection_id, Collection.user_id == current_user.id)
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
