"""
Pricing tier configuration for RAG Transcript SaaS.

Defines available subscription tiers, pricing, quotas, features, and LLM model assignments.

Model Tier Configuration (DeepSeek API):
- Free tier uses deepseek-chat: Fast responses, 128K context, $0.28/M in, $0.42/M out
- Paid tiers use deepseek-reasoner: Advanced reasoning with chain-of-thought, 128K context

DeepSeek automatically caches prompt prefixes (system prompt, conversation history),
reducing input costs by up to 90% for long conversations ($0.028/M for cache hits).

See docs/MODEL_RESEARCH.md for detailed analysis.
"""
from typing import Dict, Any, List, Optional

from app.core.config import settings


# =============================================================================
# LLM Model Configuration by Tier (DeepSeek API)
# =============================================================================
#
# DeepSeek models for RAG transcript processing:
#
# | Model             | Context | Max Output | Pricing (per M tokens)        |
# |-------------------|---------|------------|-------------------------------|
# | deepseek-chat     | 128K    | 8K         | $0.28 in / $0.42 out         |
# | deepseek-reasoner | 128K    | 64K        | $0.28 in / $0.42 out         |
#
# Cache pricing: $0.028/M (10x cheaper for automatic prefix cache hits)
#
# Key benefits:
# - OpenAI-compatible API (easy integration)
# - Automatic context caching (reduces costs for multi-turn conversations)
# - Reasoner model provides chain-of-thought for complex queries

MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    "free": {
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek Chat",
        "description": "Fast responses for most queries",
        "specs": {
            "provider": "deepseek",
            "context_length": 128000,
            "max_output": 8000,
            "pricing_input": "$0.28/M",
            "pricing_output": "$0.42/M",
            "pricing_cache_hit": "$0.028/M",
            "strengths": ["Fast inference", "Low latency", "Cost effective"],
            "limitations": ["No chain-of-thought reasoning"],
        },
    },
    "pro": {
        "model_id": "deepseek-reasoner",
        "display_name": "DeepSeek Reasoner",
        "description": "Advanced reasoning for complex analysis",
        "specs": {
            "provider": "deepseek",
            "context_length": 128000,
            "max_output": 64000,
            "has_reasoning": True,
            "pricing_input": "$0.28/M",
            "pricing_output": "$0.42/M",
            "pricing_cache_hit": "$0.028/M",
            "strengths": ["Chain-of-thought reasoning", "Complex analysis", "Long output"],
            "limitations": ["Slightly slower due to reasoning step"],
        },
    },
    "enterprise": {
        "model_id": "deepseek-reasoner",
        "display_name": "DeepSeek Reasoner (Enterprise)",
        "description": "Enterprise-grade with SLA",
        "specs": {
            "provider": "deepseek",
            "context_length": 128000,
            "max_output": 64000,
            "has_reasoning": True,
            "pricing_input": "$0.28/M",
            "pricing_output": "$0.42/M",
            "pricing_cache_hit": "$0.028/M",
            "strengths": ["Chain-of-thought reasoning", "Complex analysis", "Enterprise SLA"],
            "limitations": ["Slightly slower due to reasoning step"],
        },
    },
}


def get_model_for_tier(tier: str) -> str:
    """
    Get the default LLM model ID for a subscription tier.

    Checks environment-configured overrides first (settings.llm_model_{tier}),
    then falls back to MODEL_TIERS defaults.

    Args:
        tier: Subscription tier (free, pro, enterprise)

    Returns:
        Model ID string in Ollama format (e.g., "qwen3-vl:235b")

    Raises:
        ValueError: If tier is invalid
    """
    # Check for environment override first
    env_model = getattr(settings, f"llm_model_{tier}", None)
    if env_model:
        return env_model

    if tier not in MODEL_TIERS:
        # Fallback to free tier model if unknown tier
        return MODEL_TIERS["free"]["model_id"]

    return MODEL_TIERS[tier]["model_id"]


def get_model_info_for_tier(tier: str) -> Dict[str, Any]:
    """
    Get full model information for a subscription tier.

    Args:
        tier: Subscription tier (free, pro, enterprise)

    Returns:
        Dictionary with model_id, display_name, description, and specs
    """
    if tier not in MODEL_TIERS:
        return MODEL_TIERS["free"]

    return MODEL_TIERS[tier]


