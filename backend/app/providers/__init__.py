"""
Content providers package.

Providers handle content from different sources (YouTube, RSS, uploads, etc.)
with a unified interface for searching, fetching, and processing content.
"""
from app.providers.base import (
    ContentProvider,
    DiscoveryProvider,
    SearchResult,
    ContentMetadata,
    SourceInfo,
    ValidationResult,
    DiscoveredContentData,
)
from app.providers.registry import provider_registry
from app.providers.youtube import YouTubeProvider

__all__ = [
    # Base classes and types
    "ContentProvider",
    "DiscoveryProvider",
    "SearchResult",
    "ContentMetadata",
    "SourceInfo",
    "ValidationResult",
    "DiscoveredContentData",
    # Registry
    "provider_registry",
    # Providers
    "YouTubeProvider",
]
