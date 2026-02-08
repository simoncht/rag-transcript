"""
Database models package.

All SQLAlchemy models are exported from this module for easy imports.
"""
from app.models.user import User
from app.models.video import Video
from app.models.transcript import Transcript
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.conversation_source import ConversationSource
from app.models.conversation_insight import ConversationInsight
from app.models.conversation_fact import ConversationFact
from app.models.message import Message, MessageChunkReference
from app.models.collection import Collection, CollectionVideo, CollectionMember
from app.models.usage import UsageEvent, UserQuota
from app.models.llm_usage import LLMUsageEvent, calculate_llm_cost
from app.models.job import Job
from app.models.admin_audit_log import AdminAuditLog
from app.models.subscription import Subscription

# Discovery and content source models
from app.models.discovery import (
    DiscoverySource,
    DiscoveredContent,
    UserInterestProfile,
)

# Quota registry models
from app.models.quota import (
    QuotaType,
    TierQuotaLimit,
    UserQuotaUsage,
)

# Collection theme models
from app.models.collection_theme import CollectionTheme

# Notification models
from app.models.notification import (
    NotificationEventType,
    UserNotificationPreference,
    Notification,
    NotificationDelivery,
)

__all__ = [
    "User",
    "Video",
    "Transcript",
    "Chunk",
    "Conversation",
    "ConversationSource",
    "ConversationInsight",
    "ConversationFact",
    "Message",
    "MessageChunkReference",
    "Collection",
    "CollectionVideo",
    "CollectionMember",
    "UsageEvent",
    "UserQuota",
    "LLMUsageEvent",
    "calculate_llm_cost",
    "Job",
    "AdminAuditLog",
    "Subscription",
    # Discovery models
    "DiscoverySource",
    "DiscoveredContent",
    "UserInterestProfile",
    # Quota models
    "QuotaType",
    "TierQuotaLimit",
    "UserQuotaUsage",
    # Notification models
    "NotificationEventType",
    "UserNotificationPreference",
    "Notification",
    "NotificationDelivery",
    # Collection theme models
    "CollectionTheme",
]
