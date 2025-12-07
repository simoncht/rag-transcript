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
    VideoDeleteRequest,
    VideoDeleteResponse,
    VideoDeleteBreakdown,
)
from app.schemas.job import (
    JobStatus,
    JobDetail,
)
from app.schemas.transcript import (
    TranscriptDetail,
    TranscriptSegment,
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
    ConversationSource,
    ConversationSourcesResponse,
    ConversationSourcesUpdateRequest,
)
from app.schemas.collection import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    CollectionAddVideosRequest,
    VideoUpdateTagsRequest,
    CollectionVideoInfo,
    CollectionSummary,
    CollectionDetail,
    CollectionList,
    VideoWithCollections,
)
from app.schemas.usage import (
    UsageSummary,
    StorageBreakdown,
    UsageCounts,
    VectorStoreStat,
    QuotaStat,
)

__all__ = [
    # Video
    "VideoIngestRequest",
    "VideoIngestResponse",
    "VideoMetadata",
    "VideoStatus",
    "VideoDetail",
    "VideoList",
    "VideoDeleteRequest",
    "VideoDeleteResponse",
    "VideoDeleteBreakdown",
    # Transcript
    "TranscriptDetail",
    "TranscriptSegment",
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
    "ConversationSource",
    "ConversationSourcesResponse",
    "ConversationSourcesUpdateRequest",
    # Collection
    "CollectionCreateRequest",
    "CollectionUpdateRequest",
    "CollectionAddVideosRequest",
    "VideoUpdateTagsRequest",
    "CollectionVideoInfo",
    "CollectionSummary",
    "CollectionDetail",
    "CollectionList",
    "VideoWithCollections",
    # Usage
    "UsageSummary",
    "StorageBreakdown",
    "UsageCounts",
    "VectorStoreStat",
    "QuotaStat",
]
