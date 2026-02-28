"""
API routes for universal content (document upload, list, get, delete).

Handles file uploads for PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB, CSV, RTF, email.
Uses the same videos table with content_type discriminator for backward compatibility.
"""
import logging
from pathlib import Path
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.nextauth import get_current_user
from app.core.rate_limit import limiter
from app.db.base import get_db
from app.models import Video, User, Chunk
from app.schemas.content import (
    DOCUMENT_CONTENT_TYPES,
    EXTENSION_TO_CONTENT_TYPE,
    ContentUploadResponse,
    ContentDetail,
    ContentList,
    ContentDeleteResponse,
    ContentStatusUpdate,
)
from app.services.storage import storage_service
from app.services.usage_tracker import UsageTracker, QuotaExceededError

logger = logging.getLogger(__name__)

router = APIRouter()


def _file_extension_to_content_type(filename: str) -> Optional[str]:
    """Map file extension to content type."""
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_CONTENT_TYPE.get(ext)


def _extract_enrichment_progress(video: Video) -> dict:
    """Extract enrichment progress fields from video source_metadata."""
    from datetime import datetime, timedelta

    meta = video.source_metadata or {}
    chunks_enriched = meta.get("chunks_enriched")
    total_chunks = meta.get("total_chunks")
    eta_seconds = meta.get("eta_seconds")

    # Compute seconds since last progress update
    now = datetime.utcnow()
    seconds_since_update = None
    activity_status = "active"
    processing_rate = None

    processing_statuses = {"pending", "extracting", "extracted", "chunking", "enriching", "indexing"}
    if video.status in processing_statuses:
        # Prefer last_progress_at (set per-chunk), fall back to updated_at
        last_progress_str = meta.get("last_progress_at")
        if last_progress_str:
            try:
                last_progress = datetime.fromisoformat(last_progress_str)
            except (ValueError, TypeError):
                last_progress = video.updated_at
        else:
            last_progress = video.updated_at

        if last_progress:
            delta = now - last_progress
            seconds_since_update = max(0, int(delta.total_seconds()))

            if seconds_since_update < 60:
                activity_status = "active"
            elif seconds_since_update < 300:
                activity_status = "slow"
            elif seconds_since_update < 900:
                activity_status = "stalled"
            else:
                activity_status = "unresponsive"

        # Compute processing rate (chunks/min) from enrichment_started_at
        enrichment_started_at = meta.get("enrichment_started_at")
        if enrichment_started_at and chunks_enriched and chunks_enriched > 0:
            try:
                elapsed = now.timestamp() - float(enrichment_started_at)
                if elapsed > 0:
                    processing_rate = round(chunks_enriched / (elapsed / 60), 1)
            except (ValueError, TypeError):
                pass

    is_active = activity_status in ("active", "slow")

    return {
        "chunks_enriched": chunks_enriched,
        "total_chunks": total_chunks,
        "eta_seconds": eta_seconds,
        "is_active": is_active,
        "activity_status": activity_status if video.status in processing_statuses else None,
        "seconds_since_update": seconds_since_update,
        "processing_rate": processing_rate,
    }


def _video_to_content_detail(video: Video, db: Session) -> ContentDetail:
    """Convert a Video model instance to ContentDetail schema."""
    # Calculate storage
    storage_mb = 0.0
    if video.file_size_bytes:
        storage_mb += video.file_size_bytes / (1024 * 1024)
    if video.audio_file_size_mb:
        storage_mb += video.audio_file_size_mb

    progress = _extract_enrichment_progress(video)

    return ContentDetail(
        id=video.id,
        user_id=video.user_id,
        content_type=video.content_type,
        title=video.title,
        description=video.description,
        original_filename=video.original_filename,
        file_size_bytes=video.file_size_bytes,
        source_url=video.source_url,
        page_count=video.page_count,
        source_metadata=video.source_metadata,
        status=video.status,
        progress_percent=video.progress_percent,
        error_message=video.error_message,
        chunks_enriched=progress["chunks_enriched"],
        total_chunks=progress["total_chunks"],
        eta_seconds=progress["eta_seconds"],
        is_active=progress["is_active"],
        activity_status=progress["activity_status"],
        seconds_since_update=progress["seconds_since_update"],
        processing_rate=progress["processing_rate"],
        chunk_count=video.chunk_count,
        summary=video.summary,
        key_topics=video.key_topics,
        storage_total_mb=round(storage_mb, 2) if storage_mb else None,
        created_at=video.created_at,
        updated_at=video.updated_at,
        completed_at=video.completed_at,
    )


