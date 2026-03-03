"""
API endpoints for content discovery.

Endpoints:
- POST /discovery/search - Search YouTube for videos
- POST /discovery/import - Batch import videos
- GET/POST/DELETE /discovery/sources - Manage discovery sources
- GET/POST /discovery/content - Manage discovered content
- GET /discovery/recommendations - Get recommendations
- GET /discovery/channel-info - Get YouTube channel info
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.nextauth import get_current_user
from app.core.rate_limit import limiter
from app.db.base import get_db
from app.models import User, Video, Job
from app.schemas.discovery import (
    YouTubeSearchRequest,
    YouTubeSearchResult,
    YouTubeSearchResponse,
    YouTubeBatchImportRequest,
    YouTubeBatchImportResponse,
    BatchImportResultItem,
    DiscoverySourceCreate,
    DiscoverySourceUpdate,
    DiscoverySourceResponse,
    DiscoverySourceList,
    DiscoveredContentResponse,
    DiscoveredContentList,
    DiscoveredContentAction,
    BulkDiscoveredContentAction,
    ChannelInfoRequest,
    ChannelInfoResponse,
    RecommendationResponse,
)
from app.providers.registry import provider_registry
from app.services.discovery_service import DiscoveryService, get_discovery_service
from app.services.quota_service import QuotaService
from app.services.notification_service import NotificationService
from app.tasks.video_tasks import process_video_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# YouTube Search
# =============================================================================


@router.post("/search", response_model=YouTubeSearchResponse)
@limiter.limit("30/minute")
async def search_youtube(
    request: Request,
    search_request: YouTubeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search YouTube for videos.

    Rate limited to protect YouTube API quota.
    Uses the user's daily search quota based on tier.
    """
    # Check YouTube search quota
    quota_service = QuotaService(db)
    check_result = quota_service.check_quota(
        current_user.id,
        "youtube_searches",
        amount=1,
    )

    if not check_result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Daily YouTube search quota exceeded",
                "quota_type": "youtube_searches",
                "upgrade_url": "/pricing",
            },
        )

    # Get YouTube provider
    try:
        provider = provider_registry.get_content_provider("youtube")
    except ValueError:
        raise HTTPException(
            status_code=503,
            detail="YouTube search is not available",
        )

    # Execute search with pagination support
    try:
        results, next_token, prev_token, total_results = await provider.search(
            query=search_request.query,
            max_results=search_request.max_results,
            page_token=search_request.page_token,
            duration=search_request.duration,
            published_after=search_request.published_after,
            order=search_request.order,
            category=search_request.category,
        )
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Search failed. Please try again later.",
        )

    # Increment quota usage
    quota_info = quota_service.increment(current_user.id, "youtube_searches", 1)

    # Query existing videos to mark as already_imported
    video_ids = [r.id for r in results]
    existing_videos = (
        db.query(Video.youtube_id)
        .filter(
            Video.user_id == current_user.id,
            Video.youtube_id.in_(video_ids),
            Video.is_deleted.is_(False),
        )
        .all()
    )
    existing_ids = {v.youtube_id for v in existing_videos}

    # Convert to response
    search_results = [
        YouTubeSearchResult(
            id=r.id,
            title=r.title,
            description=r.description,
            thumbnail_url=r.thumbnail_url,
            duration_seconds=r.duration_seconds,
            published_at=r.published_at,
            channel_name=r.channel_name,
            channel_id=r.channel_id,
            view_count=r.view_count,
            already_imported=r.id in existing_ids,
        )
        for r in results
    ]

    # Check if we have true pagination (API mode)
    has_api_pagination = next_token is not None or prev_token is not None

    return YouTubeSearchResponse(
        results=search_results,
        total=len(search_results),
        quota_used=1,
        quota_remaining=int(quota_info.remaining) if not quota_info.is_unlimited else 999,
        next_page_token=next_token,
        prev_page_token=prev_token,
        total_results=total_results if has_api_pagination else None,
        has_api_pagination=has_api_pagination,
    )


