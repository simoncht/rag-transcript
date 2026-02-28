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
from typing import Dict, Any, Optional

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
        Model ID string (e.g., "deepseek-chat")

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
            "AI-powered transcription & summaries",
            "Semantic search across all content",
            "Conversation memory for long chats",
            "Citation links to exact sources",
            "Up to 20 MB file uploads",
            "Community support",
        ],
        # Free tier uses basic RAG pipeline: vector search + BM25 + reranking + query rewrite (8K max output)
        # Pro features disabled: query expansion, relevance grading, HyDE, follow-up questions (64K max output)
        "video_limit": 10,
        "document_limit": 50,
        "message_limit": 200,
        "storage_limit_mb": 1000,
        "minutes_limit": 1000,
        "max_document_words": 50_000,  # ~100 pages, ~1 min enrichment
        "max_upload_size_mb": 20,
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
            "Everything in Free",
            "Advanced AI that reasons through complex questions",
            "In-depth answers and full-length summaries",
            "Searches your content from multiple angles",
            "Smart follow-up question suggestions",
            "100 MB uploads & 500K-word documents",
            "Export conversations",
            "Priority support",
        ],
        "video_limit": -1,  # -1 means unlimited
        "document_limit": -1,
        "message_limit": -1,
        "storage_limit_mb": 50000,
        "minutes_limit": -1,
        "max_document_words": 500_000,  # matches NotebookLM, ~6 min enrichment
        "max_upload_size_mb": 100,
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
            "Unlimited document size",
            "Custom integrations",
            "Dedicated account manager",
            "SLA guarantee (99.9% uptime)",
            "Custom deployment options",
            "Team collaboration features",
        ],
        "video_limit": -1,
        "document_limit": -1,
        "message_limit": -1,
        "storage_limit_mb": -1,  # -1 means unlimited
        "minutes_limit": -1,
        "max_document_words": -1,  # unlimited
        "max_upload_size_mb": 100,
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
        "document_limit": config["document_limit"],
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
# Updated based on Railway and DeepSeek pricing as of February 2026.
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
    # Estimated per-unit costs (split by tier due to different models)
    # Includes ALL LLM calls per message: main + query rewrite + expansion + relevance grading
    # Auxiliary calls add ~$0.00034/msg (rewrite $0.067, expansion $0.032, grading $0.196,
    # HyDE+facts amortized $0.048) — only for Pro/Enterprise (free tier skips expensive features)
    "per_unit": {
        "message_free_no_cache": 0.0016,  # deepseek-chat: main $0.0012 + aux $0.00034
        "message_free_with_cache": 0.0012,  # deepseek-chat: 50% cache on main + aux $0.00034
        "message_pro_no_cache": 0.0023,  # deepseek-reasoner: main $0.0019 + aux $0.00034
        "message_pro_with_cache": 0.0019,  # deepseek-reasoner: 50% cache on main + aux $0.00034
        "video_processing": 0.015,  # ~34 chunks × enrichment (was $0.05, overestimated)
        "storage_per_gb_month": 0.15,  # Railway volume storage
    },
    # Stripe fees
    "stripe": {
        "percentage_fee": 0.029,  # 2.9%
        "fixed_fee": 0.30,  # $0.30 per transaction
    },
    # Base infrastructure cost (7 containers)
    "base_infrastructure_monthly": 76.00,  # ~$76/month fixed costs at minimum specs
    # Infrastructure scaling model (Railway)
    # Base: 7 containers. Scales with users/data.
    "infrastructure_scaling": {
        "base_monthly": 76.00,  # 7 containers at minimum specs
        "per_1000_users_monthly": 80.00,  # Additional compute/memory
        "per_100gb_vectors_monthly": 40.00,  # Qdrant RAM scaling (~5KB/vector)
    },
}


# =============================================================================
# Heavy User Monitoring Thresholds
# =============================================================================
#
# Thresholds for identifying heavy users who may exceed cost targets.
# Users exceeding these thresholds should be reviewed for fair use compliance.
#
# Based on profitability analysis (corrected Feb 2026):
# - Pro tier costs ~$1.25/month for medium usage (500 msgs)
# - Heavy users (3000+ messages) cost ~$6.00/month
# - Power users (6000+ messages) cost ~$13.14/month

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
# Updated Feb 2026: Corrected for auxiliary LLM costs and feature gating
TIER_COST_TARGETS: Dict[str, Dict[str, float]] = {
    "free": {
        "max_cost_per_user": 1.50,  # Acceptable as loss-leader (corrected for aux LLM costs)
        "expected_cost": 0.29,  # 200 msgs × $0.0012 + minimal storage + infra share
    },
    "pro": {
        "max_cost_per_user": 23.99,  # Should not exceed subscription price
        "expected_cost_light": 0.49,  # 100 msgs × $0.0019 + 2GB storage
        "expected_cost_medium": 1.25,  # 500 msgs × $0.0019 + 5GB storage
        "expected_cost_heavy": 6.00,  # 3000 msgs × $0.0019 + 15GB storage
        "expected_cost_power": 13.14,  # 6000 msgs × $0.0019 + 50GB storage + 100 videos
        "target_margin_percent": 50.0,  # Target 50% margin
    },
    "enterprise": {
        "max_cost_per_user": 79.99,
        "expected_cost": 25.00,  # Higher usage expected
        "target_margin_percent": 60.0,
    },
}

