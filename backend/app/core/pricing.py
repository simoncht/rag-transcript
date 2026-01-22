"""
Pricing tier configuration for RAG Transcript SaaS.

Defines available subscription tiers, pricing, quotas, and features.
"""
from typing import Dict, Any, List

# Pricing tiers configuration
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
            "60 minutes of video per month",
            "Community support",
        ],
        "video_limit": 2,
        "message_limit": 50,
        "storage_limit_mb": 1000,
        "minutes_limit": 60,
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
            "Priority support",
            "Advanced analytics",
            "Export conversations",
        ],
        "video_limit": -1,  # -1 means unlimited
        "message_limit": -1,
        "storage_limit_mb": 50000,
        "minutes_limit": 1000,
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
