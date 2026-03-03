"""
Discovery service for managing content sources and discovered content.

Handles:
- Discovery source subscriptions (channels, topics)
- Checking sources for new content
- Managing discovered content lifecycle
- User interest profile updates
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.discovery import (
    DiscoverySource,
    DiscoveredContent,
    UserInterestProfile,
)
from app.providers.registry import provider_registry
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class DiscoveryService:
    """
    Manages discovery sources and discovered content.

    Usage:
        service = DiscoveryService(db, NotificationService(db))

        # Subscribe to a channel
        source = await service.subscribe(
            user_id=user.id,
            source_type="youtube_channel",
            source_identifier="UCxyz...",
        )

        # Check source for new content
        new_count = await service.check_source(source)
    """

    def __init__(self, db: Session, notifications: Optional[NotificationService] = None):
        self.db = db
        self.notifications = notifications

    async def subscribe(
        self,
        user_id: UUID,
        source_type: str,
        source_identifier: str,
        is_explicit: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> DiscoverySource:
        """
        Subscribe to a discovery source.

        Args:
            user_id: User UUID
            source_type: Type of source (youtube_channel, youtube_topic)
            source_identifier: Source-specific identifier
            is_explicit: Whether user explicitly subscribed
            config: Optional source configuration

        Returns:
            DiscoverySource instance
        """
        # Check for existing subscription
        existing = (
            self.db.query(DiscoverySource)
            .filter(
                DiscoverySource.user_id == user_id,
                DiscoverySource.source_type == source_type,
                DiscoverySource.source_identifier == source_identifier,
            )
            .first()
        )

        if existing:
            # Upgrade auto-follow to explicit if needed
            if is_explicit and not existing.is_explicit:
                existing.is_explicit = True
                self.db.commit()
            return existing

        # Get source info from provider
        try:
            provider = provider_registry.get_discovery_provider(source_type)
            source_info = await provider.get_source_info(source_type, source_identifier)
        except Exception as e:
            logger.warning(f"Failed to get source info: {e}")
            # Create with minimal info
            source_info = None

        source = DiscoverySource(
            user_id=user_id,
            source_type=source_type,
            source_identifier=source_identifier,
            display_name=source_info.display_name if source_info else source_identifier,
            display_image_url=source_info.display_image_url if source_info else None,
            config=config or {},
            is_explicit=is_explicit,
            is_active=True,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)

        logger.info(
            f"User {user_id} subscribed to {source_type}: {source_identifier}"
        )

        return source

    def unsubscribe(self, user_id: UUID, source_id: UUID) -> bool:
        """
        Unsubscribe from a discovery source.

        Args:
            user_id: User UUID
            source_id: Source UUID to unsubscribe

        Returns:
            True if unsubscribed, False if not found
        """
        source = (
            self.db.query(DiscoverySource)
            .filter(
                DiscoverySource.id == source_id,
                DiscoverySource.user_id == user_id,
            )
            .first()
        )

        if not source:
            return False

        self.db.delete(source)
        self.db.commit()

        logger.info(f"User {user_id} unsubscribed from source {source_id}")
        return True

    def get_user_sources(
        self,
        user_id: UUID,
        source_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[DiscoverySource]:
        """Get all discovery sources for a user."""
        query = self.db.query(DiscoverySource).filter(
            DiscoverySource.user_id == user_id
        )

        if source_type:
            query = query.filter(DiscoverySource.source_type == source_type)
        if is_active is not None:
            query = query.filter(DiscoverySource.is_active == is_active)

        return query.order_by(DiscoverySource.created_at.desc()).all()

    async def check_source(self, source: DiscoverySource) -> int:
        """
        Check a discovery source for new content.

        Args:
            source: DiscoverySource to check

        Returns:
            Number of new items discovered
        """
        if not source.is_active:
            return 0

        try:
            provider = provider_registry.get_discovery_provider(source.source_type)
        except ValueError:
            logger.warning(f"No provider for source type: {source.source_type}")
            return 0

        since = source.last_checked_at or (datetime.utcnow() - timedelta(days=7))

        try:
            new_items = await provider.check_for_new_content(
                source.source_type,
                source.source_identifier,
                since,
                source.config,
            )
        except Exception as e:
            logger.error(f"Failed to check source {source.id}: {e}")
            return 0

        added_count = 0
        for item in new_items:
            # Skip if already discovered
            existing = (
                self.db.query(DiscoveredContent)
                .filter(
                    DiscoveredContent.user_id == source.user_id,
                    DiscoveredContent.source_type == source.source_type,
                    DiscoveredContent.source_identifier == item.source_identifier,
                )
                .first()
            )

            if existing:
                continue

            discovered = DiscoveredContent(
                user_id=source.user_id,
                discovery_source_id=source.id,
                content_type=item.content_type,
                source_type=source.source_type,
                source_identifier=item.source_identifier,
                title=item.title,
                description=item.description,
                thumbnail_url=item.thumbnail_url,
                preview_metadata=item.metadata,
                discovery_reason="subscription",
                discovery_context={"source_name": source.display_name},
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            self.db.add(discovered)
            added_count += 1

        # Update last checked
        source.last_checked_at = datetime.utcnow()
        self.db.commit()

        # Emit notification if new content found
        if added_count > 0 and self.notifications:
            await self.notifications.emit(
                event_type_id="subscription.new_content",
                user_id=source.user_id,
                title=f"{added_count} new from {source.display_name}",
                action_url="/subscriptions",
                metadata={
                    "count": added_count,
                    "source_id": str(source.id),
                    "source_name": source.display_name,
                },
            )

        logger.info(f"Found {added_count} new items from source {source.id}")
        return added_count

    async def check_all_sources(self) -> Dict[str, int]:
        """
        Check all active sources that are due for checking.

        Returns:
            Dict of user_id -> new items count
        """
        now = datetime.utcnow()
        results = {}

        # Get sources due for checking
        sources = (
            self.db.query(DiscoverySource)
            .filter(DiscoverySource.is_active == True)  # noqa: E712
            .all()
        )

        for source in sources:
            # Check if due for check
            if source.last_checked_at:
                next_check = source.last_checked_at + timedelta(
                    hours=source.check_frequency_hours
                )
                if now < next_check:
                    continue

            count = await self.check_source(source)
            user_id_str = str(source.user_id)
            results[user_id_str] = results.get(user_id_str, 0) + count

        return results

    def get_discovered_content(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DiscoveredContent]:
        """Get discovered content for a user."""
        query = self.db.query(DiscoveredContent).filter(
            DiscoveredContent.user_id == user_id
        )

        if status:
            query = query.filter(DiscoveredContent.status == status)

        return (
            query.order_by(DiscoveredContent.discovered_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_pending_count(self, user_id: UUID) -> int:
        """Get count of pending discovered content."""
        return (
            self.db.query(DiscoveredContent)
            .filter(
                DiscoveredContent.user_id == user_id,
                DiscoveredContent.status == "pending",
            )
            .count()
        )

    def action_content(
        self,
        user_id: UUID,
        content_id: UUID,
        action: str,
    ) -> bool:
        """
        Take action on discovered content.

        Args:
            user_id: User UUID
            content_id: Content UUID
            action: import, dismiss

        Returns:
            True if action taken
        """
        content = (
            self.db.query(DiscoveredContent)
            .filter(
                DiscoveredContent.id == content_id,
                DiscoveredContent.user_id == user_id,
            )
            .first()
        )

        if not content:
            return False

        now = datetime.utcnow()

        if action == "dismiss":
            content.status = "dismissed"
            content.actioned_at = now
        elif action == "import":
            content.status = "imported"
            content.actioned_at = now
        else:
            return False

        self.db.commit()
        return True

    def bulk_action(
        self,
        user_id: UUID,
        content_ids: List[UUID],
        action: str,
    ) -> int:
        """
        Take action on multiple discovered content items.

        Returns:
            Number of items actioned
        """
        count = 0
        for content_id in content_ids:
            if self.action_content(user_id, content_id, action):
                count += 1
        return count

    def dismiss_all_pending(self, user_id: UUID) -> int:
        """Dismiss all pending discovered content."""
        now = datetime.utcnow()

        items = (
            self.db.query(DiscoveredContent)
            .filter(
                DiscoveredContent.user_id == user_id,
                DiscoveredContent.status == "pending",
            )
            .all()
        )

        for item in items:
            item.status = "dismissed"
            item.actioned_at = now

        self.db.commit()
        return len(items)

    def cleanup_expired(self) -> int:
        """
        Clean up expired discovered content.

        Returns:
            Number of items expired
        """
        now = datetime.utcnow()

        items = (
            self.db.query(DiscoveredContent)
            .filter(
                DiscoveredContent.status == "pending",
                DiscoveredContent.expires_at < now,
            )
            .all()
        )

        for item in items:
            item.status = "expired"
            item.actioned_at = now

        self.db.commit()
        logger.info(f"Expired {len(items)} discovered content items")
        return len(items)

    def update_interest_profile(
        self,
        user_id: UUID,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        topics: Optional[List[str]] = None,
    ) -> None:
        """
        Update user's interest profile based on imported content.

        Called after a video is imported to track interests.
        """
        profile = (
            self.db.query(UserInterestProfile)
            .filter(UserInterestProfile.user_id == user_id)
            .first()
        )

        if not profile:
            profile = UserInterestProfile(
                user_id=user_id,
                topics=[],
                channels=[],
                total_imports=0,
            )
            self.db.add(profile)

        profile.total_imports += 1
        profile.updated_at = datetime.utcnow()

        # Update channel interests
        if channel_id and channel_name:
            channels = profile.channels or []
            found = False
            for ch in channels:
                if ch.get("channel_id") == channel_id:
                    ch["import_count"] = ch.get("import_count", 0) + 1
                    ch["last_import"] = datetime.utcnow().isoformat()
                    found = True
                    break
            if not found:
                channels.append({
                    "channel_id": channel_id,
                    "name": channel_name,
                    "import_count": 1,
                    "last_import": datetime.utcnow().isoformat(),
                })
            profile.channels = channels

        # Update topic interests
        if topics:
            topic_data = profile.topics or []
            topic_map = {t["topic"]: t for t in topic_data}

            for topic in topics:
                if topic in topic_map:
                    topic_map[topic]["score"] = topic_map[topic].get("score", 0) + 1.0
                    topic_map[topic]["last_seen"] = datetime.utcnow().isoformat()
                else:
                    topic_map[topic] = {
                        "topic": topic,
                        "score": 1.0,
                        "last_seen": datetime.utcnow().isoformat(),
                    }

            profile.topics = list(topic_map.values())

        self.db.commit()



# Convenience function
def get_discovery_service(db: Session) -> DiscoveryService:
    """Get a DiscoveryService instance."""
    from app.services.notification_service import NotificationService
    return DiscoveryService(db, NotificationService(db))
