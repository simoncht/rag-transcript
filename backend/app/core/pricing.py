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
            "2 videos",
            "50 messages per month",
            "1GB storage",
            "1000 minutes of video per month",
            "DeepSeek Chat model (fast responses)",
            "Community support",
        ],
        "video_limit": 2,
        "message_limit": 50,
        "storage_limit_mb": 1000,
        "minutes_limit": 1000,
        "model_tier": "free",
    },
    "pro": {
        "name": "Pro",
        "description": "For power users and professionals",
        "price_monthly": 2000,  # $20.00 in cents
        "price_yearly": 20000,  # $200.00 in cents ($16.67/month)
        "stripe_price_id_monthly": "price_1Sr9hZRmTkZwB6fL9IH117SW",
        "stripe_price_id_yearly": "price_1Sr9hgRmTkZwB6fLEex5Pf6S",
        "features": [
            "Unlimited videos",
            "Unlimited messages",
            "50GB storage",
            "1,000 minutes of video per month",
            "DeepSeek Reasoner (advanced reasoning)",
            "Priority support",
            "Advanced analytics",
            "Export conversations",
        ],
        "video_limit": -1,  # -1 means unlimited
        "message_limit": -1,
        "storage_limit_mb": 50000,
        "minutes_limit": 1000,
        "model_tier": "pro",
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "For teams and organizations",
        "price_monthly": 10000,  # $100.00 in cents
        "price_yearly": 100000,  # $1,000.00 in cents ($83.33/month)
        "stripe_price_id_monthly": "price_1Sr9hxRmTkZwB6fL2zacqIkU",
        "stripe_price_id_yearly": "price_1Sr9i3RmTkZwB6fLi01443us",
        "features": [
            "Everything in Pro",
            "Unlimited storage",
            "Unlimited video minutes",
            "DeepSeek Reasoner (enterprise SLA)",
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
