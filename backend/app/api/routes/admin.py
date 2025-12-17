"""
Admin API endpoints for user management and system monitoring.

All routes require admin (superuser) authentication.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, and_, or_
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
    UsageEvent,
    Chunk,
)
from app.schemas import (
    UserSummary,
    UserListResponse,
    UserDetail,
    UserDetailMetrics,
    UserCostBreakdown,
    UserUpdateRequest,
    QuotaOverrideRequest,
    DashboardResponse,
    SystemStats,
    UserEngagementStats,
)
from app.services.usage_tracker import UsageTracker

router = APIRouter()


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
        Video.user_id == user_id,
        Video.is_deleted == False  # noqa: E712
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
        .scalar() or 0
    ) / 60.0

    # Collection metrics
    collections_total = db.query(Collection).filter(Collection.user_id == user_id).count()
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
        db.query(Message)
        .join(Conversation)
        .filter(Conversation.user_id == user_id)
    )
    messages_total = messages_query.count()
    messages_sent = messages_query.filter(Message.role == "user").count()
    messages_received = messages_query.filter(Message.role == "assistant").count()

    # Token metrics
    token_stats = (
        messages_query.with_entities(
            func.sum(Message.input_tokens).label("input"),
            func.sum(Message.output_tokens).label("output"),
        )
        .first()
    )
    input_tokens = int(token_stats.input or 0)
    output_tokens = int(token_stats.output or 0)
    total_tokens = input_tokens + output_tokens

    # Storage metrics
    audio_mb = (
        videos_query.with_entities(func.sum(Video.audio_file_size_mb)).scalar() or 0.0
    )

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
        storage_mb=round(audio_mb, 2),
        audio_mb=round(audio_mb, 2),
        transcript_mb=0.0,  # TODO: Calculate from transcript files
        quota_videos_used=quota.videos_used if quota else 0,
        quota_videos_limit=quota.videos_limit if quota else 0,
        quota_minutes_used=quota.minutes_used if quota else 0.0,
        quota_minutes_limit=quota.minutes_limit if quota else 0.0,
        quota_messages_used=quota.messages_used if quota else 0,
        quota_messages_limit=quota.messages_limit if quota else 0,
        quota_storage_used=quota.storage_mb_used if quota else 0.0,
        quota_storage_limit=quota.storage_mb_limit if quota else 0.0,
    )


def calculate_user_costs(db: Session, user_id: UUID, metrics: UserDetailMetrics) -> UserCostBreakdown:
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
    llm_cost = (
        (metrics.input_tokens / 1_000_000) * LLM_INPUT_COST_PER_1M +
        (metrics.output_tokens / 1_000_000) * LLM_OUTPUT_COST_PER_1M
    )

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
    profit_margin = (net_profit / subscription_revenue * 100) if subscription_revenue > 0 else -100.0

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

    # New users this month
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_users_this_month = (
        db.query(User).filter(User.created_at >= month_start).count()
    )

    # Subscription tier breakdown
    tier_counts = (
        db.query(User.subscription_tier, func.count(User.id))
        .group_by(User.subscription_tier)
        .all()
    )
    tier_dict = {tier: count for tier, count in tier_counts}

    # Content stats
    total_videos = db.query(Video).filter(Video.is_deleted == False).count()  # noqa: E712
    total_videos_completed = (
        db.query(Video)
        .filter(Video.is_deleted == False, Video.status == "completed")  # noqa: E712
        .count()
    )
    total_videos_processing = (
        db.query(Video)
        .filter(Video.is_deleted == False, Video.status.notin_(["completed", "failed"]))  # noqa: E712
        .count()
    )
    total_videos_failed = (
        db.query(Video)
        .filter(Video.is_deleted == False, Video.status == "failed")  # noqa: E712
        .count()
    )

    total_conversations = db.query(Conversation).count()
    total_messages = db.query(Message).count()
    total_collections = db.query(Collection).count()

    # Usage stats
    total_minutes = (
        db.query(func.sum(Video.duration_seconds))
        .filter(Video.is_deleted == False, Video.status == "completed")  # noqa: E712
        .scalar() or 0
    ) / 60.0

    total_tokens = (
        db.query(func.sum(Message.input_tokens) + func.sum(Message.output_tokens))
        .scalar() or 0
    )

    total_storage_mb = (
        db.query(func.sum(Video.audio_file_size_mb))
        .filter(Video.is_deleted == False)  # noqa: E712
        .scalar() or 0.0
    )

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
        new_users_this_month=new_users_this_month,
        churned_users_this_month=0,  # TODO: Track churned users
        users_free=tier_dict.get("free", 0),
        users_starter=tier_dict.get("starter", 0),
        users_pro=tier_dict.get("pro", 0),
        users_business=tier_dict.get("business", 0),
        users_enterprise=tier_dict.get("enterprise", 0),
        total_videos=total_videos,
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
    status: Optional[str] = Query(None, description="Filter by account status: active, inactive"),
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
        video_count = db.query(Video).filter(
            Video.user_id == user.id,
            Video.is_deleted == False  # noqa: E712
        ).count()

        collection_count = db.query(Collection).filter(Collection.user_id == user.id).count()

        conversation_count = db.query(Conversation).filter(Conversation.user_id == user.id).count()

        message_count = (
            db.query(func.count(Message.id))
            .join(Conversation)
            .filter(Conversation.user_id == user.id)
            .scalar() or 0
        )

        token_sum = (
            db.query(func.sum(Message.input_tokens) + func.sum(Message.output_tokens))
            .join(Conversation)
            .filter(Conversation.user_id == user.id)
            .scalar() or 0
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
                clerk_user_id=user.clerk_user_id,
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
        clerk_user_id=user.clerk_user_id,
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
        clerk_user_id=user.clerk_user_id,
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
        clerk_user_id=user.clerk_user_id,
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
