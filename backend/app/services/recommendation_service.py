"""
Recommendation service using strategy pattern.

Provides pluggable recommendation strategies:
- TopicMatchingStrategy: Based on user's topic interests
- ChannelFollowStrategy: From auto-followed channels
- TrendingStrategy: Popular content (future)
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.discovery import DiscoveredContent, UserInterestProfile, DiscoverySource
from app.providers.registry import provider_registry

logger = logging.getLogger(__name__)


class RecommendationItem:
    """A recommended content item."""

    def __init__(
        self,
        source_type: str,
        source_identifier: str,
        title: str,
        description: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        reason: str = "recommendation",
        context: Optional[Dict[str, Any]] = None,
        score: float = 1.0,
    ):
        self.source_type = source_type
        self.source_identifier = source_identifier
        self.title = title
        self.description = description
        self.thumbnail_url = thumbnail_url
        self.reason = reason
        self.context = context or {}
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_identifier": self.source_identifier,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "reason": self.reason,
            "context": self.context,
            "score": self.score,
        }


class RecommendationStrategy(ABC):
    """Base class for recommendation strategies."""

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Return the strategy type identifier."""
        pass

    @abstractmethod
    async def generate(
        self,
        user_id: UUID,
        db: Session,
        limit: int = 10,
    ) -> List[RecommendationItem]:
        """
        Generate recommendations for a user.

        Args:
            user_id: User UUID
            db: Database session
            limit: Maximum recommendations to return

        Returns:
            List of RecommendationItem
        """
        pass


