"""
Admin API endpoints for user management and system monitoring.

All routes require admin (superuser) authentication.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.admin_auth import get_admin_user
from app.db.base import get_db
from app.models import (
    User,
    Video,
    Collection,
    Conversation,
    Message,
    UserQuota,
    Chunk,
    MessageChunkReference,
    AdminAuditLog,
)
from app.models.subscription import Subscription
from app.schemas import (
    AdminCollectionOverview,
    AdminVideoItem,
    AdminVideoOverview,
    ContentOverviewResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessage,
    ConversationSummary,
    DashboardResponse,
    QASource,
    QAFeedItem,
    QAFeedResponse,
    AuditLogItem,
    AuditLogResponse,
    QuotaOverrideRequest,
    QuotaRecalculateResponse,
    SystemStats,
    UserCostBreakdown,
    UserDeleteResponse,
    UserDetail,
    UserDetailMetrics,
    UserEngagementStats,
    UserListResponse,
    UserSummary,
    UserUpdateRequest,
    AbuseAlertResponse,
)
from app.services.usage_tracker import UsageTracker
from app.services.storage_calculator import StorageCalculator
from app.services.storage import storage_service

router = APIRouter()


def _estimate_response_cost(
    input_tokens: Optional[int], output_tokens: Optional[int]
) -> Optional[float]:
    """
    Estimate LLM cost for a single answer using the same pricing assumptions
    used elsewhere in the admin panel.
    """
    if not input_tokens and not output_tokens:
        return None

    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0

    llm_input_cost = (input_tokens / 1_000_000) * 3.0
    llm_output_cost = (output_tokens / 1_000_000) * 15.0
    total = llm_input_cost + llm_output_cost
    return round(total, 4)


def _safe_snippet(text: Optional[str], max_length: int = 220) -> Optional[str]:
    """Return a short, display-friendly snippet."""
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _extract_flags(metadata: Optional[dict]) -> List[str]:
    """Collect any moderation/safety flags stored on a message."""
    flags: List[str] = []
    if not isinstance(metadata, dict):
        return flags

    for key in ("flags", "moderation_flags", "safety_flags"):
        value = metadata.get(key)
        if isinstance(value, list):
            flags.extend(str(v) for v in value)
        elif isinstance(value, str):
            flags.append(value)

    if metadata.get("had_error"):
        flags.append("error")
    if metadata.get("pii_detected"):
        flags.append("pii_detected")

    return sorted(set(flags))


def _load_sources(
    db: Session, message_id: UUID, limit: int = 5
) -> List[QASource]:
    """Load a limited set of chunk references for an assistant message."""
    refs = (
        db.query(MessageChunkReference, Chunk, Video)
        .join(Chunk, MessageChunkReference.chunk_id == Chunk.id)
        .join(Video, Chunk.video_id == Video.id)
        .filter(MessageChunkReference.message_id == message_id)
        .order_by(MessageChunkReference.rank.asc())
        .limit(limit)
        .all()
    )

    sources: List[QASource] = []
    for ref, chunk, video in refs:
        sources.append(
            QASource(
                chunk_id=chunk.id,
                video_id=chunk.video_id,
                video_title=video.title,
                score=ref.relevance_score,
                snippet=_safe_snippet(chunk.text),
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
            )
        )
    return sources


def calculate_user_metrics(db: Session, user_id: UUID) -> UserDetailMetrics:
    """
    Calculate detailed metrics for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        UserDetailMetrics with all calculated metrics
    """
    # Video metrics
    videos_query = db.query(Video).filter(
        Video.user_id == user_id, Video.is_deleted.is_(False)  # noqa: E712
    )
    videos_total = videos_query.count()
    videos_completed = videos_query.filter(Video.status == "completed").count()
    videos_processing = videos_query.filter(
        Video.status.notin_(["completed", "failed"])
    ).count()
    videos_failed = videos_query.filter(Video.status == "failed").count()

    total_minutes = (
        videos_query.with_entities(func.sum(Video.duration_seconds))
        .filter(Video.status == "completed")
        .scalar()
        or 0
    ) / 60.0

    # Collection metrics
    collections_total = (
        db.query(Collection).filter(Collection.user_id == user_id).count()
    )
    collections_with_videos = (
        db.query(Collection)
        .join(Collection.collection_videos)
        .filter(Collection.user_id == user_id)
        .distinct()
        .count()
    )

    # Conversation metrics
    conversations_query = db.query(Conversation).filter(Conversation.user_id == user_id)
    conversations_total = conversations_query.count()
    conversations_active = conversations_query.filter(
        Conversation.last_message_at >= datetime.utcnow() - timedelta(days=30)
    ).count()

    # Message metrics
    messages_query = (
        db.query(Message).join(Conversation).filter(Conversation.user_id == user_id)
    )
    messages_sent = messages_query.filter(Message.role == "user").count()
    messages_received = messages_query.filter(Message.role == "assistant").count()

    # Token metrics
    token_stats = messages_query.with_entities(
        func.sum(Message.input_tokens).label("input"),
        func.sum(Message.output_tokens).label("output"),
    ).first()
    input_tokens = int(token_stats.input or 0)
    output_tokens = int(token_stats.output or 0)
    total_tokens = input_tokens + output_tokens

    # Comprehensive storage metrics (audio files + database + vectors)
    # Audio from videos table (for backwards compatibility display)
    audio_mb = (
        videos_query.with_entities(func.sum(Video.audio_file_size_mb)).scalar() or 0.0
    )

    # Calculate comprehensive storage using StorageCalculator
    calculator = StorageCalculator(db)
    storage_breakdown = calculator.calculate_total_storage_mb(user_id)

    # Disk usage from storage service (audio + transcript files)
    disk_usage_mb = storage_service.get_storage_usage(user_id)

    # Total storage = disk files + database text + vectors
    total_storage_mb = disk_usage_mb + storage_breakdown["database_mb"] + storage_breakdown["vector_mb"]

    # Get user quota
    quota = db.query(UserQuota).filter(UserQuota.user_id == user_id).first()

    return UserDetailMetrics(
        videos_total=videos_total,
        videos_completed=videos_completed,
        videos_processing=videos_processing,
        videos_failed=videos_failed,
        total_transcription_minutes=round(total_minutes, 2),
        collections_total=collections_total,
        collections_with_videos=collections_with_videos,
        conversations_total=conversations_total,
        conversations_active=conversations_active,
        messages_sent=messages_sent,
        messages_received=messages_received,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        storage_mb=round(total_storage_mb, 2),  # Now includes all storage
        audio_mb=round(audio_mb, 2),
        transcript_mb=round(storage_breakdown["database_mb"], 2),  # DB text storage
        quota_videos_used=quota.videos_used if quota else 0,
        quota_videos_limit=quota.videos_limit if quota else 0,
        quota_minutes_used=quota.minutes_used if quota else 0.0,
        quota_minutes_limit=quota.minutes_limit if quota else 0.0,
        quota_messages_used=quota.messages_used if quota else 0,
        quota_messages_limit=quota.messages_limit if quota else 0,
        quota_storage_used=quota.storage_mb_used if quota else 0.0,
        quota_storage_limit=quota.storage_mb_limit if quota else 0.0,
    )


def calculate_user_costs(
    db: Session, user_id: UUID, metrics: UserDetailMetrics
) -> UserCostBreakdown:
    """
    Calculate cost breakdown for a user based on usage.

    Pricing assumptions (can be configured later):
    - Whisper: $0.006/minute
    - Embeddings: $0.02/1M tokens
    - LLM (Claude): $3/1M input, $15/1M output
    - Storage: $0.02/GB/month

    Args:
        db: Database session
        user_id: User ID
        metrics: User metrics

    Returns:
        UserCostBreakdown with cost estimates
    """
    # Pricing constants (should move to config later)
    WHISPER_COST_PER_MINUTE = 0.006
    EMBEDDING_COST_PER_1M_TOKENS = 0.02
    LLM_INPUT_COST_PER_1M = 3.0
    LLM_OUTPUT_COST_PER_1M = 15.0
    STORAGE_COST_PER_GB_MONTH = 0.02

    # Calculate costs
    transcription_cost = metrics.total_transcription_minutes * WHISPER_COST_PER_MINUTE

    # Estimate embedding tokens (avg 256 tokens per chunk)
    chunk_count = db.query(Chunk).filter(Chunk.user_id == user_id).count()
    embedding_tokens = chunk_count * 256
    embedding_cost = (embedding_tokens / 1_000_000) * EMBEDDING_COST_PER_1M_TOKENS

    # LLM costs
    llm_cost = (metrics.input_tokens / 1_000_000) * LLM_INPUT_COST_PER_1M + (
        metrics.output_tokens / 1_000_000
    ) * LLM_OUTPUT_COST_PER_1M

    # Storage cost (monthly)
    storage_gb = metrics.storage_mb / 1024.0
    storage_cost = storage_gb * STORAGE_COST_PER_GB_MONTH

    total_cost = transcription_cost + embedding_cost + llm_cost + storage_cost

    # Revenue calculation based on subscription tier
    user = db.query(User).filter(User.id == user_id).first()
    tier_revenue = {
        "free": 0.0,
        "starter": 9.0,
        "pro": 29.0,
        "business": 79.0,
        "enterprise": 299.0,
    }
    subscription_revenue = tier_revenue.get(user.subscription_tier.lower(), 0.0)

    net_profit = subscription_revenue - total_cost
    profit_margin = (
        (net_profit / subscription_revenue * 100)
        if subscription_revenue > 0
        else -100.0
    )

    return UserCostBreakdown(
        transcription_cost=round(transcription_cost, 4),
        embedding_cost=round(embedding_cost, 4),
        llm_cost=round(llm_cost, 4),
        storage_cost=round(storage_cost, 4),
        total_cost=round(total_cost, 4),
        subscription_revenue=subscription_revenue,
        net_profit=round(net_profit, 4),
        profit_margin=round(profit_margin, 2),
        transcription_minutes=round(metrics.total_transcription_minutes, 2),
        embedding_tokens=embedding_tokens,
        llm_input_tokens=metrics.input_tokens,
        llm_output_tokens=metrics.output_tokens,
        storage_gb=round(storage_gb, 4),
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_admin_dashboard(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Get system-wide dashboard statistics.

    Requires admin authentication.
    """
    # User stats
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712
    inactive_users = total_users - active_users

    # New users this month
    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    new_users_this_month = db.query(User).filter(User.created_at >= month_start).count()

    # Subscription tier breakdown
    tier_counts = (
        db.query(User.subscription_tier, func.count(User.id))
        .group_by(User.subscription_tier)
        .all()
    )
    tier_dict = {tier: count for tier, count in tier_counts}

    # Content stats
    total_videos = db.query(Video).filter(Video.is_deleted.is_(False)).count()
    total_videos_completed = (
        db.query(Video)
        .filter(Video.is_deleted.is_(False), Video.status == "completed")
        .count()
    )
    total_videos_processing = (
        db.query(Video)
        .filter(
            Video.is_deleted.is_(False), Video.status.notin_(["completed", "failed"])
        )
        .count()
    )
    total_videos_failed = (
        db.query(Video)
        .filter(Video.is_deleted.is_(False), Video.status == "failed")  # noqa: E712
        .count()
    )

    total_conversations = db.query(Conversation).count()
    total_messages = db.query(Message).count()
    total_collections = db.query(Collection).count()

    # Usage stats
    total_minutes = (
        db.query(func.sum(Video.duration_seconds))
        .filter(Video.is_deleted.is_(False), Video.status == "completed")  # noqa: E712
        .scalar()
        or 0
    ) / 60.0

    total_tokens = (
        db.query(
            func.sum(Message.input_tokens) + func.sum(Message.output_tokens)
        ).scalar()
        or 0
    )

    # Calculate comprehensive storage across all users
    # Audio files from videos table (quick count)
    audio_storage_mb = (
        db.query(func.sum(Video.audio_file_size_mb))
        .filter(Video.is_deleted.is_(False))  # noqa: E712
        .scalar()
        or 0.0
    )

    # Estimate total database + vector storage system-wide
    # For dashboard performance, we use audio_mb as base and estimate overhead
    # More accurate per-user calculation is done in calculate_user_metrics
    # Estimated overhead: ~50% for database text + ~30% for vectors
    estimated_overhead_factor = 1.8
    total_storage_mb = float(audio_storage_mb) * estimated_overhead_factor

    # Engagement stats
    week_ago = datetime.utcnow() - timedelta(days=7)
    two_weeks_ago = datetime.utcnow() - timedelta(days=14)
    month_ago = datetime.utcnow() - timedelta(days=30)
    three_months_ago = datetime.utcnow() - timedelta(days=90)

    # Get users with their last activity
    users_with_activity = (
        db.query(User.id, func.max(Message.created_at).label("last_activity"))
        .outerjoin(Conversation, Conversation.user_id == User.id)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(User.id)
        .subquery()
    )

    active_count = (
        db.query(users_with_activity)
        .filter(users_with_activity.c.last_activity >= week_ago)
        .count()
    )

    at_risk_count = (
        db.query(users_with_activity)
        .filter(
            users_with_activity.c.last_activity < two_weeks_ago,
            users_with_activity.c.last_activity >= month_ago,
        )
        .count()
    )

    churning_count = (
        db.query(users_with_activity)
        .filter(
            users_with_activity.c.last_activity < month_ago,
            users_with_activity.c.last_activity >= three_months_ago,
        )
        .count()
    )

    dormant_count = (
        db.query(users_with_activity)
        .filter(
            or_(
                users_with_activity.c.last_activity < three_months_ago,
                users_with_activity.c.last_activity.is_(None),
            )
        )
        .count()
    )

    system_stats = SystemStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        new_users_this_month=new_users_this_month,
        churned_users_this_month=0,  # TODO: Track churned users
        users_free=tier_dict.get("free", 0),
        users_starter=tier_dict.get("starter", 0),
        users_pro=tier_dict.get("pro", 0),
        users_business=tier_dict.get("business", 0),
        users_enterprise=tier_dict.get("enterprise", 0),
        users_by_tier=tier_dict,
        total_videos=total_videos,
        videos_completed=total_videos_completed,
        videos_processing=total_videos_processing,
        videos_failed=total_videos_failed,
        total_videos_completed=total_videos_completed,
        total_videos_processing=total_videos_processing,
        total_videos_failed=total_videos_failed,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_collections=total_collections,
        total_transcription_minutes=round(total_minutes, 2),
        total_tokens_used=int(total_tokens),
        total_storage_gb=round(total_storage_mb / 1024.0, 2),
        total_cost_this_month=0.0,  # TODO: Calculate from usage events
        total_revenue_this_month=0.0,  # TODO: Calculate from subscriptions
        net_profit_this_month=0.0,  # TODO: Calculate
    )

    engagement_stats = UserEngagementStats(
        active_users=active_count,
        at_risk_users=at_risk_count,
        churning_users=churning_count,
        dormant_users=dormant_count,
    )

    return DashboardResponse(
        system_stats=system_stats,
        engagement_stats=engagement_stats,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by email or name"),
    tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    status: Optional[str] = Query(
        None, description="Filter by account status: active, inactive"
    ),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    List all users with summary metrics.

    Supports pagination, search, and filtering.
    """
    # Base query
    query = db.query(User)

    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
            )
        )

    if tier:
        query = query.filter(User.subscription_tier == tier)

    if status == "active":
        query = query.filter(User.is_active == True)  # noqa: E712
    elif status == "inactive":
        query = query.filter(User.is_active == False)  # noqa: E712

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    # Build user summaries with metrics
    user_summaries = []
    for user in users:
        # Get basic aggregates
        video_count = (
            db.query(Video)
            .filter(Video.user_id == user.id, Video.is_deleted.is_(False))  # noqa: E712
            .count()
        )

        collection_count = (
            db.query(Collection).filter(Collection.user_id == user.id).count()
        )

        conversation_count = (
            db.query(Conversation).filter(Conversation.user_id == user.id).count()
        )

        message_count = (
            db.query(func.count(Message.id))
            .join(Conversation)
            .filter(Conversation.user_id == user.id)
            .scalar()
            or 0
        )

        token_sum = (
            db.query(func.sum(Message.input_tokens) + func.sum(Message.output_tokens))
            .join(Conversation)
            .filter(Conversation.user_id == user.id)
            .scalar()
            or 0
        )

        # Get quota for storage
        quota = db.query(UserQuota).filter(UserQuota.user_id == user.id).first()
        storage_mb = quota.storage_mb_used if quota else 0.0

        # Get last activity
        last_activity = (
            db.query(func.max(Message.created_at))
            .join(Conversation)
            .filter(Conversation.user_id == user.id)
            .scalar()
        )

        # Calculate days
        days_since_signup = (datetime.utcnow() - user.created_at).days
        days_since_last_active = (
            (datetime.utcnow() - last_activity).days if last_activity else None
        )

        user_summaries.append(
            UserSummary(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                oauth_provider=user.oauth_provider,
                oauth_provider_id=user.oauth_provider_id,
                subscription_tier=user.subscription_tier,
                subscription_status=user.subscription_status,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                video_count=video_count,
                collection_count=collection_count,
                conversation_count=conversation_count,
                total_messages=int(message_count),
                total_tokens_used=int(token_sum),
                storage_mb_used=round(storage_mb, 2),
                last_active_at=last_activity,
                days_since_signup=days_since_signup,
                days_since_last_active=days_since_last_active,
            )
        )

    return UserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        users=user_summaries,
    )


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Get detailed information about a specific user.

    Includes full metrics and cost breakdown.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Calculate metrics
    metrics = calculate_user_metrics(db, user_id)

    # Calculate costs
    costs = calculate_user_costs(db, user_id, metrics)

    return UserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        oauth_provider=user.oauth_provider,
                oauth_provider_id=user.oauth_provider_id,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        stripe_customer_id=user.stripe_customer_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        metrics=metrics,
        costs=costs,
        admin_notes_count=0,  # TODO: Implement admin notes
    )


@router.patch("/users/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: UUID,
    update_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Update user account settings.

    Admin only. Allows changing subscription tier, status, and admin privileges.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apply updates
    if update_data.subscription_tier is not None:
        user.subscription_tier = update_data.subscription_tier

    if update_data.subscription_status is not None:
        user.subscription_status = update_data.subscription_status

    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    if update_data.is_superuser is not None:
        user.is_superuser = update_data.is_superuser

    db.commit()
    db.refresh(user)

    # Return updated user detail
    metrics = calculate_user_metrics(db, user_id)
    costs = calculate_user_costs(db, user_id, metrics)

    return UserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        oauth_provider=user.oauth_provider,
                oauth_provider_id=user.oauth_provider_id,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        stripe_customer_id=user.stripe_customer_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        metrics=metrics,
        costs=costs,
        admin_notes_count=0,
    )


@router.patch("/users/{user_id}/quota", response_model=UserDetail)
async def override_user_quota(
    user_id: UUID,
    quota_data: QuotaOverrideRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Manually override user quota limits.

    Admin only. Allows setting custom quota limits for specific users.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get or create quota
    quota = db.query(UserQuota).filter(UserQuota.user_id == user_id).first()
    if not quota:
        quota = UsageTracker(db)._create_initial_quota(user_id, user.subscription_tier)
        db.add(quota)

    # Apply overrides
    if quota_data.videos_limit is not None:
        quota.videos_limit = quota_data.videos_limit

    if quota_data.minutes_limit is not None:
        quota.minutes_limit = quota_data.minutes_limit

    if quota_data.messages_limit is not None:
        quota.messages_limit = quota_data.messages_limit

    if quota_data.storage_mb_limit is not None:
        quota.storage_mb_limit = quota_data.storage_mb_limit

    db.commit()
    db.refresh(quota)

    # Return updated user detail
    metrics = calculate_user_metrics(db, user_id)
    costs = calculate_user_costs(db, user_id, metrics)

    return UserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        oauth_provider=user.oauth_provider,
                oauth_provider_id=user.oauth_provider_id,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        stripe_customer_id=user.stripe_customer_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        metrics=metrics,
        costs=costs,
        admin_notes_count=0,
    )


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Delete a user and all associated data.

    Admin only. Prevents self-deletion. Handles non-cascading foreign keys
    (subscriptions) before deleting user. Other tables with CASCADE constraints
    are automatically cleaned up.

    Returns count of deleted records by table.
    """
    # Prevent self-deletion
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account",
        )

    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    deleted_email = user.email
    deleted_records: Dict[str, int] = {}

    # Delete subscriptions first (no CASCADE constraint)
    subscription_count = (
        db.query(Subscription).filter(Subscription.user_id == user_id).delete()
    )
    deleted_records["subscriptions"] = subscription_count

    # Delete user_quotas (may not have CASCADE depending on setup)
    quota_count = db.query(UserQuota).filter(UserQuota.user_id == user_id).delete()
    deleted_records["user_quotas"] = quota_count

    # Delete user (cascades to: videos, conversations, collections, usage_events,
    # jobs, llm_usage_events, conversation_facts, conversation_insights)
    db.delete(user)
    db.commit()

    return UserDeleteResponse(
        success=True,
        message=f"Successfully deleted user {deleted_email} and all associated data",
        deleted_user_id=user_id,
        deleted_email=deleted_email,
        deleted_records=deleted_records,
    )