@router.get("/counts")
async def get_content_counts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document counts by status category."""
    base = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.content_type != "youtube",
        Video.is_deleted == False,
    )

    processing_statuses = [
        "pending", "extracting", "extracted", "chunking", "enriching", "indexing",
    ]

    return {
        "total": base.count(),
        "completed": base.filter(Video.status == "completed").count(),
        "processing": base.filter(Video.status.in_(processing_statuses)).count(),
        "failed": base.filter(Video.status == "failed").count(),
    }


@router.get("/limits")
async def get_content_limits(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document upload limits for current user's tier."""
    from app.core.pricing import get_tier_config

    user_tier = current_user.subscription_tier or "free"
    tier_config = get_tier_config(user_tier)

    return {
        "tier": user_tier,
        "max_upload_size_mb": tier_config.get("max_upload_size_mb", 100),
        "max_document_words": tier_config.get("max_document_words", -1),
    }


@router.post("/upload", response_model=ContentUploadResponse, status_code=201)
@limiter.limit("10/minute")
async def upload_content(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document for processing.

    Accepts: PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB, CSV, RTF, EML.
    Max file size: configured via MAX_UPLOAD_SIZE_MB (default 100 MB).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Determine content type from extension
    content_type = _file_extension_to_content_type(file.filename)
    if not content_type:
        ext = Path(file.filename).suffix.lower()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported types: {', '.join(EXTENSION_TO_CONTENT_TYPE.keys())}",
        )

    if content_type not in settings.allowed_file_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' is not allowed. Allowed: {', '.join(settings.allowed_file_types)}",
        )

    # Check file size against per-tier limit
    file_content = await file.read()
    file_size_bytes = len(file_content)

    from app.core.pricing import get_tier_config
    user_tier = current_user.subscription_tier or "free"
    tier_config = get_tier_config(user_tier)
    tier_max_mb = tier_config.get("max_upload_size_mb", settings.max_upload_size_mb)
    max_bytes = tier_max_mb * 1024 * 1024

    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_bytes / (1024*1024):.1f} MB. "
                   f"Your {user_tier} plan allows up to {tier_max_mb} MB per document.",
        )

    if file_size_bytes == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Check document count quota
    from app.core.quota import check_document_quota
    await check_document_quota(current_user, db)

    # Check storage quota
    try:
        usage_tracker = UsageTracker(db)
        usage_tracker.check_quota(current_user.id, "storage", file_size_bytes / (1024 * 1024))
    except QuotaExceededError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Determine title
    doc_title = title or Path(file.filename).stem

    # Create video record (content_type != 'youtube')
    video = Video(
        user_id=current_user.id,
        content_type=content_type,
        title=doc_title,
        original_filename=file.filename,
        file_size_bytes=file_size_bytes,
        status="pending",
        progress_percent=0.0,
        chunk_count=0,
        tags=[],
    )
    db.add(video)
    db.flush()

    # Save file to storage
    import io
    file_stream = io.BytesIO(file_content)
    document_path = storage_service.save_document(
        current_user.id, video.id, file_stream, file.filename
    )
    video.document_file_path = document_path
    db.commit()

    # Track storage usage for uploaded document
    try:
        upload_tracker = UsageTracker(db)
        upload_tracker.track_storage_usage(
            current_user.id,
            file_size_bytes / (1024 * 1024),
            reason="document_uploaded",
            video_id=video.id,
            extra_metadata={"content_type": content_type, "filename": file.filename},
        )
    except Exception as e:
        logger.warning(f"Failed to track storage for document upload {video.id}: {e}")

    # Dispatch processing task
    from app.tasks.document_tasks import process_document_pipeline

    process_document_pipeline.delay(str(video.id))

    logger.info(
        f"[Content Upload] user={current_user.id} content_id={video.id} "
        f"type={content_type} file={file.filename} size={file_size_bytes}"
    )

    # Warn for large files that will take a while to process
    warning = None
    file_size_mb = file_size_bytes / (1024 * 1024)
    if file_size_mb > 20:
        warning = f"Large document ({file_size_mb:.0f} MB). Processing may take 30+ minutes."

    return ContentUploadResponse(
        content_id=video.id,
        status=video.status,
        content_type=content_type,
        title=doc_title,
        original_filename=file.filename,
        file_size_bytes=file_size_bytes,
        message="Document upload started. Processing will begin shortly.",
        warning=warning,
    )