class TopicMatchingStrategy(RecommendationStrategy):
    """Recommend based on user's topic interests."""

    @property
    def strategy_type(self) -> str:
        return "topic_match"

    async def generate(
        self,
        user_id: UUID,
        db: Session,
        limit: int = 10,
    ) -> List[RecommendationItem]:
        """Generate recommendations based on user's topic interests."""
        # Get user's interest profile
        profile = (
            db.query(UserInterestProfile)
            .filter(UserInterestProfile.user_id == user_id)
            .first()
        )

        if not profile or not profile.topics:
            return []

        # Get top topics by score
        topics = sorted(
            profile.topics,
            key=lambda t: t.get("score", 0),
            reverse=True,
        )[:5]

        if not topics:
            return []

        # Try to get YouTube provider
        try:
            provider = provider_registry.get_content_provider("youtube")
            if not provider.is_configured():
                logger.debug("YouTube provider not configured, skipping topic recommendations")
                return []
        except ValueError:
            return []

        results = []
        for topic_data in topics:
            topic = topic_data.get("topic", "")
            if not topic:
                continue

            try:
                search_results = await provider.search(topic, max_results=3)
                for result in search_results:
                    results.append(
                        RecommendationItem(
                            source_type="youtube",
                            source_identifier=result.id,
                            title=result.title,
                            description=result.description,
                            thumbnail_url=result.thumbnail_url,
                            reason="topic_match",
                            context={
                                "matched_topic": topic,
                                "topic_score": topic_data.get("score", 0),
                            },
                            score=topic_data.get("score", 1.0),
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to search for topic '{topic}': {e}")
                continue

        # Dedupe by source_identifier
        seen = set()
        deduped = []
        for item in results:
            if item.source_identifier not in seen:
                seen.add(item.source_identifier)
                deduped.append(item)

        # Sort by score and limit
        deduped.sort(key=lambda x: x.score, reverse=True)
        return deduped[:limit]


class ChannelFollowStrategy(RecommendationStrategy):
    """Recommend from auto-followed channels."""

    @property
    def strategy_type(self) -> str:
        return "channel_follow"

    async def generate(
        self,
        user_id: UUID,
        db: Session,
        limit: int = 10,
    ) -> List[RecommendationItem]:
        """Generate recommendations from auto-followed channels."""
        # Get auto-followed channels
        sources = (
            db.query(DiscoverySource)
            .filter(
                DiscoverySource.user_id == user_id,
                DiscoverySource.source_type == "youtube_channel",
                DiscoverySource.is_explicit == False,  # noqa: E712
                DiscoverySource.is_active == True,  # noqa: E712
            )
            .all()
        )

        if not sources:
            return []

        try:
            provider = provider_registry.get_discovery_provider("youtube_channel")
        except ValueError:
            return []

        results = []
        since = datetime.utcnow() - timedelta(days=7)

        for source in sources:
            try:
                new_items = await provider.check_for_new_content(
                    source.source_type,
                    source.source_identifier,
                    since,
                    source.config,
                )
                for item in new_items:
                    results.append(
                        RecommendationItem(
                            source_type=source.source_type,
                            source_identifier=item.source_identifier,
                            title=item.title,
                            description=item.description,
                            thumbnail_url=item.thumbnail_url,
                            reason="channel_follow",
                            context={"channel_name": source.display_name},
                            score=1.0,
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to get content from channel {source.source_identifier}: {e}")
                continue

        return results[:limit]


class RecommendationEngine:
    """
    Combines multiple recommendation strategies.

    Usage:
        engine = RecommendationEngine(db)
        recommendations = await engine.generate(user_id, limit=10)
    """

    def __init__(self, db: Session):
        self.db = db
        self.strategies: Dict[str, RecommendationStrategy] = {}

        # Register default strategies
        self.register_strategy(TopicMatchingStrategy())
        self.register_strategy(ChannelFollowStrategy())

    def register_strategy(self, strategy: RecommendationStrategy) -> None:
        """Register a recommendation strategy."""
        self.strategies[strategy.strategy_type] = strategy

    async def generate(
        self,
        user_id: UUID,
        strategies: Optional[List[str]] = None,
        limit: int = 10,
        diversity_factor: float = 0.2,
    ) -> List[RecommendationItem]:
        """
        Generate recommendations using specified strategies.

        Args:
            user_id: User UUID
            strategies: List of strategy types to use (None = all)
            limit: Maximum recommendations to return
            diversity_factor: Fraction of results to inject for diversity (0-1)

        Returns:
            List of RecommendationItem
        """
        strategies_to_use = strategies or list(self.strategies.keys())

        all_results = []
        strategies_used = []

        for strategy_type in strategies_to_use:
            if strategy_type not in self.strategies:
                continue

            strategy = self.strategies[strategy_type]
            try:
                results = await strategy.generate(user_id, self.db, limit)
                all_results.extend(results)
                if results:
                    strategies_used.append(strategy_type)
            except Exception as e:
                logger.error(f"Strategy {strategy_type} failed: {e}")
                continue

        # Filter out already imported content
        imported_ids = set(
            dc.source_identifier
            for dc in self.db.query(DiscoveredContent.source_identifier)
            .filter(
                DiscoveredContent.user_id == user_id,
                DiscoveredContent.status == "imported",
            )
            .all()
        )

        filtered = [r for r in all_results if r.source_identifier not in imported_ids]

        # Dedupe
        seen = set()
        deduped = []
        for item in filtered:
            if item.source_identifier not in seen:
                seen.add(item.source_identifier)
                deduped.append(item)

        # Sort by score
        deduped.sort(key=lambda x: x.score, reverse=True)

        # Apply diversity injection (mix strategies)
        final = self._apply_diversity(deduped, limit, diversity_factor)

        return final

    def _apply_diversity(
        self,
        items: List[RecommendationItem],
        limit: int,
        diversity_factor: float,
    ) -> List[RecommendationItem]:
        """
        Apply diversity injection to mix different recommendation sources.

        Ensures recommendations aren't dominated by a single strategy.
        """
        if not items or diversity_factor <= 0:
            return items[:limit]

        # Group by reason
        by_reason: Dict[str, List[RecommendationItem]] = {}
        for item in items:
            reason = item.reason
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(item)

        if len(by_reason) <= 1:
            return items[:limit]

        # Round-robin selection with diversity
        result = []
        reasons = list(by_reason.keys())
        idx = 0

        while len(result) < limit:
            reason = reasons[idx % len(reasons)]
            if by_reason[reason]:
                result.append(by_reason[reason].pop(0))
            idx += 1

            # Check if all sources exhausted
            if all(not v for v in by_reason.values()):
                break

        return result
