"""
Celery tasks for content discovery.

Tasks:
- check_discovery_sources: Check all due sources for new content
- cleanup_expired_discoveries: Clean up expired discovered content
- generate_recommendations: Generate weekly recommendations for users
- send_notification_digests: Send email digest notifications
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

from celery import shared_task

from app.db.base import SessionLocal
from app.services.discovery_service import DiscoveryService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.discovery_tasks.check_discovery_sources",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def check_discovery_sources(self) -> Dict[str, int]:
    """
    Check all active discovery sources for new content.

    Runs hourly via Celery beat. Checks sources that are due for
    checking based on their check_frequency_hours setting.

    Returns:
        Dict mapping user_id to count of new items discovered
    """
    import asyncio

    logger.info("Starting discovery source check")
    db = SessionLocal()

    try:
        service = DiscoveryService(db, NotificationService(db))

        # Run async check in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(service.check_all_sources())
        finally:
            loop.close()

        total_items = sum(results.values())
        logger.info(
            f"Discovery check complete: {total_items} new items for {len(results)} users"
        )

        return results

    except Exception as e:
        logger.error(f"Discovery source check failed: {e}")
        self.retry(exc=e)
    finally:
        db.close()


@shared_task(name="app.tasks.discovery_tasks.cleanup_expired_discoveries")
def cleanup_expired_discoveries() -> int:
    """
    Clean up expired discovered content.

    Runs daily via Celery beat. Marks pending items as expired
    if their expires_at timestamp has passed.

    Returns:
        Number of items expired
    """
    logger.info("Starting expired discovery cleanup")
    db = SessionLocal()

    try:
        service = DiscoveryService(db)
        count = service.cleanup_expired()

        logger.info(f"Expired {count} discovered content items")
        return count

    except Exception as e:
        logger.error(f"Discovery cleanup failed: {e}")
        raise
    finally:
        db.close()


@shared_task(
    name="app.tasks.discovery_tasks.generate_recommendations",
    bind=True,
    max_retries=2,
)
def generate_recommendations(self, user_id: str = None) -> Dict[str, int]:
    """
    Generate recommendations for users.

    If user_id is provided, generates for that user only.
    Otherwise generates for all users with recommendations enabled.

    Runs weekly via Celery beat.

    Returns:
        Dict mapping user_id to count of recommendations generated
    """
    import asyncio

    from app.models import User
    from app.models.discovery import DiscoveredContent
    from app.services.recommendation_service import RecommendationEngine

    logger.info("Starting recommendation generation")
    db = SessionLocal()

    try:
        # Get users to generate for
        if user_id:
            users = db.query(User).filter(User.id == user_id).all()
        else:
            users = (
                db.query(User)
                .filter(
                    User.is_active == True,  # noqa: E712
                    User.recommendations_enabled == True,  # noqa: E712
                )
                .all()
            )

        engine = RecommendationEngine(db)
        notification_service = NotificationService(db)
        results = {}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for user in users:
                try:
                    recommendations = loop.run_until_complete(
                        engine.generate(user.id, limit=10)
                    )

                    # Store as discovered content
                    added = 0
                    for rec in recommendations:
                        # Check for existing
                        existing = (
                            db.query(DiscoveredContent)
                            .filter(
                                DiscoveredContent.user_id == user.id,
                                DiscoveredContent.source_identifier == rec.source_identifier,
                            )
                            .first()
                        )

                        if existing:
                            continue

                        discovered = DiscoveredContent(
                            user_id=user.id,
                            content_type="video",
                            source_type=rec.source_type,
                            source_identifier=rec.source_identifier,
                            title=rec.title,
                            description=rec.description,
                            thumbnail_url=rec.thumbnail_url,
                            preview_metadata=rec.context,
                            discovery_reason=rec.reason,
                            discovery_context=rec.context,
                            expires_at=datetime.utcnow() + timedelta(days=14),
                        )
                        db.add(discovered)
                        added += 1

                    db.commit()
                    results[str(user.id)] = added

                    # Emit notification if recommendations were added
                    if added > 0:
                        loop.run_until_complete(
                            notification_service.emit(
                                event_type_id="recommendation.weekly",
                                user_id=user.id,
                                title=f"{added} new recommendations for you",
                                body="Based on your interests, we found some videos you might like",
                                action_url="/subscriptions",
                                metadata={"count": added},
                            )
                        )

                except Exception as e:
                    logger.warning(f"Failed to generate recommendations for user {user.id}: {e}")
                    continue
        finally:
            loop.close()

        total = sum(results.values())
        logger.info(f"Generated {total} recommendations for {len(results)} users")

        return results

    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        self.retry(exc=e)
    finally:
        db.close()


@shared_task(name="app.tasks.discovery_tasks.send_notification_digests")
def send_notification_digests(frequency: str = "daily") -> Dict[str, int]:
    """
    Send notification digest emails.

    Batches unread notifications for users with email digest enabled
    and sends a summary email.

    Args:
        frequency: "daily" or "weekly"

    Returns:
        Dict mapping user_id to count of notifications included
    """
    from app.models import User
    from app.models.notification import Notification, NotificationDelivery

    logger.info(f"Starting {frequency} notification digest send")
    db = SessionLocal()

    try:
        # Get users with digest enabled for this frequency
        users = (
            db.query(User)
            .filter(
                User.is_active == True,  # noqa: E712
                User.email_digest_enabled == True,  # noqa: E712
                User.email_digest_frequency == frequency,
            )
            .all()
        )

        results = {}

        for user in users:
            # Get unread notifications with pending email delivery
            pending_deliveries = (
                db.query(NotificationDelivery)
                .join(Notification)
                .filter(
                    Notification.user_id == user.id,
                    NotificationDelivery.channel == "email",
                    NotificationDelivery.status == "pending",
                )
                .all()
            )

            if not pending_deliveries:
                continue

            # TODO: Actually send email digest
            # For now, just mark as sent
            for delivery in pending_deliveries:
                delivery.status = "sent"
                delivery.delivered_at = datetime.utcnow()

            db.commit()
            results[str(user.id)] = len(pending_deliveries)

            logger.info(f"Would send digest to {user.email} with {len(pending_deliveries)} items")

        total = sum(results.values())
        logger.info(f"Sent {frequency} digests to {len(results)} users with {total} total notifications")

        return results

    except Exception as e:
        logger.error(f"Notification digest send failed: {e}")
        raise
    finally:
        db.close()
