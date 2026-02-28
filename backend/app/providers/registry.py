"""
Provider registry for content and discovery providers.

The registry is a singleton that holds all registered providers,
allowing the application to dynamically dispatch to the correct
provider based on source type.
"""
from typing import Dict, Optional, List
import logging

from app.providers.base import ContentProvider, DiscoveryProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for content and discovery providers.

    Usage:
        # Register a provider
        provider_registry.register_content_provider(YouTubeProvider())

        # Get a provider
        provider = provider_registry.get_content_provider("youtube")
        results = await provider.search("python tutorial")
    """

    def __init__(self):
        self._content_providers: Dict[str, ContentProvider] = {}
        self._discovery_providers: Dict[str, DiscoveryProvider] = {}
        self._initialized = False

    def register_content_provider(self, provider: ContentProvider) -> None:
        """
        Register a content provider.

        Args:
            provider: ContentProvider instance to register
        """
        source_type = provider.source_type
        if source_type in self._content_providers:
            logger.warning(f"Overwriting existing content provider for: {source_type}")
        self._content_providers[source_type] = provider
        logger.info(f"Registered content provider: {source_type}")

    def register_discovery_provider(
        self,
        source_types: List[str],
        provider: DiscoveryProvider,
    ) -> None:
        """
        Register a discovery provider for one or more source types.

        Args:
            source_types: List of source types this provider handles
            provider: DiscoveryProvider instance to register
        """
        for source_type in source_types:
            if source_type in self._discovery_providers:
                logger.warning(f"Overwriting existing discovery provider for: {source_type}")
            self._discovery_providers[source_type] = provider
            logger.info(f"Registered discovery provider for: {source_type}")

    def get_content_provider(self, source_type: str) -> ContentProvider:
        """
        Get a content provider by source type.

        Args:
            source_type: Source type identifier

        Returns:
            ContentProvider instance

        Raises:
            ValueError: If no provider is registered for the source type
        """
        self._ensure_initialized()
        if source_type not in self._content_providers:
            raise ValueError(
                f"No content provider registered for source type: {source_type}. "
                f"Available: {list(self._content_providers.keys())}"
            )
        return self._content_providers[source_type]

    def get_discovery_provider(self, source_type: str) -> DiscoveryProvider:
        """
        Get a discovery provider by source type.

        Args:
            source_type: Source type identifier

        Returns:
            DiscoveryProvider instance

        Raises:
            ValueError: If no provider is registered for the source type
        """
        self._ensure_initialized()
        if source_type not in self._discovery_providers:
            raise ValueError(
                f"No discovery provider registered for source type: {source_type}. "
                f"Available: {list(self._discovery_providers.keys())}"
            )
        return self._discovery_providers[source_type]

    def has_content_provider(self, source_type: str) -> bool:
        """Check if a content provider is registered for the source type."""
        self._ensure_initialized()
        return source_type in self._content_providers

    def has_discovery_provider(self, source_type: str) -> bool:
        """Check if a discovery provider is registered for the source type."""
        self._ensure_initialized()
        return source_type in self._discovery_providers

    def list_content_providers(self) -> List[str]:
        """Get list of registered content provider source types."""
        self._ensure_initialized()
        return list(self._content_providers.keys())

    def list_discovery_providers(self) -> List[str]:
        """Get list of registered discovery provider source types."""
        self._ensure_initialized()
        return list(self._discovery_providers.keys())

    def get_configured_content_providers(self) -> Dict[str, bool]:
        """
        Get dict of content providers and their configuration status.

        Returns:
            Dict mapping source_type to is_configured boolean
        """
        self._ensure_initialized()
        return {
            source_type: provider.is_configured()
            for source_type, provider in self._content_providers.items()
        }

    def _ensure_initialized(self) -> None:
        """Ensure providers are registered on first access."""
        if self._initialized:
            return

        # Lazy import to avoid circular dependencies
        try:
            from app.providers.youtube import YouTubeProvider

            youtube = YouTubeProvider()

            # Register as both content and discovery provider
            self.register_content_provider(youtube)
            self.register_discovery_provider(
                ["youtube_channel", "youtube_topic"],
                youtube,
            )
        except Exception as e:
            logger.error(f"Failed to initialize YouTube provider: {e}")

        self._initialized = True


# Singleton instance
provider_registry = ProviderRegistry()