def resolve_model(
    user_tier: str,
    requested_model: Optional[str] = None,
    allow_upgrade: bool = False,
) -> str:
    """
    Resolve which model to use based on user tier and optional override.

    If a model is explicitly requested:
    - If allow_upgrade=False (default): Only allow the tier's assigned model
    - If allow_upgrade=True: Allow any model (for admin/testing purposes)

    Args:
        user_tier: User's subscription tier
        requested_model: Optional explicit model request from API
        allow_upgrade: Whether to allow model upgrades beyond tier

    Returns:
        Model ID to use for the request
    """
    tier_model = get_model_for_tier(user_tier)

    if not requested_model:
        return tier_model

    if allow_upgrade:
        return requested_model

    # For now, allow explicit model requests (future: enforce tier limits)
    # This enables testing different models while preserving tier defaults
    return requested_model


# =============================================================================
# Pricing Tiers Configuration
# =============================================================================

PRICING_TIERS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "description": "Perfect for getting started",
        "price_monthly": 0,
        "price_yearly": 0,
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
        "features": [
            "10 videos",
            "200 messages per month",
            "1GB storage",
            "1000 minutes of video per month",
            "AI-powered summaries",
            "Conversation memory for long chats",
            "Community support",
        ],
        "video_limit": 10,
        "message_limit": 200,
        "storage_limit_mb": 1000,
        "minutes_limit": 1000,
        "model_tier": "free",
    },
    "pro": {
        "name": "Pro",
        "description": "For power users and professionals",
        "price_monthly": 2399,  # $23.99 in cents
        "price_yearly": 22999,  # $229.99 in cents ($19.17/month, 20% off)
        "stripe_price_id_monthly": "price_1SugDfRmTkZwB6fLSa2jHi9B",
        "stripe_price_id_yearly": "price_1SugDlRmTkZwB6fLQRsvGWqN",
        "features": [
            "Unlimited videos",
            "Unlimited messages",
            "Unlimited video minutes",
            "50GB storage",
            "AI with step-by-step reasoning",
            "Conversation memory for long chats",
            "Priority support",
            "Advanced analytics",
            "Export conversations",
        ],
        "video_limit": -1,  # -1 means unlimited
        "message_limit": -1,
        "storage_limit_mb": 50000,
        "minutes_limit": -1,
        "model_tier": "pro",
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "For teams and organizations",
        "price_monthly": 7999,  # $79.99 in cents
        "price_yearly": 79999,  # $799.99 in cents ($66.67/month, 17% off)
        "stripe_price_id_monthly": "price_1SugDnRmTkZwB6fLFOyPjWIK",
        "stripe_price_id_yearly": "price_1SugDoRmTkZwB6fLgO05P9wH",
        "features": [
            "Everything in Pro",
            "Unlimited storage",
            "Unlimited video minutes",
            "AI with step-by-step reasoning",
            "Conversation memory for long chats",
            "Custom integrations",
            "Dedicated account manager",
            "SLA guarantee (99.9% uptime)",
            "Custom deployment options",
            "Team collaboration features",
        ],
        "video_limit": -1,
        "message_limit": -1,
        "storage_limit_mb": -1,  # -1 means unlimited
        "minutes_limit": -1,
        "model_tier": "enterprise",
    },
}


def get_tier_config(tier: str) -> Dict[str, Any]:
    """
    Get configuration for a specific tier.

    Args:
        tier: Tier name (free, pro, enterprise)

    Returns:
        Tier configuration dictionary

    Raises:
        ValueError: If tier is invalid
    """
    if tier not in PRICING_TIERS:
        raise ValueError(f"Invalid tier: {tier}. Must be one of: {list(PRICING_TIERS.keys())}")

    return PRICING_TIERS[tier]


def get_all_tiers() -> List[Dict[str, Any]]:
    """
    Get all pricing tiers with their configurations.

    Returns:
        List of tier configurations
    """
    return [
        {"tier": tier, **config}
        for tier, config in PRICING_TIERS.items()
    ]


