"""
API endpoints for subscription management.

Endpoints:
- POST /subscriptions/checkout - Create Stripe checkout session
- POST /subscriptions/portal - Create Stripe customer portal session
- GET /subscriptions/quota - Get user quota usage
- GET /subscriptions/pricing - Get available pricing tiers
- GET /subscriptions/current - Get current subscription details
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.nextauth import get_current_user
from app.db.base import get_db
from app.models import User, Subscription
from app.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CustomerPortalRequest,
    CustomerPortalResponse,
    QuotaUsage,
    PricingTier,
    SubscriptionDetail,
)
from app.services.subscription import subscription_service
from app.main import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/checkout", response_model=CheckoutSessionResponse)
@limiter.limit("5/minute")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe checkout session for subscription purchase.

    Allows users to upgrade to Pro or Enterprise plans.
    """
    try:
        # Validate tier
        if request.tier == "free":
            raise HTTPException(
                status_code=400,
                detail="Cannot create checkout session for free tier"
            )

        # Determine billing cycle from tier request
        # Default to monthly if not specified in success_url
        billing_cycle = "monthly"
        if "yearly" in request.success_url.lower():
            billing_cycle = "yearly"

        # Create checkout session
        result = subscription_service.create_checkout_session(
            user=current_user,
            tier=request.tier,
            billing_cycle=billing_cycle,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            db=db,
        )

        logger.info(f"Created checkout session for user {current_user.id}: {result['session_id']}")

        return CheckoutSessionResponse(
            checkout_url=result["checkout_url"],
            session_id=result["session_id"],
        )

    except ValueError as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/portal", response_model=CustomerPortalResponse)
@limiter.limit("5/minute")
async def create_customer_portal_session(
    request: CustomerPortalRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe customer portal session for subscription management.

    Allows users to:
    - View billing history
    - Update payment method
    - Cancel subscription
    - Change plan
    """
    try:
        if not current_user.stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="No active subscription found. Please subscribe first."
            )

        # Create portal session
        result = subscription_service.create_customer_portal_session(
            user=current_user,
            return_url=request.return_url,
        )

        logger.info(f"Created customer portal session for user {current_user.id}")

        return CustomerPortalResponse(
            portal_url=result["portal_url"],
        )

    except ValueError as e:
        logger.error(f"Error creating customer portal session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating customer portal session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create customer portal session")


@router.get("/quota", response_model=QuotaUsage)
@limiter.limit("30/minute")
async def get_quota_usage(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current quota usage for the authenticated user.

    Returns:
    - Current usage for videos, messages, storage, and minutes
    - Quota limits based on subscription tier
    - Remaining quota for each category
    """
    try:
        quota = subscription_service.get_user_quota(current_user.id, db)

        logger.debug(f"Retrieved quota for user {current_user.id}: {quota.tier}")

        return quota

    except Exception as e:
        logger.error(f"Error retrieving quota for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve quota information")


@router.get("/pricing", response_model=List[PricingTier])
@limiter.limit("100/hour")
async def get_pricing_tiers(request: Request):
    """
    Get all available pricing tiers with their features and limits.

    Public endpoint - does not require authentication.
    """
    try:
        tiers = subscription_service.get_pricing_tiers()

        logger.debug(f"Retrieved {len(tiers)} pricing tiers")

        return tiers

    except Exception as e:
        logger.error(f"Error retrieving pricing tiers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve pricing information")


@router.get("/current", response_model=SubscriptionDetail, response_model_exclude_none=True)
@limiter.limit("30/minute")
async def get_current_subscription(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current subscription details for the authenticated user.

    Returns the most recent active subscription record.
    """
    try:
        # Get most recent subscription
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).order_by(Subscription.created_at.desc()).first()

        if not subscription:
            # User has no subscription record - return free tier info
            raise HTTPException(
                status_code=404,
                detail="No subscription found. User is on free tier."
            )

        logger.debug(f"Retrieved subscription for user {current_user.id}: {subscription.tier}")

        return subscription

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve subscription information")
