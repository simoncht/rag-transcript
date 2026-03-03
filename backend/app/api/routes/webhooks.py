"""
Webhook endpoints.

Currently supports Stripe subscription webhooks.
"""
from fastapi import APIRouter, HTTPException, Request, status
from app.core.config import settings
from app.db.base import SessionLocal
from app.core.rate_limit import limiter
from app.services.subscription import subscription_service
import stripe
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
@limiter.limit("200/minute")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks for subscription lifecycle events.

    Processes events:
    - checkout.session.completed: User completed payment
    - customer.subscription.created: Subscription created
    - customer.subscription.updated: Subscription updated (status, plan, etc.)
    - customer.subscription.deleted: Subscription canceled
    - invoice.payment_succeeded: Payment successful
    - invoice.payment_failed: Payment failed
    """
    if not hasattr(settings, 'stripe_webhook_secret') or not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid Stripe webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe webhook signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e

    # Get event type and data
    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    # Handle events
    with SessionLocal() as db:
        try:
            if event_type == "checkout.session.completed":
                # Payment successful, create subscription
                subscription_service.handle_checkout_completed(event_data, db)

            elif event_type == "customer.subscription.created":
                # Subscription created (handled by checkout.session.completed)
                logger.info(f"Subscription created: {event_data['id']}")

            elif event_type == "customer.subscription.updated":
                # Subscription updated (status change, plan change, etc.)
                subscription_service.handle_subscription_updated(event_data, db)

            elif event_type == "customer.subscription.deleted":
                # Subscription canceled
                subscription_service.handle_subscription_deleted(event_data, db)

            elif event_type == "invoice.payment_succeeded":
                # Payment succeeded - subscription renewed
                logger.info(f"Payment succeeded for subscription: {event_data.get('subscription')}")

            elif event_type == "invoice.payment_failed":
                # Payment failed - mark subscription as past_due
                subscription_service.handle_payment_failed(event_data, db)

            else:
                # Log unhandled event type
                logger.debug(f"Unhandled Stripe event type: {event_type}")

        except (KeyError, ValueError, TypeError) as e:
            # Permanent errors (bad data shape) — return 200 so Stripe doesn't retry
            logger.error(
                f"Permanent error processing Stripe webhook {event_type}: {str(e)}",
                exc_info=True,
            )
        except Exception as e:
            # Transient errors (DB down, network issue) — return 500 so Stripe retries
            logger.error(
                f"Transient error processing Stripe webhook {event_type}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed, please retry",
            ) from e

    return {"status": "ok"}
