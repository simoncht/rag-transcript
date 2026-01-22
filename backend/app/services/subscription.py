"""
Subscription service for managing user subscriptions and quotas.

Handles:
- Quota calculation and enforcement
- Stripe checkout session creation
- Stripe customer portal access
- Subscription lifecycle management
- Webhook event processing
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import stripe
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.pricing import (
    get_tier_config,
    get_quota_limits,
    check_limit_exceeded,
    get_usage_percentage,
    PRICING_TIERS,
)
from app.models import User, Subscription, Video, UsageEvent, Transcript
from app.schemas import (
    QuotaUsage,
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionDetail,
    PricingTier,
)
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe with API key from settings
stripe.api_key = settings.stripe_api_key if hasattr(settings, 'stripe_api_key') else None


class SubscriptionService:
    """Service for managing subscriptions and quotas."""

    def get_user_quota(self, user_id: uuid.UUID, db: Session) -> QuotaUsage:
        """
        Calculate current quota usage for a user.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            QuotaUsage with current usage and limits
        """
        # Get user to determine tier
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Admin users get unlimited quotas regardless of subscription tier
        if user.is_superuser:
            limits = {
                "video_limit": -1,
                "message_limit": -1,
                "storage_limit_mb": -1,
                "minutes_limit": -1,
            }
            logger.info(f"Admin user {user_id} returning unlimited quota limits")
        else:
            # Get tier limits
            limits = get_quota_limits(user.subscription_tier)

        # Calculate videos used
        videos_used = db.query(func.count(Video.id)).filter(
            Video.user_id == user_id
        ).scalar() or 0

        # Calculate messages used (from usage_events)
        messages_used = db.query(func.count(UsageEvent.id)).filter(
            UsageEvent.user_id == user_id,
            UsageEvent.event_type == "message"
        ).scalar() or 0

        # Calculate storage used (sum of video file sizes)
        storage_query = db.query(func.sum(Video.audio_file_size_mb)).filter(
            Video.user_id == user_id
        ).scalar()
        storage_used_mb = float(storage_query) if storage_query else 0.0

        # Calculate video minutes used (sum of video durations)
        minutes_query = db.query(func.sum(Video.duration_seconds)).filter(
            Video.user_id == user_id
        ).scalar()
        minutes_used = int((minutes_query or 0) / 60)  # Convert seconds to minutes

        # Calculate remaining quotas
        videos_remaining = max(0, limits["video_limit"] - videos_used) if limits["video_limit"] != -1 else -1
        messages_remaining = max(0, limits["message_limit"] - messages_used) if limits["message_limit"] != -1 else -1
        storage_remaining_mb = max(0.0, limits["storage_limit_mb"] - storage_used_mb) if limits["storage_limit_mb"] != -1 else -1.0
        minutes_remaining = max(0, limits["minutes_limit"] - minutes_used) if limits["minutes_limit"] != -1 else -1

        return QuotaUsage(
            tier=user.subscription_tier,
            videos_used=videos_used,
            videos_limit=limits["video_limit"],
            videos_remaining=videos_remaining if videos_remaining != -1 else 999999,
            messages_used=messages_used,
            messages_limit=limits["message_limit"],
            messages_remaining=messages_remaining if messages_remaining != -1 else 999999,
            storage_used_mb=storage_used_mb,
            storage_limit_mb=limits["storage_limit_mb"],
            storage_remaining_mb=storage_remaining_mb if storage_remaining_mb != -1 else 999999.0,
            minutes_used=minutes_used,
            minutes_limit=limits["minutes_limit"],
            minutes_remaining=minutes_remaining if minutes_remaining != -1 else 999999,
        )

    def check_video_quota(self, user_id: uuid.UUID, db: Session) -> bool:
        """
        Check if user can ingest another video.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            True if allowed, False if quota exceeded
        """
        quota = self.get_user_quota(user_id, db)
        return quota.videos_remaining > 0

    def check_message_quota(self, user_id: uuid.UUID, db: Session) -> bool:
        """
        Check if user can send another message.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            True if allowed, False if quota exceeded
        """
        quota = self.get_user_quota(user_id, db)
        return quota.messages_remaining > 0

    def check_storage_quota(self, user_id: uuid.UUID, file_size_mb: float, db: Session) -> bool:
        """
        Check if user has enough storage quota for a file.

        Args:
            user_id: User ID
            file_size_mb: Size of file to upload in MB
            db: Database session

        Returns:
            True if allowed, False if quota exceeded
        """
        quota = self.get_user_quota(user_id, db)
        return quota.storage_remaining_mb >= file_size_mb

    def check_minutes_quota(self, user_id: uuid.UUID, duration_minutes: int, db: Session) -> bool:
        """
        Check if user has enough minutes quota for a video.

        Args:
            user_id: User ID
            duration_minutes: Video duration in minutes
            db: Database session

        Returns:
            True if allowed, False if quota exceeded
        """
        quota = self.get_user_quota(user_id, db)
        return quota.minutes_remaining >= duration_minutes

    def create_checkout_session(
        self,
        user: User,
        tier: str,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
        db: Session,
    ) -> Dict[str, str]:
        """
        Create a Stripe checkout session for subscription purchase.

        Args:
            user: User object
            tier: Subscription tier (pro, enterprise)
            billing_cycle: "monthly" or "yearly"
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            db: Database session

        Returns:
            Dictionary with checkout_url and session_id
        """
        if not stripe.api_key:
            raise ValueError("Stripe API key not configured")

        # Get tier configuration
        tier_config = get_tier_config(tier)

        # Get Stripe price ID based on billing cycle
        if billing_cycle == "monthly":
            price_id = tier_config["stripe_price_id_monthly"]
        elif billing_cycle == "yearly":
            price_id = tier_config["stripe_price_id_yearly"]
        else:
            raise ValueError(f"Invalid billing cycle: {billing_cycle}")

        if not price_id:
            raise ValueError(f"Stripe price ID not configured for {tier} {billing_cycle}")

        # Create or get Stripe customer
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={"user_id": str(user.id)},
            )
            customer_id = customer.id
            user.stripe_customer_id = customer_id
            db.commit()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "tier": tier,
            },
        )

        logger.info(f"Created Stripe checkout session for user {user.id}: {session.id}")

        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }

    def create_customer_portal_session(
        self,
        user: User,
        return_url: str,
    ) -> Dict[str, str]:
        """
        Create a Stripe customer portal session for subscription management.

        Args:
            user: User object
            return_url: URL to return to after managing subscription

        Returns:
            Dictionary with portal_url
        """
        if not stripe.api_key:
            raise ValueError("Stripe API key not configured")

        if not user.stripe_customer_id:
            raise ValueError("User does not have a Stripe customer ID")

        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )

        logger.info(f"Created Stripe customer portal session for user {user.id}")

        return {
            "portal_url": session.url,
        }

    def handle_checkout_completed(
        self,
        session: Dict[str, Any],
        db: Session,
    ) -> None:
        """
        Handle successful checkout session completion.

        Args:
            session: Stripe checkout session object
            db: Database session
        """
        user_id = uuid.UUID(session["metadata"]["user_id"])
        tier = session["metadata"]["tier"]

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found for checkout session: {user_id}")
            return

        # Update user subscription
        user.subscription_tier = tier
        user.subscription_status = "active"

        # Get subscription ID from Stripe
        subscription_id = session.get("subscription")

        if subscription_id:
            # Fetch subscription details from Stripe
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)

            # Create subscription record
            subscription = Subscription(
                user_id=user_id,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=session["customer"],
                stripe_price_id=stripe_subscription["items"]["data"][0]["price"]["id"],
                tier=tier,
                status="active",
                current_period_start=datetime.fromtimestamp(stripe_subscription["current_period_start"]),
                current_period_end=datetime.fromtimestamp(stripe_subscription["current_period_end"]),
                cancel_at_period_end=0,
            )
            db.add(subscription)

        db.commit()

        logger.info(f"Checkout completed for user {user_id}: upgraded to {tier}")

    def handle_subscription_updated(
        self,
        subscription_data: Dict[str, Any],
        db: Session,
    ) -> None:
        """
        Handle subscription update event from Stripe.

        Args:
            subscription_data: Stripe subscription object
            db: Database session
        """
        stripe_subscription_id = subscription_data["id"]

        # Find subscription record
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()

        if not subscription:
            logger.warning(f"Subscription not found: {stripe_subscription_id}")
            return

        # Update subscription
        subscription.status = subscription_data["status"]
        subscription.current_period_start = datetime.fromtimestamp(subscription_data["current_period_start"])
        subscription.current_period_end = datetime.fromtimestamp(subscription_data["current_period_end"])
        subscription.cancel_at_period_end = 1 if subscription_data.get("cancel_at_period_end") else 0

        if subscription_data.get("canceled_at"):
            subscription.canceled_at = datetime.fromtimestamp(subscription_data["canceled_at"])

        # Update user
        user = db.query(User).filter(User.id == subscription.user_id).first()
        if user:
            user.subscription_status = subscription_data["status"]

            # If canceled, revert to free tier at period end
            if subscription.cancel_at_period_end:
                logger.info(f"Subscription will cancel at period end for user {user.id}")

        db.commit()

        logger.info(f"Subscription updated: {stripe_subscription_id} - status: {subscription_data['status']}")

    def handle_subscription_deleted(
        self,
        subscription_data: Dict[str, Any],
        db: Session,
    ) -> None:
        """
        Handle subscription deletion event from Stripe.

        Args:
            subscription_data: Stripe subscription object
            db: Database session
        """
        stripe_subscription_id = subscription_data["id"]

        # Find subscription record
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()

        if not subscription:
            logger.warning(f"Subscription not found for deletion: {stripe_subscription_id}")
            return

        # Update subscription status
        subscription.status = "canceled"
        subscription.canceled_at = datetime.utcnow()

        # Downgrade user to free tier
        user = db.query(User).filter(User.id == subscription.user_id).first()
        if user:
            user.subscription_tier = "free"
            user.subscription_status = "canceled"

        db.commit()

        logger.info(f"Subscription deleted for user {subscription.user_id}: reverted to free tier")

    def get_pricing_tiers(self) -> list[PricingTier]:
        """
        Get all available pricing tiers.

        Returns:
            List of PricingTier objects
        """
        tiers = []
        for tier_name, config in PRICING_TIERS.items():
            tiers.append(
                PricingTier(
                    tier=tier_name,
                    name=config["name"],
                    price_monthly=config["price_monthly"],
                    price_yearly=config["price_yearly"],
                    stripe_price_id_monthly=config.get("stripe_price_id_monthly", ""),
                    stripe_price_id_yearly=config.get("stripe_price_id_yearly", ""),
                    features=config["features"],
                    video_limit=config["video_limit"],
                    message_limit=config["message_limit"],
                    storage_limit_mb=config["storage_limit_mb"],
                    minutes_limit=config["minutes_limit"],
                )
            )
        return tiers


# Global service instance
subscription_service = SubscriptionService()
