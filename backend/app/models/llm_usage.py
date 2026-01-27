"""
LLM usage tracking model for cost monitoring and analytics.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


# DeepSeek pricing (per million tokens)
DEEPSEEK_PRICING = {
    "deepseek-chat": {
        "input": Decimal("0.28"),
        "output": Decimal("0.42"),
        "cache_hit": Decimal("0.028"),
    },
    "deepseek-reasoner": {
        "input": Decimal("0.28"),
        "output": Decimal("0.42"),
        "cache_hit": Decimal("0.028"),
    },
}


def calculate_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
    cache_miss_tokens: int = 0,
) -> Decimal:
    """
    Calculate LLM cost based on token usage.

    Args:
        model: Model name (e.g., "deepseek-chat")
        input_tokens: Total input tokens (used if cache metrics not available)
        output_tokens: Output tokens generated
        cache_hit_tokens: Tokens served from cache (cheaper)
        cache_miss_tokens: Tokens not cached (full price)

    Returns:
        Cost in USD as Decimal
    """
    pricing = DEEPSEEK_PRICING.get(model, DEEPSEEK_PRICING["deepseek-chat"])

    # If cache metrics available, use them
    if cache_hit_tokens > 0 or cache_miss_tokens > 0:
        input_cost = (
            Decimal(cache_hit_tokens) * pricing["cache_hit"] / Decimal(1_000_000)
            + Decimal(cache_miss_tokens) * pricing["input"] / Decimal(1_000_000)
        )
    else:
        # Fallback to total input tokens
        input_cost = Decimal(input_tokens) * pricing["input"] / Decimal(1_000_000)

    output_cost = Decimal(output_tokens) * pricing["output"] / Decimal(1_000_000)

    return input_cost + output_cost


class LLMUsageEvent(Base):
    """
    LLM usage event for tracking API costs.

    Records every LLM call with token counts, cache metrics, and computed costs.
    Used for billing, analytics, and cost optimization.
    """

    __tablename__ = "llm_usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Model info
    model = Column(String(100), nullable=False, index=True)
    provider = Column(String(50), nullable=False, default="deepseek")

    # Token counts
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cache metrics (DeepSeek automatic caching)
    cache_hit_tokens = Column(Integer, nullable=False, default=0)
    cache_miss_tokens = Column(Integer, nullable=False, default=0)

    # Cost (in USD, 6 decimal places for precision)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)

    # Performance metrics
    response_time_seconds = Column(Numeric(10, 3), nullable=True)

    # Reasoning tokens (for deepseek-reasoner)
    reasoning_tokens = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="llm_usage_events")

    # Indexes for analytics queries
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_usage_model_created", "model", "created_at"),
    )

    def __repr__(self):
        return f"<LLMUsageEvent(id={self.id}, model={self.model}, cost=${self.cost_usd})>"

    @classmethod
    def create_from_response(
        cls,
        user_id: uuid.UUID,
        model: str,
        provider: str,
        usage: dict,
        conversation_id: uuid.UUID = None,
        message_id: uuid.UUID = None,
        response_time_seconds: float = None,
    ) -> "LLMUsageEvent":
        """
        Create LLM usage event from an LLM response.

        Args:
            user_id: User who made the request
            model: Model used
            provider: Provider name
            usage: Usage dict from LLM response
            conversation_id: Optional conversation ID
            message_id: Optional message ID
            response_time_seconds: Optional response time

        Returns:
            LLMUsageEvent instance (not yet committed)
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        cache_hit = usage.get("prompt_cache_hit_tokens", 0)
        cache_miss = usage.get("prompt_cache_miss_tokens", 0)

        cost = calculate_llm_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=cache_miss,
        )

        return cls(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=cache_miss,
            cost_usd=cost,
            response_time_seconds=Decimal(str(response_time_seconds)) if response_time_seconds else None,
        )