def get_quota_limits(tier: str) -> Dict[str, int]:
    """
    Get quota limits for a specific tier.

    Args:
        tier: Tier name (free, pro, enterprise)

    Returns:
        Dictionary with quota limits
    """
    config = get_tier_config(tier)

    return {
        "video_limit": config["video_limit"],
        "message_limit": config["message_limit"],
        "storage_limit_mb": config["storage_limit_mb"],
        "minutes_limit": config["minutes_limit"],
    }


def is_unlimited(limit: int) -> bool:
    """
    Check if a limit is unlimited.

    Args:
        limit: Limit value

    Returns:
        True if unlimited (limit == -1)
    """
    return limit == -1


def check_limit_exceeded(used: int, limit: int) -> bool:
    """
    Check if a quota limit has been exceeded.

    Args:
        used: Current usage
        limit: Maximum limit (-1 for unlimited)

    Returns:
        True if limit exceeded, False otherwise
    """
    if is_unlimited(limit):
        return False

    return used >= limit


def get_usage_percentage(used: int, limit: int) -> float:
    """
    Calculate usage percentage.

    Args:
        used: Current usage
        limit: Maximum limit (-1 for unlimited)

    Returns:
        Usage percentage (0-100), or 0 for unlimited
    """
    if is_unlimited(limit):
        return 0.0

    if limit == 0:
        return 100.0

    return min((used / limit) * 100, 100.0)


# Quota warning thresholds (percentages)
QUOTA_WARNING_THRESHOLD_LOW = 80.0  # Send warning at 80%
QUOTA_WARNING_THRESHOLD_HIGH = 90.0  # Send urgent warning at 90%
QUOTA_WARNING_THRESHOLD_CRITICAL = 100.0  # Send critical warning at 100%


# =============================================================================
# Cost Tracking Configuration (Internal)
# =============================================================================
#
# These values are used for internal cost monitoring and profitability analysis.
# Updated based on Railway and DeepSeek pricing as of January 2025.
#
# Sources:
# - Railway: https://docs.railway.com/reference/pricing/plans
# - DeepSeek: https://api-docs.deepseek.com/quick_start/pricing

COST_CONFIG: Dict[str, Any] = {
    # Railway infrastructure costs
    "infrastructure": {
        "cpu_per_vcpu_month": 20.00,  # $0.000463/vCPU/min ≈ $20/vCPU/month
        "memory_per_gb_month": 10.00,  # $0.000231/GB/min ≈ $10/GB/month
        "storage_per_gb_month": 0.15,  # $0.15/GB/month
        "egress_per_gb": 0.05,  # $0.05/GB
    },
    # DeepSeek API costs (per million tokens)
    "deepseek": {
        "input_per_million": 0.28,  # $0.28/M tokens
        "input_cache_hit_per_million": 0.028,  # $0.028/M tokens (90% cheaper)
        "output_per_million": 0.42,  # $0.42/M tokens
    },
    # Estimated per-unit costs
    "per_unit": {
        "message_no_cache": 0.0016,  # ~$0.0016/message (5100 in + 500 out, no cache)
        "message_with_cache": 0.0010,  # ~$0.0010/message (50% cache hit rate)
        "video_processing": 0.05,  # ~$0.05/video (transcription + chunking + embedding)
        "storage_per_gb_month": 0.15,  # Railway volume storage
    },
    # Stripe fees
    "stripe": {
        "percentage_fee": 0.029,  # 2.9%
        "fixed_fee": 0.30,  # $0.30 per transaction
    },
    # Base infrastructure cost (7 containers)
    "base_infrastructure_monthly": 100.00,  # ~$100/month fixed costs
}


# =============================================================================
# Heavy User Monitoring Thresholds
# =============================================================================
#
# Thresholds for identifying heavy users who may exceed cost targets.
# Users exceeding these thresholds should be reviewed for fair use compliance.
#
# Based on profitability analysis:
# - Pro tier costs ~$7.30/month for medium usage
# - Heavy users (2000+ messages) cost ~$23.70/month (exceeds $20 price)