@router.post("/import", response_model=YouTubeBatchImportResponse)
@limiter.limit("10/minute")
async def batch_import(
    request: Request,
    import_request: YouTubeBatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import multiple YouTube videos at once.

    Validates quota and queues all videos for processing.
    """
    from app.core.quota import check_video_quota, check_minutes_quota

    # Check video quota (verify user can add at least one video)
    try:
        await check_video_quota(current_user, db)
    except HTTPException:
        raise

    # Get provider for metadata
    try:
        provider = provider_registry.get_content_provider("youtube")
    except ValueError:
        raise HTTPException(
            status_code=503,
            detail="YouTube is not available",
        )

    results = []
    imported_count = 0
    failed_count = 0

    for video_id in import_request.video_ids:
        try:
            # Check for existing video
            existing = (
                db.query(Video)
                .filter(
                    Video.user_id == current_user.id,
                    Video.youtube_id == video_id,
                    Video.is_deleted.is_(False),
                )
                .first()
            )

            if existing:
                results.append(
                    BatchImportResultItem(
                        video_id=video_id,
                        success=False,
                        error=f"Video already exists (id: {existing.id})",
                    )
                )
                failed_count += 1
                continue

            # Get metadata
            try:
                metadata = await provider.get_metadata(video_id)
            except Exception as e:
                results.append(
                    BatchImportResultItem(
                        video_id=video_id,
                        success=False,
                        error=f"Failed to fetch metadata: {str(e)}",
                    )
                )
                failed_count += 1
                continue

            # Check minutes quota
            duration_minutes = int((metadata.duration_seconds or 0) / 60)
            try:
                await check_minutes_quota(current_user, duration_minutes, db)
            except HTTPException as e:
                results.append(
                    BatchImportResultItem(
                        video_id=video_id,
                        success=False,
                        error=str(e.detail),
                    )
                )
                failed_count += 1
                continue

            # Create video record
            video = Video(
                user_id=current_user.id,
                youtube_id=video_id,
                youtube_url=f"https://www.youtube.com/watch?v={video_id}",
                title=metadata.title,
                description=metadata.description,
                channel_name=metadata.channel_name,
                channel_id=metadata.channel_id,
                thumbnail_url=metadata.thumbnail_url,
                duration_seconds=metadata.duration_seconds,
                upload_date=metadata.published_at,
                language=metadata.language,
                status="pending",
                progress_percent=0.0,
            )
            db.add(video)
            db.flush()

            # Create job
            job = Job(
                user_id=current_user.id,
                video_id=video.id,
                job_type="full_pipeline",
                status="pending",
                progress_percent=0.0,
            )
            db.add(job)
            db.commit()
            db.refresh(video)
            db.refresh(job)

            # Queue background task
            task = process_video_pipeline.delay(
                video_id=str(video.id),
                youtube_url=video.youtube_url,
                user_id=str(current_user.id),
                job_id=str(job.id),
            )

            job.celery_task_id = task.id
            db.commit()

            # Update user interest profile
            discovery_service = get_discovery_service(db)
            discovery_service.update_interest_profile(
                user_id=current_user.id,
                channel_id=metadata.channel_id,
                channel_name=metadata.channel_name,
                topics=metadata.tags[:5] if metadata.tags else None,
            )

            # Add to collection if specified
            if import_request.collection_id:
                from app.models import CollectionVideo
                cv = CollectionVideo(
                    collection_id=import_request.collection_id,
                    video_id=video.id,
                )
                db.add(cv)
                db.commit()

            results.append(
                BatchImportResultItem(
                    video_id=video_id,
                    success=True,
                    internal_id=video.id,
                    job_id=job.id,
                )
            )
            imported_count += 1

        except Exception as e:
            logger.error(f"Failed to import video {video_id}: {e}")
            results.append(
                BatchImportResultItem(
                    video_id=video_id,
                    success=False,
                    error=str(e),
                )
            )
            failed_count += 1

    return YouTubeBatchImportResponse(
        total=len(import_request.video_ids),
        imported=imported_count,
        failed=failed_count,
        results=results,
    )


# =============================================================================
# Discovery Sources
# =============================================================================


@router.get("/sources", response_model=DiscoverySourceList)
async def list_sources(
    source_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's discovery sources (subscriptions)."""
    service = DiscoveryService(db)
    sources = service.get_user_sources(
        user_id=current_user.id,
        source_type=source_type,
        is_active=is_active,
    )

    return DiscoverySourceList(
        sources=[DiscoverySourceResponse.model_validate(s) for s in sources],
        total=len(sources),
    )


@router.post("/sources", response_model=DiscoverySourceResponse)
async def create_source(
    source_request: DiscoverySourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Subscribe to a discovery source."""
    service = DiscoveryService(db, NotificationService(db))

    try:
        source = await service.subscribe(
            user_id=current_user.id,
            source_type=source_request.source_type,
            source_identifier=source_request.source_identifier,
            is_explicit=True,
            config=source_request.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DiscoverySourceResponse.model_validate(source)


@router.patch("/sources/{source_id}", response_model=DiscoverySourceResponse)
async def update_source(
    source_id: UUID,
    update_request: DiscoverySourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a discovery source."""
    from app.models.discovery import DiscoverySource

    source = (
        db.query(DiscoverySource)
        .filter(
            DiscoverySource.id == source_id,
            DiscoverySource.user_id == current_user.id,
        )
        .first()
    )

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if update_request.is_active is not None:
        source.is_active = update_request.is_active
    if update_request.config is not None:
        source.config = update_request.config
    if update_request.check_frequency_hours is not None:
        source.check_frequency_hours = update_request.check_frequency_hours

    db.commit()
    db.refresh(source)

    return DiscoverySourceResponse.model_validate(source)


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unsubscribe from a discovery source."""
    service = DiscoveryService(db)

    if not service.unsubscribe(current_user.id, source_id):
        raise HTTPException(status_code=404, detail="Source not found")

    return {"message": "Unsubscribed successfully"}


# =============================================================================
# Discovered Content
# =============================================================================


@router.get("/content", response_model=DiscoveredContentList)
async def list_discovered_content(
    status: Optional[str] = Query("pending"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List discovered content for the user."""
    service = DiscoveryService(db)

    items = service.get_discovered_content(
        user_id=current_user.id,
        status=status,
        limit=limit,
        offset=offset,
    )

    pending_count = service.get_pending_count(current_user.id)

    return DiscoveredContentList(
        items=[DiscoveredContentResponse.model_validate(i) for i in items],
        total=len(items),
        pending_count=pending_count,
    )


@router.post("/content/{content_id}/action")
async def action_content(
    content_id: UUID,
    action_request: DiscoveredContentAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Take action on discovered content (import or dismiss)."""
    service = DiscoveryService(db)

    if action_request.action == "import":
        # Get content details
        from app.models.discovery import DiscoveredContent

        content = (
            db.query(DiscoveredContent)
            .filter(
                DiscoveredContent.id == content_id,
                DiscoveredContent.user_id == current_user.id,
            )
            .first()
        )

        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Import via batch import
        import_result = await batch_import(
            request=None,  # Not used in rate limiting here
            import_request=YouTubeBatchImportRequest(
                video_ids=[content.source_identifier],
                collection_id=action_request.collection_id,
            ),
            db=db,
            current_user=current_user,
        )

        # Mark as imported
        service.action_content(current_user.id, content_id, "import")

        return {
            "action": "import",
            "success": import_result.imported > 0,
            "result": import_result.results[0].model_dump() if import_result.results else None,
        }

    elif action_request.action == "dismiss":
        if not service.action_content(current_user.id, content_id, "dismiss"):
            raise HTTPException(status_code=404, detail="Content not found")

        return {"action": "dismiss", "success": True}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action_request.action}")


@router.post("/content/bulk-action")
async def bulk_action_content(
    action_request: BulkDiscoveredContentAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Take action on multiple discovered content items."""
    service = DiscoveryService(db)

    if action_request.action == "dismiss_all":
        count = service.dismiss_all_pending(current_user.id)
        return {"action": "dismiss_all", "count": count}

    count = service.bulk_action(
        current_user.id,
        action_request.content_ids,
        action_request.action,
    )

    return {"action": action_request.action, "count": count}


# =============================================================================
# Channel Info
# =============================================================================


@router.post("/channel-info", response_model=ChannelInfoResponse)
async def get_channel_info(
    info_request: ChannelInfoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get YouTube channel information."""
    try:
        provider = provider_registry.get_content_provider("youtube")
    except ValueError:
        raise HTTPException(status_code=503, detail="YouTube is not available")

    # Resolve channel ID from URL if provided
    channel_id = info_request.channel_id
    if not channel_id and info_request.channel_url:
        channel_id = await provider.get_channel_id_from_url(info_request.channel_url)

    if not channel_id:
        raise HTTPException(status_code=400, detail="Could not resolve channel")

    try:
        info = await provider.get_source_info("youtube_channel", channel_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Check if user is subscribed
    from app.models.discovery import DiscoverySource

    is_subscribed = (
        db.query(DiscoverySource)
        .filter(
            DiscoverySource.user_id == current_user.id,
            DiscoverySource.source_type == "youtube_channel",
            DiscoverySource.source_identifier == channel_id,
            DiscoverySource.is_active == True,  # noqa: E712
        )
        .first()
        is not None
    )

    return ChannelInfoResponse(
        channel_id=channel_id,
        display_name=info.display_name,
        display_image_url=info.display_image_url,
        description=info.description,
        subscriber_count=info.subscriber_count,
        video_count=info.video_count,
        is_subscribed=is_subscribed,
    )


# =============================================================================
# Recommendations
# =============================================================================


@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    strategies: Optional[str] = Query(None, description="Comma-separated strategy types"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get personalized content recommendations."""
    from app.services.recommendation_service import RecommendationEngine

    engine = RecommendationEngine(db)

    strategy_list = None
    if strategies:
        strategy_list = [s.strip() for s in strategies.split(",")]

    try:
        items = await engine.generate(
            user_id=current_user.id,
            strategies=strategy_list,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")

    return RecommendationResponse(
        recommendations=[
            {
                "source_type": item.source_type,
                "source_identifier": item.source_identifier,
                "title": item.title,
                "description": item.description,
                "thumbnail_url": item.thumbnail_url,
                "reason": item.reason,
                "context": item.context,
                "score": item.score,
            }
            for item in items
        ],
        generated_at=datetime.utcnow(),
        strategies_used=strategy_list or list(engine.strategies.keys()),
    )
