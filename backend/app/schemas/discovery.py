"""
Pydantic schemas for discovery-related API endpoints.

Includes schemas for:
- YouTube search
- Discovery sources (subscriptions)
- Discovered content
- Recommendations
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


# =============================================================================
# YouTube Search Schemas
# =============================================================================


class YouTubeSearchRequest(BaseModel):
    """Request to search YouTube videos."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    max_results: int = Field(default=25, ge=1, le=100, description="Results per page (max 50 for API, 100 for yt-dlp)")
    page_token: Optional[str] = Field(default=None, description="Page token for pagination (API mode only)")

    # Filter options
    duration: Optional[str] = Field(
        default=None,
        description="Video duration filter: short (<4 min), medium (4-20 min), long (>20 min)"
    )
    published_after: Optional[str] = Field(
        default=None,
        description="Published after filter: ISO date string or 'week', 'month', 'year'"
    )
    order: Optional[str] = Field(
        default="relevance",
        description="Sort order: relevance, date, viewCount"
    )
    category: Optional[str] = Field(
        default=None,
        description="Content category: education, howto, tech, entertainment"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "machine learning tutorial",
                "max_results": 25,
                "page_token": None,
                "duration": None,
                "published_after": None,
                "order": "relevance",
                "category": None,
            }
        }


class YouTubeSearchResult(BaseModel):
    """Single YouTube search result."""

    id: str = Field(..., description="YouTube video ID")
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    view_count: Optional[int] = None
    already_imported: bool = Field(default=False, description="True if user has already imported this video")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "dQw4w9WgXcQ",
                "title": "Example Video",
                "description": "An example video description",
                "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
                "duration_seconds": 212,
                "channel_name": "Example Channel",
                "view_count": 1000000,
            }
        }


class YouTubeSearchResponse(BaseModel):
    """Response from YouTube search."""

    results: List[YouTubeSearchResult]
    total: int
    quota_used: int = Field(default=1, description="Search quota units used")
    quota_remaining: int = Field(description="Remaining search quota for today")

    # Pagination fields (only available when YouTube API key is configured)
    next_page_token: Optional[str] = Field(default=None, description="Token for next page (API mode only)")
    prev_page_token: Optional[str] = Field(default=None, description="Token for previous page (API mode only)")
    total_results: Optional[int] = Field(default=None, description="Total results across all pages (API mode)")
    has_api_pagination: bool = Field(default=False, description="True if server-side pagination is available")

    class Config:
        json_schema_extra = {
            "example": {
                "results": [],
                "total": 0,
                "quota_used": 1,
                "quota_remaining": 9,
                "next_page_token": None,
                "prev_page_token": None,
                "total_results": None,
                "has_api_pagination": False,
            }
        }


class YouTubeBatchImportRequest(BaseModel):
    """Request to import multiple YouTube videos."""

    video_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="YouTube video IDs to import",
    )
    collection_id: Optional[UUID] = Field(
        default=None,
        description="Optional collection to add videos to",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "video_ids": ["dQw4w9WgXcQ", "jNQXAC9IVRw"],
                "collection_id": None,
            }
        }


class BatchImportResultItem(BaseModel):
    """Result for a single video in batch import."""

    video_id: str
    success: bool
    internal_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    error: Optional[str] = None


class YouTubeBatchImportResponse(BaseModel):
    """Response from batch import."""

    total: int
    imported: int
    failed: int
    results: List[BatchImportResultItem]


# =============================================================================
# Discovery Source Schemas
# =============================================================================


class DiscoverySourceCreate(BaseModel):
    """Request to create a discovery source (subscription)."""

    source_type: str = Field(
        ...,
        description="Type of source: youtube_channel, youtube_topic",
    )
    source_identifier: str = Field(
        ...,
        description="Source identifier (channel ID, topic name)",
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific configuration",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source_type": "youtube_channel",
                "source_identifier": "UCxyz123",
                "config": {"notify": True, "auto_import": False},
            }
        }


class DiscoverySourceUpdate(BaseModel):
    """Request to update a discovery source."""

    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    check_frequency_hours: Optional[int] = Field(default=None, ge=1, le=168)


class DiscoverySourceResponse(BaseModel):
    """Discovery source response."""

    id: UUID
    source_type: str
    source_identifier: str
    display_name: Optional[str] = None
    display_image_url: Optional[str] = None
    config: Dict[str, Any]
    is_explicit: bool
    is_active: bool
    last_checked_at: Optional[datetime] = None
    check_frequency_hours: int
    created_at: datetime

    class Config:
        from_attributes = True


class DiscoverySourceList(BaseModel):
    """List of discovery sources."""

    sources: List[DiscoverySourceResponse]
    total: int


# =============================================================================
# Discovered Content Schemas
# =============================================================================


class DiscoveredContentResponse(BaseModel):
    """Discovered content item response."""

    id: UUID
    source_type: str
    source_identifier: str
    content_type: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_metadata: Dict[str, Any]
    discovery_reason: Optional[str] = None
    discovery_context: Dict[str, Any]
    status: str
    discovered_at: datetime
    expires_at: Optional[datetime] = None
    discovery_source_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class DiscoveredContentList(BaseModel):
    """List of discovered content."""

    items: List[DiscoveredContentResponse]
    total: int
    pending_count: int


class DiscoveredContentAction(BaseModel):
    """Request to action discovered content."""

    action: str = Field(
        ...,
        description="Action to take: import, dismiss",
    )
    collection_id: Optional[UUID] = Field(
        default=None,
        description="Collection to add to (for import action)",
    )


class BulkDiscoveredContentAction(BaseModel):
    """Request to action multiple discovered content items."""

    content_ids: List[UUID]
    action: str = Field(..., description="import, dismiss, or dismiss_all")
    collection_id: Optional[UUID] = None


# =============================================================================
# Channel Info Schemas
# =============================================================================


class ChannelInfoRequest(BaseModel):
    """Request for channel info."""

    channel_url: Optional[str] = Field(
        default=None,
        description="YouTube channel URL (any format)",
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Direct channel ID",
    )


class ChannelInfoResponse(BaseModel):
    """YouTube channel info response."""

    channel_id: str
    display_name: str
    display_image_url: Optional[str] = None
    description: Optional[str] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    is_subscribed: bool = False


# =============================================================================
# Recommendation Schemas
# =============================================================================


class RecommendationItem(BaseModel):
    """A recommended content item."""

    source_type: str
    source_identifier: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    reason: str  # topic_match, channel_follow, trending
    context: Dict[str, Any]  # {matched_topic: "...", score: 0.85}
    score: float


class RecommendationResponse(BaseModel):
    """Response with recommendations."""

    recommendations: List[RecommendationItem]
    generated_at: datetime
    strategies_used: List[str]
