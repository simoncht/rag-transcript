"""
Base interfaces for content and discovery providers.

These abstract base classes define the contract that all providers must implement.
This enables adding new content sources (PDFs, podcasts, etc.) without changing
the core application logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class SearchResult:
    """Result from a content search."""

    id: str  # Source-specific ID (e.g., YouTube video ID)
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source_type: str = ""  # youtube, rss, etc.
    content_type: str = "video"  # video, audio, document
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    view_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "source_type": self.source_type,
            "content_type": self.content_type,
            "duration_seconds": self.duration_seconds,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "channel_name": self.channel_name,
            "channel_id": self.channel_id,
            "view_count": self.view_count,
            "metadata": self.metadata,
        }


@dataclass
class ContentMetadata:
    """Full metadata for a content item."""

    id: str
    title: str
    description: Optional[str] = None
    source_type: str = ""
    content_type: str = "video"
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    language: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceInfo:
    """Display information for a discovery source."""

    identifier: str
    display_name: str
    display_image_url: Optional[str] = None
    description: Optional[str] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result from content validation."""

    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class DiscoveredContentData:
    """Data for newly discovered content from a source."""

    source_identifier: str  # Source-specific ID
    content_type: str  # video, audio, document
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContentProvider(ABC):
    """
    Base interface for all content source providers.

    Providers handle fetching, validating, and processing content from
    specific sources like YouTube, RSS feeds, file uploads, etc.
    """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'youtube', 'rss')."""
        pass

    @property
    def display_name(self) -> str:
        """Human-readable name for this provider."""
        return self.source_type.replace("_", " ").title()

    def is_configured(self) -> bool:
        """Check if the provider is properly configured (API keys, etc.)."""
        return True

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs,
    ) -> List[SearchResult]:
        """
        Search for content from this source.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Provider-specific search options

        Returns:
            List of SearchResult objects
        """
        pass

    @abstractmethod
    async def get_metadata(self, source_identifier: str) -> ContentMetadata:
        """
        Fetch full metadata for a specific content item.

        Args:
            source_identifier: Source-specific identifier (e.g., YouTube video ID)

        Returns:
            ContentMetadata object with full details
        """
        pass

    @abstractmethod
    async def validate(self, source_identifier: str) -> ValidationResult:
        """
        Validate that content can be processed.

        Checks things like:
        - Content exists
        - Content is accessible
        - Duration within limits
        - No age restrictions

        Args:
            source_identifier: Source-specific identifier

        Returns:
            ValidationResult with is_valid flag and any error messages
        """
        pass


class DiscoveryProvider(ABC):
    """
    Base interface for discovery source providers.

    Discovery providers check subscribed sources for new content
    and fetch display info for sources.
    """

    @abstractmethod
    async def check_for_new_content(
        self,
        source_type: str,
        source_identifier: str,
        since: datetime,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[DiscoveredContentData]:
        """
        Check a discovery source for new content since the last check.

        Args:
            source_type: Type of source (e.g., 'youtube_channel')
            source_identifier: Source-specific ID (e.g., channel ID)
            since: Only return content newer than this timestamp
            config: Optional source-specific configuration

        Returns:
            List of DiscoveredContentData for new items
        """
        pass

    @abstractmethod
    async def get_source_info(
        self,
        source_type: str,
        source_identifier: str,
    ) -> SourceInfo:
        """
        Get display info for a discovery source.

        Args:
            source_type: Type of source
            source_identifier: Source-specific ID

        Returns:
            SourceInfo with display name, image, etc.
        """
        pass

    def get_supported_source_types(self) -> List[str]:
        """Return list of source types this provider supports."""
        return []
