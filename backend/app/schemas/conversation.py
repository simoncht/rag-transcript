"""
Pydantic schemas for conversations and chat messages.
"""
from typing import Literal, Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request schemas
class ConversationCreateRequest(BaseModel):
    """Request to create a new conversation."""
    title: Optional[str] = Field(None, max_length=255, description="Conversation title (auto-generated if not provided)")
    collection_id: Optional[UUID] = Field(None, description="Collection ID (use all videos from collection)")
    selected_video_ids: Optional[List[UUID]] = Field(None, min_items=1, description="List of video IDs to include in conversation scope")
    # Optional: set true to auto-select new collection videos (default behaviour)
    auto_sync_collection: bool | None = Field(
        None,
        description="If provided with collection_id, automatically sync new collection videos. Defaults to true.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Discussion about React hooks",
                "collection_id": "770e8400-e29b-41d4-a716-446655440000"
            }
        }


class ConversationUpdateRequest(BaseModel):
    """Request to update conversation."""
    title: Optional[str] = Field(None, max_length=255)
    selected_video_ids: Optional[List[UUID]] = None
    add_video_ids: Optional[List[UUID]] = None  # Optional manual additions


class MessageSendRequest(BaseModel):
    """Request to send a message in a conversation."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    stream: bool = Field(False, description="Whether to stream the response")
    mode: Literal[
        "summarize",
        "deep_dive",
        "compare_sources",
        "timeline",
        "extract_actions",
        "quiz_me",
    ] = Field(
        "summarize",
        description="Response mode indicating how the assistant should structure the answer.",
    )
    model: Optional[str] = Field(
        None,
        description=(
            "Optional LLM model identifier (e.g., 'llama3.1:8b-instruct') to use for this message. "
            "If not provided, the backend default model is used."
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
          "message": "What are the main benefits of using React hooks?",
          "stream": False,
          "mode": "summarize"
        }
      }


# Response schemas
class ChunkReference(BaseModel):
    """Reference to a source chunk used in response."""
    chunk_id: UUID
    video_id: UUID
    video_title: str
    start_timestamp: float
    end_timestamp: float
    text_snippet: str = Field(..., max_length=500, description="Excerpt from the chunk")
    relevance_score: float = Field(..., ge=0, le=1, description="Relevance score (0-1)")
    timestamp_display: str = Field(..., description="Human-readable timestamp (MM:SS or HH:MM:SS)")
    rank: int = Field(..., description="Rank/order used when labeling sources (Source 1, Source 2, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "660e8400-e29b-41d4-a716-446655440000",
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "video_title": "React Hooks Explained",
            "start_timestamp": 125.5,
            "end_timestamp": 180.2,
            "text_snippet": "React hooks allow you to use state and other React features without writing a class...",
            "relevance_score": 0.92,
            "timestamp_display": "02:05 - 03:00",
            "rank": 1,
            }
        }


class Message(BaseModel):
    """Chat message."""
    id: UUID
    role: str = Field(..., description="Message role: user or assistant")
    content: str
    token_count: int
    created_at: datetime

    # For assistant messages
    chunks_retrieved_count: Optional[int] = None
    response_time_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class MessageWithReferences(Message):
    """Message with source chunk references."""
    chunk_references: List[ChunkReference] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    """Detailed conversation information."""
    id: UUID
    user_id: UUID
    title: Optional[str] = None
    collection_id: Optional[UUID] = None
    selected_video_ids: List[UUID]
    message_count: int
    total_tokens_used: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationDetail):
    """Conversation with message history."""
    messages: List[MessageWithReferences]


class ConversationList(BaseModel):
    """List of conversations."""
    total: int
    conversations: List[ConversationDetail]


class ConversationSource(BaseModel):
    """A video/transcript attached to a conversation."""

    conversation_id: UUID
    video_id: UUID
    is_selected: bool
    added_at: datetime
    added_via: Optional[str] = None

    # Video metadata for UI
    title: Optional[str] = None
    status: Optional[str] = None
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    youtube_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "880e8400-e29b-41d4-a716-446655440000",
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "is_selected": True,
                "added_at": "2025-12-06T12:00:00Z",
                "added_via": "collection",
                "title": "React Hooks Explained",
                "status": "completed",
                "duration_seconds": 1234,
                "thumbnail_url": "https://img.youtube.com/...",
                "youtube_id": "abcd123",
            }
        }


class ConversationSourcesResponse(BaseModel):
    """List of sources for a conversation."""

    total: int
    selected: int
    sources: List[ConversationSource]


class ConversationSourcesUpdateRequest(BaseModel):
    """Update selection for conversation sources."""

    selected_video_ids: Optional[List[UUID]] = None
    add_video_ids: Optional[List[UUID]] = None


class MessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: UUID
    conversation_id: UUID
    role: str
    content: str
    chunk_references: List[ChunkReference]
    token_count: int
    response_time_seconds: float
    model: Optional[str] = Field(
        None,
        description="LLM model used to generate this response (if available).",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "770e8400-e29b-41d4-a716-446655440000",
                "conversation_id": "880e8400-e29b-41d4-a716-446655440000",
                "role": "assistant",
                "content": "React hooks provide several key benefits: 1) They allow you to use state...",
                "chunk_references": [],
                "token_count": 150,
                "response_time_seconds": 2.5
            }
        }
