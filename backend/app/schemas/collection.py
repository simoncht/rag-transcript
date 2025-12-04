"""
Pydantic schemas for collections and video organization.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request schemas
class CollectionCreateRequest(BaseModel):
    """Request to create a new collection."""
    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Collection metadata (instructor, subject, semester, tags)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Machine Learning Course",
                "description": "Stanford CS229 lectures",
                "metadata": {
                    "instructor": "Dr. Andrew Ng",
                    "subject": "Computer Science",
                    "semester": "Fall 2024",
                    "tags": ["course", "ai", "ml"]
                }
            }
        }


class CollectionUpdateRequest(BaseModel):
    """Request to update collection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CollectionAddVideosRequest(BaseModel):
    """Request to add videos to collection."""
    video_ids: List[UUID] = Field(..., min_items=1, description="List of video IDs to add")

    class Config:
        json_schema_extra = {
            "example": {
                "video_ids": ["550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440001"]
            }
        }


class VideoUpdateTagsRequest(BaseModel):
    """Request to update video tags."""
    tags: List[str] = Field(default_factory=list, description="List of tags")

    class Config:
        json_schema_extra = {
            "example": {
                "tags": ["midterm-prep", "advanced", "important"]
            }
        }


# Response schemas
class CollectionVideoInfo(BaseModel):
    """Video info within a collection."""
    id: UUID
    title: str
    youtube_id: str
    duration_seconds: Optional[int]
    status: str
    thumbnail_url: Optional[str]
    tags: List[str]
    added_at: datetime
    position: Optional[int]

    class Config:
        from_attributes = True


class CollectionSummary(BaseModel):
    """Collection summary for list views."""
    id: UUID
    name: str
    description: Optional[str]
    metadata: Dict[str, Any]
    is_default: bool
    video_count: int = Field(0, description="Number of videos in collection")
    total_duration_seconds: int = Field(0, description="Total duration of all videos")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionDetail(BaseModel):
    """Detailed collection with videos."""
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    metadata: Dict[str, Any]
    is_default: bool
    video_count: int = Field(0, description="Number of videos in collection")
    total_duration_seconds: int = Field(0, description="Total duration of all videos")
    videos: List[CollectionVideoInfo] = Field(default_factory=list, description="Videos in this collection")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionList(BaseModel):
    """Paginated list of collections."""
    total: int
    collections: List[CollectionSummary]


class VideoWithCollections(BaseModel):
    """Video info with its collections."""
    id: UUID
    title: str
    youtube_id: str
    duration_seconds: Optional[int]
    status: str
    thumbnail_url: Optional[str]
    tags: List[str]
    collections: List[CollectionSummary] = Field(default_factory=list, description="Collections this video belongs to")
    created_at: datetime

    class Config:
        from_attributes = True