@router.get("", response_model=ContentList)
async def list_content(
    request: Request,
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    search: Optional[str] = Query(None, description="Search by title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents (non-YouTube content) for the current user."""
    query = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.content_type != "youtube",
        Video.is_deleted == False,
    )

    if content_type:
        query = query.filter(Video.content_type == content_type)
    if status:
        if status == "processing":
            processing_statuses = [
                "pending", "extracting", "extracted", "chunking", "enriching", "indexing",
            ]
            query = query.filter(Video.status.in_(processing_statuses))
        else:
            query = query.filter(Video.status == status)
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))

    total = query.count()
    items = query.order_by(Video.created_at.desc()).offset(skip).limit(limit).all()

    return ContentList(
        total=total,
        items=[_video_to_content_detail(v, db) for v in items],
    )


@router.get("/{content_id}", response_model=ContentDetail)
async def get_content(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific content item."""
    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    return _video_to_content_detail(video, db)


@router.get("/{content_id}/status", response_model=ContentStatusUpdate)
async def get_content_status(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get processing status for a content item (lightweight polling endpoint)."""
    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    progress = _extract_enrichment_progress(video)

    return ContentStatusUpdate(
        id=video.id,
        status=video.status,
        progress_percent=video.progress_percent,
        error_message=video.error_message,
        chunk_count=video.chunk_count,
        completed_at=video.completed_at,
        chunks_enriched=progress["chunks_enriched"],
        total_chunks=progress["total_chunks"],
        eta_seconds=progress["eta_seconds"],
        is_active=progress["is_active"],
        activity_status=progress["activity_status"],
        seconds_since_update=progress["seconds_since_update"],
        processing_rate=progress["processing_rate"],
    )


@router.get("/{content_id}/file")
async def get_content_file(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Serve the PDF preview for the document viewer.

    Returns the preview.pdf (converted or copied during processing).
    Falls back to the original file for PDFs if no preview exists.
    """
    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    # Try preview PDF first
    preview_path = storage_service.get_preview_path(current_user.id, content_id)
    if preview_path:
        return FileResponse(
            preview_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    # Fall back to original file for PDFs
    if video.content_type == "pdf" and video.document_file_path:
        from pathlib import Path as _Path

        if _Path(video.document_file_path).exists():
            return FileResponse(
                video.document_file_path,
                media_type="application/pdf",
                headers={"Content-Disposition": "inline"},
            )

    raise HTTPException(
        status_code=404,
        detail="Document preview not available. The document may still be processing.",
    )


@router.delete("/{content_id}", response_model=ContentDeleteResponse)
async def delete_content(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a content item (soft delete + cleanup)."""
    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    # Calculate storage savings
    savings_mb = 0.0
    if video.file_size_bytes:
        savings_mb += video.file_size_bytes / (1024 * 1024)

    # Delete from vector store
    from app.services.vector_store import vector_store_service
    try:
        vector_store_service.delete_video(video.id)
    except Exception as e:
        logger.warning(f"Failed to delete vectors for content {content_id}: {e}")

    # Delete document files from storage
    try:
        storage_service.delete_document(current_user.id, video.id)
    except Exception as e:
        logger.warning(f"Failed to delete document files for content {content_id}: {e}")

    # Delete chunks from database
    chunk_count = db.query(Chunk).filter(Chunk.video_id == content_id).delete()

    # Soft delete
    from datetime import datetime
    video.is_deleted = True
    video.deleted_at = datetime.utcnow()
    db.commit()

    # Credit storage back
    try:
        usage_tracker = UsageTracker(db)
        usage_tracker.track_storage_usage(current_user.id, -savings_mb, "document_delete", video_id=content_id)
    except Exception as e:
        logger.warning(f"Failed to credit storage for content {content_id}: {e}")

    logger.info(
        f"[Content Delete] user={current_user.id} content_id={content_id} "
        f"chunks_deleted={chunk_count} savings_mb={savings_mb:.2f}"
    )

    return ContentDeleteResponse(
        deleted_count=1,
        total_savings_mb=round(savings_mb, 2),
        message="Document deleted successfully",
    )


@router.post("/{content_id}/reprocess")
@limiter.limit("5/minute")
async def reprocess_content(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocess a failed or canceled document."""
    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    if video.status not in ("failed", "canceled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reprocess content with status '{video.status}'. Only failed or canceled content can be reprocessed.",
        )

    # Reset status
    video.status = "pending"
    video.progress_percent = 0.0
    video.error_message = None
    # Clear stale enrichment metadata from previous run
    if video.source_metadata:
        for key in ("chunks_enriched", "total_chunks", "eta_seconds", "last_progress_at", "enrichment_started_at"):
            video.source_metadata.pop(key, None)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(video, "source_metadata")
    db.commit()

    # Clear Redis dedup lock from previous failed/crashed task
    try:
        import redis as _redis
        from app.core.celery_app import celery_app
        redis_client = _redis.from_url(celery_app.conf.broker_url)
        redis_client.delete(f"doc_pipeline_lock:{content_id}")
    except Exception as e:
        logger.warning(f"[Content Reprocess] Failed to clear dedup lock for {content_id}: {e}")

    # Re-dispatch processing task
    from app.tasks.document_tasks import process_document_pipeline

    process_document_pipeline.delay(str(video.id))

    logger.info(
        f"[Content Reprocess] user={current_user.id} content_id={content_id} "
        f"type={video.content_type}"
    )

    return {"status": "pending", "message": "Document reprocessing started"}


@router.post("/{content_id}/cancel")
async def cancel_content(
    content_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a processing document."""
    from app.services.job_cancellation import is_cancelable, cancel_video_processing, CleanupOption

    video = (
        db.query(Video)
        .filter(
            Video.id == content_id,
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Content not found")

    if not is_cancelable(video):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel - status is '{video.status}'",
        )

    result = cancel_video_processing(db, video, CleanupOption.KEEP_VIDEO)

    logger.info(
        f"[Content Cancel] user={current_user.id} content_id={content_id} "
        f"prev_status={result.previous_status} new_status={result.new_status}"
    )

    return {
        "content_id": str(result.video_id),
        "previous_status": result.previous_status,
        "new_status": result.new_status,
        "message": "Document processing canceled",
    }


@router.post("/delete-bulk", response_model=ContentDeleteResponse)
async def delete_content_bulk(
    content_ids: List[UUID],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete multiple content items."""
    videos = (
        db.query(Video)
        .filter(
            Video.id.in_(content_ids),
            Video.user_id == current_user.id,
            Video.is_deleted == False,
        )
        .all()
    )

    if not videos:
        raise HTTPException(status_code=404, detail="No content found to delete")

    total_savings = 0.0
    deleted_count = 0

    for video in videos:
        savings_mb = (video.file_size_bytes or 0) / (1024 * 1024)

        # Delete vectors
        from app.services.vector_store import vector_store_service
        try:
            vector_store_service.delete_video(video.id)
        except Exception:
            pass

        # Delete document files
        try:
            storage_service.delete_document(current_user.id, video.id)
        except Exception:
            pass

        # Delete chunks
        db.query(Chunk).filter(Chunk.video_id == video.id).delete()

        # Soft delete
        from datetime import datetime
        video.is_deleted = True
        video.deleted_at = datetime.utcnow()

        total_savings += savings_mb
        deleted_count += 1

    db.commit()

    # Credit storage back for deleted documents
    if total_savings > 0:
        try:
            usage_tracker = UsageTracker(db)
            for video in videos:
                savings_mb = (video.file_size_bytes or 0) / (1024 * 1024)
                if savings_mb > 0:
                    usage_tracker.track_storage_usage(
                        current_user.id,
                        -savings_mb,
                        reason="document_delete",
                        video_id=video.id,
                    )
        except Exception as e:
            logger.warning(f"Failed to credit storage for bulk delete: {e}")

    return ContentDeleteResponse(
        deleted_count=deleted_count,
        total_savings_mb=round(total_savings, 2),
        message=f"{deleted_count} document(s) deleted successfully",
    )
