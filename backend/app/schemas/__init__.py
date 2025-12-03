"""
Pydantic schemas for API request/response validation.
"""
from app.schemas.video import (
    VideoIngestRequest,
    VideoIngestResponse,
    VideoMetadata,
    VideoStatus,
    VideoDetail,
    VideoList,
)
from app.schemas.job import (
    JobStatus,
    JobDetail,
)
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    MessageSendRequest,
    ChunkReference,
    Message,
    MessageWithReferences,
    ConversationDetail,
    ConversationWithMessages,
    ConversationList,
    MessageResponse,
)

__all__ = [
    # Video
    "VideoIngestRequest",
    "VideoIngestResponse",
    "VideoMetadata",
    "VideoStatus",
    "VideoDetail",
    "VideoList",
    # Job
    "JobStatus",
    "JobDetail",
    # Conversation
    "ConversationCreateRequest",
    "ConversationUpdateRequest",
    "MessageSendRequest",
    "ChunkReference",
    "Message",
    "MessageWithReferences",
    "ConversationDetail",
    "ConversationWithMessages",
    "ConversationList",
    "MessageResponse",
]