@router.post("/quotas/recalculate", response_model=QuotaRecalculateResponse)
async def recalculate_quotas(
    user_id: Optional[UUID] = Query(None, description="Recalculate for specific user only"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Recalculate quota usage from actual data.

    Fixes discrepancies between tracked quota and actual resource usage.
    Recalculates: storage_mb_used, videos_used, minutes_used.

    Use user_id parameter to recalculate for a single user, or omit to
    recalculate for all users.
    """
    from decimal import Decimal

    corrections: List[Dict] = []

    # Build query for quotas to update
    quota_query = db.query(UserQuota)
    if user_id:
        quota_query = quota_query.filter(UserQuota.user_id == user_id)

    quotas = quota_query.all()

    for quota in quotas:
        user = db.query(User).filter(User.id == quota.user_id).first()
        user_email = user.email if user else str(quota.user_id)

        # Recalculate comprehensive storage (disk + database + vectors)
        calculator = StorageCalculator(db)
        storage_breakdown = calculator.calculate_total_storage_mb(quota.user_id)
        disk_usage_mb = storage_service.get_storage_usage(quota.user_id)
        actual_storage = disk_usage_mb + storage_breakdown["database_mb"] + storage_breakdown["vector_mb"]

        # Allow small differences (< 0.1 MB) to avoid excessive corrections
        if abs(float(quota.storage_mb_used) - actual_storage) > 0.1:
            corrections.append({
                "user_id": str(quota.user_id),
                "user_email": user_email,
                "field": "storage_mb_used",
                "old_value": float(quota.storage_mb_used),
                "new_value": round(actual_storage, 3),
            })
            quota.storage_mb_used = Decimal(str(round(actual_storage, 3)))

        # Recalculate videos_used from active videos
        actual_videos = (
            db.query(func.count(Video.id))
            .filter(
                Video.user_id == quota.user_id,
                Video.is_deleted.is_(False),
                Video.status == "completed",
            )
            .scalar()
        ) or 0

        if quota.videos_used != actual_videos:
            corrections.append({
                "user_id": str(quota.user_id),
                "user_email": user_email,
                "field": "videos_used",
                "old_value": quota.videos_used,
                "new_value": actual_videos,
            })
            quota.videos_used = actual_videos

        # Recalculate minutes_used from completed videos
        actual_minutes = (
            db.query(func.coalesce(func.sum(Video.duration_seconds), 0))
            .filter(
                Video.user_id == quota.user_id,
                Video.is_deleted.is_(False),
                Video.status == "completed",
            )
            .scalar()
        ) or 0
        actual_minutes = actual_minutes / 60.0  # Convert to minutes

        if abs(float(quota.minutes_used) - actual_minutes) > 0.01:
            corrections.append({
                "user_id": str(quota.user_id),
                "user_email": user_email,
                "field": "minutes_used",
                "old_value": float(quota.minutes_used),
                "new_value": actual_minutes,
            })
            quota.minutes_used = Decimal(str(actual_minutes))

    db.commit()

    return QuotaRecalculateResponse(
        success=True,
        message=f"Recalculated quotas for {len(quotas)} user(s), made {len(corrections)} correction(s)",
        users_updated=len(quotas),
        corrections=corrections,
    )


@router.get("/qa-feed", response_model=QAFeedResponse)
async def get_qa_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation"),
    collection_id: Optional[UUID] = Query(None, description="Filter by collection"),
    search: Optional[str] = Query(None, description="Search question text"),
    start: Optional[datetime] = Query(None, description="Start datetime"),
    end: Optional[datetime] = Query(None, description="End datetime"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Return a paginated question/answer feed for admin monitoring.

    Read-only and scoped to admin users.
    """
    query = (
        db.query(Message)
        .join(Conversation)
        .join(User, Conversation.user_id == User.id)
        .filter(Message.role == "user")
    )

    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    if conversation_id:
        query = query.filter(Message.conversation_id == conversation_id)
    if collection_id:
        query = query.filter(Conversation.collection_id == collection_id)
    if start:
        query = query.filter(Message.created_at >= start)
    if end:
        query = query.filter(Message.created_at <= end)
    if search:
        query = query.filter(Message.content.ilike(f"%{search}%"))

    total = query.count()
    offset = (page - 1) * page_size

    questions = (
        query.order_by(Message.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items: List[QAFeedItem] = []
    for question in questions:
        answer = (
            db.query(Message)
            .filter(
                Message.conversation_id == question.conversation_id,
                Message.role == "assistant",
                Message.created_at >= question.created_at,
            )
            .order_by(Message.created_at.asc())
            .first()
        )

        response_latency_ms: Optional[float] = None
        cost_usd: Optional[float] = None
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        sources: List[QASource] = []
        answer_id: Optional[UUID] = None
        answered_at: Optional[datetime] = None
        flags: List[str] = []

        if answer:
            answer_id = answer.id
            answered_at = answer.created_at
            response_latency_ms = (
                answer.response_time_seconds * 1000
                if answer.response_time_seconds is not None
                else (answer.created_at - question.created_at).total_seconds() * 1000
            )
            input_tokens = answer.input_tokens
            output_tokens = answer.output_tokens
            cost_usd = _estimate_response_cost(input_tokens, output_tokens)
            sources = _load_sources(db, answer.id)
            flags = _extract_flags(answer.message_metadata)

        conversation = question.conversation
        user_email = getattr(conversation.user, "email", None)

        items.append(
            QAFeedItem(
                qa_id=answer_id or question.id,
                question_id=question.id,
                answer_id=answer_id,
                user_id=conversation.user_id,
                user_email=user_email,
                conversation_id=conversation.id,
                collection_id=conversation.collection_id,
                question=question.content,
                answer=answer.content if answer else None,
                asked_at=question.created_at,
                answered_at=answered_at,
                response_latency_ms=response_latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                flags=flags,
                sources=sources,
            )
        )

    return QAFeedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/audit/messages", response_model=AuditLogResponse)
async def list_audit_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str = Query("chat_message", description="Filter by audit event type"),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation"),
    role: Optional[str] = Query(None, description="Filter by message role"),
    has_flags: Optional[bool] = Query(None, description="Only entries with flags"),
    search: Optional[str] = Query(None, description="Search content"),
    start: Optional[datetime] = Query(None, description="Start datetime"),
    end: Optional[datetime] = Query(None, description="End datetime"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Return paginated audit log events for chat monitoring.
    """
    query = db.query(AdminAuditLog, User.email).outerjoin(User, AdminAuditLog.user_id == User.id)

    if event_type:
        query = query.filter(AdminAuditLog.event_type == event_type)
    if user_id:
        query = query.filter(AdminAuditLog.user_id == user_id)
    if conversation_id:
        query = query.filter(AdminAuditLog.conversation_id == conversation_id)
    if role:
        query = query.filter(AdminAuditLog.role == role)
    if start:
        query = query.filter(AdminAuditLog.created_at >= start)
    if end:
        query = query.filter(AdminAuditLog.created_at <= end)
    if search:
        query = query.filter(AdminAuditLog.content.ilike(f"%{search}%"))
    if has_flags is True:
        query = query.filter(
            AdminAuditLog.flags.isnot(None),
            func.cardinality(AdminAuditLog.flags) > 0,
        )
    elif has_flags is False:
        query = query.filter(
            or_(AdminAuditLog.flags.is_(None), func.cardinality(AdminAuditLog.flags) == 0)
        )

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items: List[AuditLogItem] = []
    for log, email in rows:
        items.append(
            AuditLogItem(
                id=log.id,
                event_type=log.event_type,
                user_id=log.user_id,
                user_email=email,
                conversation_id=log.conversation_id,
                message_id=log.message_id,
                role=log.role,
                content=log.content,
                token_count=log.token_count,
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                flags=log.flags or [],
                created_at=log.created_at,
                ip_hash=log.ip_hash,
                user_agent=log.user_agent,
                metadata=log.message_metadata or {},
            )
        )

    return AuditLogResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_admin_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    collection_id: Optional[UUID] = Query(None, description="Filter by collection"),
    search: Optional[str] = Query(None, description="Search conversation title"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    List conversations for admin review.
    """
    query = db.query(Conversation, User.email).join(
        User, Conversation.user_id == User.id
    )

    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    if collection_id:
        query = query.filter(Conversation.collection_id == collection_id)
    if search:
        query = query.filter(Conversation.title.ilike(f"%{search}%"))

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(Conversation.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    conversations: List[ConversationSummary] = []
    for conversation, email in rows:
        conversations.append(
            ConversationSummary(
                id=conversation.id,
                user_id=conversation.user_id,
                user_email=email,
                title=conversation.title,
                collection_id=conversation.collection_id,
                message_count=conversation.message_count,
                total_tokens=conversation.total_tokens_used or 0,
                started_at=conversation.created_at,
                last_message_at=conversation.last_message_at,
            )
        )

    return ConversationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        conversations=conversations,
    )


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationDetailResponse
)
async def get_admin_conversation_detail(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Return the full timeline for a conversation.
    """
    record = (
        db.query(Conversation, User.email)
        .join(User, Conversation.user_id == User.id)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    conversation, email = record
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    timeline: List[ConversationMessage] = []
    for msg in messages:
        sources = _load_sources(db, msg.id) if msg.role == "assistant" else []
        timeline.append(
            ConversationMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                input_tokens=msg.input_tokens,
                output_tokens=msg.output_tokens,
                response_time_seconds=msg.response_time_seconds,
                sources=sources,
            )
        )

    return ConversationDetailResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        user_email=email,
        title=conversation.title,
        collection_id=conversation.collection_id,
        message_count=conversation.message_count,
        total_tokens=conversation.total_tokens_used or 0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_message_at=conversation.last_message_at,
        messages=timeline,
    )


@router.get("/content/overview", response_model=ContentOverviewResponse)
async def get_content_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Lightweight content overview for admin dashboard.
    """
    base_videos = db.query(Video).filter(Video.is_deleted.is_(False))
    total_videos = base_videos.count()
    completed = base_videos.filter(Video.status == "completed").count()
    failed = base_videos.filter(Video.status == "failed").count()
    processing = base_videos.filter(
        Video.status.notin_(["completed", "failed"])
    ).count()
    queued = base_videos.filter(Video.status == "pending").count()

    recent_videos = (
        db.query(Video, User.email)
        .join(User, Video.user_id == User.id)
        .filter(Video.is_deleted.is_(False))
        .order_by(Video.created_at.desc())
        .limit(8)
        .all()
    )
    recent_items = [
        AdminVideoItem(
            id=video.id,
            title=video.title,
            user_email=email,
            status=video.status,
            progress_percent=video.progress_percent or 0.0,
            error_message=video.error_message,
            created_at=video.created_at,
            updated_at=video.updated_at,
        )
        for video, email in recent_videos
    ]

    total_collections = db.query(Collection).count()
    with_videos = (
        db.query(func.count(func.distinct(Collection.id)))
        .join(Collection.collection_videos)
        .scalar()
        or 0
    )
    empty = max(total_collections - with_videos, 0)
    recent_created_rows = (
        db.query(Collection.id)
        .order_by(Collection.created_at.desc())
        .limit(10)
        .all()
    )
    recent_created = [row.id for row in recent_created_rows]

    return ContentOverviewResponse(
        videos=AdminVideoOverview(
            total=total_videos,
            completed=completed,
            processing=processing,
            failed=failed,
            queued=queued,
            recent=recent_items,
        ),
        collections=AdminCollectionOverview(
            total=total_collections,
            with_videos=with_videos,
            empty=empty,
            recent_created=recent_created,
        ),
    )


@router.get("/alerts", response_model=AbuseAlertResponse)
async def get_admin_alerts(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Placeholder alerts endpoint for admin review.

    Returns an empty list until alerting is implemented.
    """
    return AbuseAlertResponse(total=0, alerts=[])


@router.get("/llm-usage")
async def get_llm_usage(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(default=50, ge=1, le=500, description="Max recent events to return"),
):
    """
    Get LLM usage statistics and cost tracking.

    Returns aggregated stats, per-user breakdown, and recent usage events.
    """
    from datetime import timedelta
    from app.models.llm_usage import LLMUsageEvent
    from app.schemas.admin import (
        LLMUsageResponse,
        LLMUsageStats,
        LLMUsageByUser,
        LLMUsageItem,
    )

    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()

    # Query usage events in the period
    events = (
        db.query(LLMUsageEvent)
        .filter(LLMUsageEvent.created_at >= period_start)
        .order_by(LLMUsageEvent.created_at.desc())
        .all()
    )

    if not events:
        return LLMUsageResponse(
            stats=LLMUsageStats(
                period_start=period_start,
                period_end=period_end,
            ),
            by_user=[],
            recent_events=[],
        )

    # Aggregate stats
    total_input = sum(e.input_tokens for e in events)
    total_output = sum(e.output_tokens for e in events)
    total_tokens = sum(e.total_tokens for e in events)
    total_cache_hit = sum(e.cache_hit_tokens for e in events)
    total_cache_miss = sum(e.cache_miss_tokens for e in events)
    total_cost = sum(float(e.cost_usd) for e in events)

    # Calculate cache savings (difference between full price and cached price)
    # Full price: $0.28/M, Cache price: $0.028/M, Savings: $0.252/M
    estimated_savings = (total_cache_hit / 1_000_000) * 0.252

    # Cache hit rate
    total_prompt_tokens = total_cache_hit + total_cache_miss
    cache_hit_rate = total_cache_hit / total_prompt_tokens if total_prompt_tokens > 0 else 0.0

    # Requests by model
    model_counts: Dict[str, int] = {}
    for e in events:
        model_counts[e.model] = model_counts.get(e.model, 0) + 1

    # Average response time
    response_times = [float(e.response_time_seconds) for e in events if e.response_time_seconds]
    avg_response_time = sum(response_times) / len(response_times) if response_times else None

    stats = LLMUsageStats(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        total_cache_hit_tokens=total_cache_hit,
        total_cache_miss_tokens=total_cache_miss,
        total_cost_usd=round(total_cost, 4),
        estimated_savings_usd=round(estimated_savings, 4),
        total_requests=len(events),
        requests_by_model=model_counts,
        avg_response_time_seconds=round(avg_response_time, 3) if avg_response_time else None,
        cache_hit_rate=round(cache_hit_rate, 4),
        period_start=period_start,
        period_end=period_end,
    )

    # Per-user breakdown
    user_usage: Dict[UUID, dict] = {}
    for e in events:
        if e.user_id not in user_usage:
            user_usage[e.user_id] = {
                "user_id": e.user_id,
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 0,
            }
        user_usage[e.user_id]["total_requests"] += 1
        user_usage[e.user_id]["total_tokens"] += e.total_tokens
        user_usage[e.user_id]["total_cost_usd"] += float(e.cost_usd)
        user_usage[e.user_id]["cache_hit_tokens"] += e.cache_hit_tokens
        user_usage[e.user_id]["cache_miss_tokens"] += e.cache_miss_tokens

    # Get user emails
    user_ids = list(user_usage.keys())
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_email_map = {u.id: u.email for u in users}

    by_user = []
    for uid, data in sorted(user_usage.items(), key=lambda x: x[1]["total_cost_usd"], reverse=True):
        total_prompt = data["cache_hit_tokens"] + data["cache_miss_tokens"]
        user_cache_rate = data["cache_hit_tokens"] / total_prompt if total_prompt > 0 else 0.0
        by_user.append(LLMUsageByUser(
            user_id=uid,
            user_email=user_email_map.get(uid),
            total_requests=data["total_requests"],
            total_tokens=data["total_tokens"],
            total_cost_usd=round(data["total_cost_usd"], 4),
            cache_hit_rate=round(user_cache_rate, 4),
        ))

    # Recent events
    recent_events = []
    for e in events[:limit]:
        recent_events.append(LLMUsageItem(
            id=e.id,
            user_id=e.user_id,
            user_email=user_email_map.get(e.user_id),
            conversation_id=e.conversation_id,
            model=e.model,
            provider=e.provider,
            input_tokens=e.input_tokens,
            output_tokens=e.output_tokens,
            total_tokens=e.total_tokens,
            cache_hit_tokens=e.cache_hit_tokens,
            cache_miss_tokens=e.cache_miss_tokens,
            cost_usd=float(e.cost_usd),
            response_time_seconds=float(e.response_time_seconds) if e.response_time_seconds else None,
            created_at=e.created_at,
        ))

    return LLMUsageResponse(
        stats=stats,
        by_user=by_user,
        recent_events=recent_events,
    )