HEAVY_USER_THRESHOLDS: Dict[str, Dict[str, int]] = {
    "pro": {
        "messages_per_month": 2000,  # Flag users with >2000 messages/month
        "videos_per_month": 200,  # Flag users processing >200 videos/month
        "storage_used_gb": 40,  # Flag users using >40GB (80% of limit)
    },
    "enterprise": {
        "messages_per_month": 10000,  # Higher threshold for enterprise
        "videos_per_month": 1000,
        "storage_used_gb": 200,
    },
}


# Per-tier profitability targets (monthly)
# Updated January 2025: Pro tier increased to $23.99, Enterprise to $99.99
TIER_COST_TARGETS: Dict[str, Dict[str, float]] = {
    "free": {
        "max_cost_per_user": 1.25,  # Acceptable as loss-leader (updated for 200 messages)
        "expected_cost": 0.91,  # Typical free user cost with 200 messages
    },
    "pro": {
        "max_cost_per_user": 23.99,  # Should not exceed subscription price
        "expected_cost_light": 2.41,  # Light user (20 videos, 100 messages) - 90% margin
        "expected_cost_medium": 7.30,  # Medium user (50 videos, 500 messages) - 70% margin
        "expected_cost_heavy": 23.70,  # Heavy user (200 videos, 2000 messages) - ~break-even
        "target_margin_percent": 50.0,  # Target 50% margin
    },
    "enterprise": {
        "max_cost_per_user": 79.99,
        "expected_cost": 50.00,  # Higher usage expected
        "target_margin_percent": 50.0,
    },
}


def estimate_user_cost(
    messages: int,
    videos: int,
    storage_gb: float,
    cache_hit_rate: float = 0.5,
) -> float:
    """
    Estimate monthly cost for a user based on usage.

    Args:
        messages: Number of messages sent
        videos: Number of videos processed
        storage_gb: Storage used in GB
        cache_hit_rate: Estimated DeepSeek cache hit rate (0-1)

    Returns:
        Estimated cost in dollars
    """
    per_unit = COST_CONFIG["per_unit"]

    # Message cost (weighted by cache hit rate)
    message_cost = messages * (
        per_unit["message_no_cache"] * (1 - cache_hit_rate)
        + per_unit["message_with_cache"] * cache_hit_rate
    )

    # Video processing cost (one-time per video)
    video_cost = videos * per_unit["video_processing"]

    # Storage cost
    storage_cost = storage_gb * per_unit["storage_per_gb_month"]

    # Infrastructure share (simplified allocation)
    # Assumes costs are distributed across active users
    infra_share = 0.50  # Base allocation per active user

    return message_cost + video_cost + storage_cost + infra_share


def check_heavy_user(
    tier: str,
    messages: int,
    videos: int,
    storage_gb: float,
) -> Dict[str, bool]:
    """
    Check if user exceeds heavy usage thresholds.

    Args:
        tier: User's subscription tier
        messages: Messages sent this month
        videos: Videos processed this month
        storage_gb: Storage used in GB

    Returns:
        Dictionary with exceeded flags for each metric
    """
    if tier not in HEAVY_USER_THRESHOLDS:
        return {"messages": False, "videos": False, "storage": False}

    thresholds = HEAVY_USER_THRESHOLDS[tier]

    return {
        "messages": messages > thresholds["messages_per_month"],
        "videos": videos > thresholds["videos_per_month"],
        "storage": storage_gb > thresholds["storage_used_gb"],
        "any_exceeded": (
            messages > thresholds["messages_per_month"]
            or videos > thresholds["videos_per_month"]
            or storage_gb > thresholds["storage_used_gb"]
        ),
    }


def calculate_stripe_net(gross_amount: float) -> float:
    """
    Calculate net amount after Stripe fees.

    Args:
        gross_amount: Gross payment amount in dollars

    Returns:
        Net amount after Stripe fees
    """
    fees = COST_CONFIG["stripe"]
    stripe_fee = (gross_amount * fees["percentage_fee"]) + fees["fixed_fee"]
    return gross_amount - stripe_fee


def get_pro_net_revenue() -> float:
    """Get net revenue from Pro subscription after Stripe fees."""
    pro_price = PRICING_TIERS["pro"]["price_monthly"] / 100  # Convert cents to dollars
    return calculate_stripe_net(pro_price)
