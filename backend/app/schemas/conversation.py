"""
Pydantic schemas for conversations and chat messages.
"""
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request schemas
class ConversationCreateRequest(BaseModel):
    """Request to create a new conversation."""
    title: Optional[str] = Field(None, max_length=255, description="Conversation title (auto-generated if not provided)")
    selected_video_ids: List[UUID] = Field(..., min_items=1, description="List of video IDs to include in conversation scope")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Discussion about React hooks",
                "selected_video_ids": ["550e8400-e29b-41d4-a716-446655440000"]
            }
        }


class ConversationUpdateRequest(BaseModel):
    """Request to update conversation."""
    title: Optional[str] = Field(None, max_length=255)
    selected_video_ids: Optional[List[UUID]] = None


class MessageSendRequest(BaseModel):
    """Request to send a message in a conversation."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    stream: bool = Field(False, description="Whether to stream the response")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are the main benefits of using React hooks?",
                "stream": False
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
                "timestamp_display": "02:05 - 03:00"
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
    chunk_references: List[ChunkReference] = []


class ConversationDetail(BaseModel):
    """Detailed conversation information."""
    id: UUID
    user_id: UUID
    title: Optional[str] = None
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


class MessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: UUID
    conversation_id: UUID
    role: str
    content: str
    chunk_references: List[ChunkReference]
    token_count: int
    response_time_seconds: float

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
