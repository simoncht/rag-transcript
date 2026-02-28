"""Content discovery architecture with registry patterns

Revision ID: 015_content_discovery
Revises: 014_add_video_summaries
Create Date: 2025-01-31

This migration adds:
- Content source type registry (extensible providers)
- Discovery sources (subscriptions/feeds)
- Discovered content (pending user action items)
- User interest profiles (for recommendations)
- Quota type registry (extensible quotas)
- Tier quota limits (per-tier defaults)
- User quota usage (period-based tracking)
- Notification event types (notification registry)
- User notification preferences
- Notifications and delivery tracking
- User settings for digest preferences
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # Content Source Types Registry
    # ========================================================================
    op.create_table(
        "content_source_types",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("provider_class", sa.String(200), nullable=True),
        sa.Column(
            "supported_content_types",
            postgresql.ARRAY(sa.Text),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("config_schema", postgresql.JSONB, nullable=True),
    )

    # Insert default content source types
    op.execute("""
        INSERT INTO content_source_types (id, display_name, provider_class, supported_content_types, is_active)
        VALUES
            ('youtube', 'YouTube', 'app.providers.youtube.YouTubeProvider', ARRAY['video'], true),
            ('youtube_search', 'YouTube Search', 'app.providers.youtube.YouTubeSearchProvider', ARRAY['video'], true)
    """)

    # ========================================================================
    # Discovery Sources (Subscriptions/Feeds)
    # ========================================================================
    op.create_table(
        "discovery_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Source identification
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_identifier", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("display_image_url", sa.String(500), nullable=True),
        # Configuration
        sa.Column(
            "config",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        # Classification
        sa.Column("is_explicit", sa.Boolean, default=True, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        # Tracking
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_frequency_hours", sa.Integer, default=24, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Unique constraint
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "source_identifier",
            name="uq_discovery_sources_user_source",
        ),
    )

    op.create_index(
        "idx_discovery_sources_check",
        "discovery_sources",
        ["is_active", "last_checked_at"],
    )

    # ========================================================================
    # Discovered Content (Pending User Action)
    # ========================================================================
    op.create_table(
        "discovered_content",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "discovery_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Content preview
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_identifier", sa.String(500), nullable=False),
        # Display data
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column(
            "preview_metadata",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        # Discovery context
        sa.Column("discovery_reason", sa.String(100), nullable=True),
        sa.Column(
            "discovery_context",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        # Status
        sa.Column("status", sa.String(50), default="pending", nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # Unique constraint
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "source_identifier",
            name="uq_discovered_content_user_source",
        ),
    )

    op.create_index(
        "idx_discovered_content_user_status",
        "discovered_content",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_discovered_content_expires",
        "discovered_content",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ========================================================================
    # User Interest Profiles
    # ========================================================================
    op.create_table(
        "user_interest_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Aggregated interests
        sa.Column(
            "topics",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "channels",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        # Profile metadata
        sa.Column("total_imports", sa.Integer, default=0, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ========================================================================
    # Quota Types Registry
    # ========================================================================
    op.create_table(
        "quota_types",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("reset_period", sa.String(50), nullable=False),
        sa.Column(
            "warning_thresholds",
            postgresql.ARRAY(sa.Integer),
            server_default=sa.text("ARRAY[50, 80, 95]"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )

    # Insert default quota types
    op.execute("""
        INSERT INTO quota_types (id, display_name, description, unit, reset_period, warning_thresholds, is_active)
        VALUES
            ('videos', 'Videos', 'Number of content items', 'count', 'none', ARRAY[50, 80, 95], true),
            ('minutes', 'Video Minutes', 'Total video duration', 'minutes', 'none', ARRAY[50, 80, 95], true),
            ('messages', 'Messages', 'Chat messages per month', 'count', 'monthly', ARRAY[50, 80, 95], true),
            ('storage', 'Storage', 'Total storage used', 'mb', 'none', ARRAY[50, 80, 95], true),
            ('youtube_searches', 'YouTube Searches', 'Daily search requests', 'count', 'daily', ARRAY[50, 80, 95], true)
    """)

    # ========================================================================
    # Tier Quota Limits
    # ========================================================================
    op.create_table(
        "tier_quota_limits",
        sa.Column("tier", sa.String(50), nullable=False),
        sa.Column(
            "quota_type_id",
            sa.String(50),
            sa.ForeignKey("quota_types.id"),
            nullable=False,
        ),
        sa.Column("limit_value", sa.Numeric, nullable=False),
        sa.Column("is_unlimited", sa.Boolean, default=False, nullable=False),
        sa.PrimaryKeyConstraint("tier", "quota_type_id"),
    )

    # Insert tier limits (matching existing PRICING_TIERS config)
    op.execute("""
        INSERT INTO tier_quota_limits (tier, quota_type_id, limit_value, is_unlimited)
        VALUES
            -- Free tier
            ('free', 'videos', 10, false),
            ('free', 'minutes', 1000, false),
            ('free', 'messages', 200, false),
            ('free', 'storage', 1000, false),
            ('free', 'youtube_searches', 10, false),
            -- Pro tier
            ('pro', 'videos', -1, true),
            ('pro', 'minutes', -1, true),
            ('pro', 'messages', -1, true),
            ('pro', 'storage', 50000, false),
            ('pro', 'youtube_searches', 100, false),
            -- Enterprise tier
            ('enterprise', 'videos', -1, true),
            ('enterprise', 'minutes', -1, true),
            ('enterprise', 'messages', -1, true),
            ('enterprise', 'storage', -1, true),
            ('enterprise', 'youtube_searches', -1, true)
    """)

    # ========================================================================
    # User Quota Usage
    # ========================================================================
    op.create_table(
        "user_quota_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quota_type_id",
            sa.String(50),
            sa.ForeignKey("quota_types.id"),
            nullable=False,
        ),
        # Current limits
        sa.Column("limit_value", sa.Numeric, nullable=False),
        sa.Column("is_unlimited", sa.Boolean, default=False, nullable=False),
        sa.Column("is_admin_override", sa.Boolean, default=False, nullable=False),
        # Current usage
        sa.Column("used_value", sa.Numeric, default=0, nullable=False),
        # Period tracking
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        # Metadata
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Unique per user/quota/period
        sa.UniqueConstraint(
            "user_id",
            "quota_type_id",
            "period_start",
            name="uq_user_quota_usage",
        ),
    )

    op.create_index(
        "idx_user_quota_usage_lookup",
        "user_quota_usage",
        ["user_id", "quota_type_id"],
    )

    # ========================================================================
    # Notification Event Types Registry
    # ========================================================================
    op.create_table(
        "notification_event_types",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "default_channels",
            postgresql.ARRAY(sa.Text),
            server_default=sa.text("ARRAY['in_app']"),
            nullable=False,
        ),
        sa.Column("default_frequency", sa.String(50), default="immediate", nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column(
            "template_data",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    # Insert default notification event types
    op.execute("""
        INSERT INTO notification_event_types (id, category, display_name, default_channels, default_frequency, is_active)
        VALUES
            ('content.discovered', 'content', 'New Content Discovered', ARRAY['in_app'], 'immediate', true),
            ('content.processing_complete', 'content', 'Processing Complete', ARRAY['in_app'], 'immediate', true),
            ('content.processing_failed', 'content', 'Processing Failed', ARRAY['in_app', 'email'], 'immediate', true),
            ('quota.warning', 'account', 'Quota Warning', ARRAY['in_app'], 'immediate', true),
            ('quota.exceeded', 'account', 'Quota Exceeded', ARRAY['in_app', 'email'], 'immediate', true),
            ('subscription.new_content', 'content', 'New from Subscription', ARRAY['in_app'], 'immediate', true),
            ('recommendation.weekly', 'content', 'Weekly Recommendations', ARRAY['email'], 'weekly', true)
    """)

    # ========================================================================
    # User Notification Preferences
    # ========================================================================
    op.create_table(
        "user_notification_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type_id",
            sa.String(100),
            sa.ForeignKey("notification_event_types.id"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("enabled_channels", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("frequency", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "event_type_id"),
    )

    # ========================================================================
    # Notifications
    # ========================================================================
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type_id",
            sa.String(100),
            sa.ForeignKey("notification_event_types.id"),
            nullable=False,
        ),
        # Content
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        # Status
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
    )

    # ========================================================================
    # Notification Deliveries
    # ========================================================================
    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="pending", nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
    )

    op.create_index(
        "idx_notification_deliveries_pending",
        "notification_deliveries",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ========================================================================
    # User Table Additions
    # ========================================================================
    op.add_column(
        "users",
        sa.Column("email_digest_enabled", sa.Boolean, default=True, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_digest_frequency", sa.String(50), default="daily", nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(50), default="UTC", nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("recommendations_enabled", sa.Boolean, default=True, nullable=True),
    )


def downgrade():
    # Drop user columns
    op.drop_column("users", "recommendations_enabled")
    op.drop_column("users", "timezone")
    op.drop_column("users", "email_digest_frequency")
    op.drop_column("users", "email_digest_enabled")

    # Drop tables in reverse order of creation
    op.drop_table("notification_deliveries")
    op.drop_table("notifications")
    op.drop_table("user_notification_preferences")
    op.drop_table("notification_event_types")
    op.drop_table("user_quota_usage")
    op.drop_table("tier_quota_limits")
    op.drop_table("quota_types")
    op.drop_table("user_interest_profiles")
    op.drop_table("discovered_content")
    op.drop_table("discovery_sources")
    op.drop_table("content_source_types")
