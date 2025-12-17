"""
Pydantic schemas for conversation insights.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReactFlowNode(BaseModel):
    id: str
    type: str
    position: Dict[str, float]
    data: Dict[str, Any]


class ReactFlowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Optional[str] = None


class InsightGraph(BaseModel):
    nodes: List[ReactFlowNode]
    edges: List[ReactFlowEdge]


class ConversationInsightsMetadata(BaseModel):
    topics_count: int = Field(..., ge=0)
    total_chunks_analyzed: int = Field(..., ge=0)
    generation_time_seconds: Optional[float] = Field(None, ge=0)
    cached: bool
    created_at: datetime
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    extraction_prompt_version: int = Field(..., ge=1)


class ConversationInsightsResponse(BaseModel):
    conversation_id: UUID
    graph: InsightGraph
    metadata: ConversationInsightsMetadata


class TopicChunk(BaseModel):
    chunk_id: UUID
    video_id: UUID
    video_title: str
    start_timestamp: float
    end_timestamp: float
    timestamp_display: str
    text: str
    chunk_title: Optional[str] = None
    chapter_title: Optional[str] = None
    chunk_summary: Optional[str] = None


class TopicChunksResponse(BaseModel):
    topic_id: str
    topic_label: str
    chunks: List[TopicChunk]
