"""
Pydantic schemas for subscription operations.
"""
import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# Subscription tiers and pricing
SubscriptionTier = Literal["free", "pro", "enterprise"]
SubscriptionStatus = Literal["active", "canceled", "past_due", "trialing", "incomplete"]


class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    tier: SubscriptionTier
    status: SubscriptionStatus


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""
    user_id: uuid.UUID
    tier: SubscriptionTier
    stripe_customer_id: str
    stripe_price_id: str
    stripe_subscription_id: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""
    status: Optional[SubscriptionStatus] = None
    tier: Optional[SubscriptionTier] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    canceled_at: Optional[datetime] = None


class SubscriptionDetail(SubscriptionBase):
    """Detailed subscription information."""
    id: uuid.UUID
    user_id: uuid.UUID
    stripe_subscription_id: Optional[str]
    stripe_customer_id: str
    stripe_price_id: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Stripe checkout schemas
class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session."""
    tier: SubscriptionTier = Field(..., description="Subscription tier to purchase")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is canceled")


class CheckoutSessionResponse(BaseModel):
    """Response containing Stripe checkout session details."""
    checkout_url: str = Field(..., description="URL to redirect user to Stripe checkout")
    session_id: str = Field(..., description="Stripe checkout session ID")


# Customer portal schema
class CustomerPortalRequest(BaseModel):
    """Request to create a Stripe customer portal session."""
    return_url: str = Field(..., description="URL to return to after managing subscription")


class CustomerPortalResponse(BaseModel):
    """Response containing Stripe customer portal details."""
    portal_url: str = Field(..., description="URL to redirect user to Stripe customer portal")


# Quota schemas
class QuotaUsage(BaseModel):
    """Current quota usage for a user."""
    tier: SubscriptionTier

    # Video quotas
    videos_used: int
    videos_limit: int
    videos_remaining: int

    # Message quotas
    messages_used: int
    messages_limit: int
    messages_remaining: int

    # Storage quotas (in MB)
    storage_used_mb: float
    storage_limit_mb: int
    storage_remaining_mb: float

    # Video minutes
    minutes_used: int
    minutes_limit: int
    minutes_remaining: int


# Pricing tier information
class PricingTier(BaseModel):
    """Pricing tier details for display."""
    tier: SubscriptionTier
    name: str
    price_monthly: int  # in cents
    price_yearly: int  # in cents
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None
    features: list[str]
    video_limit: int
    message_limit: int
    storage_limit_mb: int
    minutes_limit: int
