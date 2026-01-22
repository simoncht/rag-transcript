"""
Subscription model for tracking user subscription history and Stripe data.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class Subscription(Base):
    """Subscription model - tracks subscription lifecycle and Stripe integration."""

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Stripe integration
    stripe_subscription_id = Column(String(255), unique=True, nullable=True, index=True)
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_price_id = Column(String(255), nullable=False)  # Stripe Price ID

    # Subscription details
    tier = Column(String(50), nullable=False)  # free, pro, enterprise
    status = Column(String(50), nullable=False)  # active, canceled, past_due, trialing

    # Billing period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Integer, default=0, nullable=False)  # Boolean as int
    canceled_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", backref="subscription_history")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, tier={self.tier}, status={self.status})>"
