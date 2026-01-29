"""
Unit tests for pricing configuration.

Tests that tier limits, pricing, and Stripe configuration are correct.
"""
import pytest

from app.core.pricing import (
    get_tier_config,
    get_quota_limits,
    is_unlimited,
    check_limit_exceeded,
    get_usage_percentage,
    PRICING_TIERS,
)


class TestPricingConfiguration:
    """Verify pricing tiers are correctly configured."""

    def test_free_tier_limits(self):
        """Free tier has correct limits: 10 videos, 200 msgs, 1GB, 1000 mins."""
        config = get_tier_config("free")
        assert config["video_limit"] == 10
        assert config["message_limit"] == 200
        assert config["storage_limit_mb"] == 1000
        assert config["minutes_limit"] == 1000

    def test_pro_tier_limits(self):
        """Pro tier: unlimited videos/msgs/mins, 50GB storage."""
        config = get_tier_config("pro")
        assert config["video_limit"] == -1  # unlimited
        assert config["message_limit"] == -1
        assert config["storage_limit_mb"] == 50000
        assert config["minutes_limit"] == -1

    def test_enterprise_tier_limits(self):
        """Enterprise tier: all unlimited."""
        config = get_tier_config("enterprise")
        assert config["video_limit"] == -1
        assert config["message_limit"] == -1
        assert config["storage_limit_mb"] == -1
        assert config["minutes_limit"] == -1

    def test_pro_pricing_correct(self):
        """Pro: $23.99/mo, $229.99/yr."""
        config = get_tier_config("pro")
        assert config["price_monthly"] == 2399
        assert config["price_yearly"] == 22999

    def test_enterprise_pricing_correct(self):
        """Enterprise: $79.99/mo, $799.99/yr."""
        config = get_tier_config("enterprise")
        assert config["price_monthly"] == 7999
        assert config["price_yearly"] == 79999

    def test_free_tier_pricing_zero(self):
        """Free tier has zero pricing."""
        config = get_tier_config("free")
        assert config["price_monthly"] == 0
        assert config["price_yearly"] == 0

    def test_stripe_price_ids_configured_for_paid_tiers(self):
        """Stripe price IDs are set for paid tiers."""
        pro = get_tier_config("pro")
        assert pro["stripe_price_id_monthly"] is not None
        assert pro["stripe_price_id_yearly"] is not None

        enterprise = get_tier_config("enterprise")
        assert enterprise["stripe_price_id_monthly"] is not None
        assert enterprise["stripe_price_id_yearly"] is not None

    def test_free_tier_no_stripe_ids(self):
        """Free tier has no Stripe price IDs."""
        free = get_tier_config("free")
        assert free["stripe_price_id_monthly"] is None
        assert free["stripe_price_id_yearly"] is None

    def test_invalid_tier_raises_error(self):
        """Invalid tier raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tier"):
            get_tier_config("invalid_tier")


class TestQuotaLimitsHelper:
    """Test get_quota_limits helper function."""

    def test_get_quota_limits_free(self):
        """Get quota limits for free tier."""
        limits = get_quota_limits("free")
        assert limits["video_limit"] == 10
        assert limits["message_limit"] == 200
        assert limits["storage_limit_mb"] == 1000
        assert limits["minutes_limit"] == 1000

    def test_get_quota_limits_pro(self):
        """Get quota limits for pro tier."""
        limits = get_quota_limits("pro")
        assert limits["video_limit"] == -1
        assert limits["message_limit"] == -1
        assert limits["storage_limit_mb"] == 50000
        assert limits["minutes_limit"] == -1


class TestIsUnlimitedHelper:
    """Test is_unlimited helper function."""

    def test_is_unlimited_returns_true_for_negative_one(self):
        """is_unlimited() returns True for -1."""
        assert is_unlimited(-1) is True

    def test_is_unlimited_returns_false_for_zero(self):
        """is_unlimited() returns False for 0."""
        assert is_unlimited(0) is False

    def test_is_unlimited_returns_false_for_positive(self):
        """is_unlimited() returns False for positive values."""
        assert is_unlimited(100) is False
        assert is_unlimited(1) is False


class TestCheckLimitExceeded:
    """Test check_limit_exceeded helper function."""

    def test_limit_exceeded_when_at_limit(self):
        """Returns True when usage equals limit."""
        assert check_limit_exceeded(10, 10) is True

    def test_limit_exceeded_when_over_limit(self):
        """Returns True when usage exceeds limit."""
        assert check_limit_exceeded(11, 10) is True

    def test_limit_not_exceeded_when_under(self):
        """Returns False when usage is under limit."""
        assert check_limit_exceeded(5, 10) is False

    def test_limit_never_exceeded_for_unlimited(self):
        """Returns False for unlimited quota (-1)."""
        assert check_limit_exceeded(1000000, -1) is False


class TestUsagePercentage:
    """Test get_usage_percentage helper function."""

    def test_usage_percentage_calculation(self):
        """Calculate correct percentage."""
        assert get_usage_percentage(50, 100) == 50.0
        assert get_usage_percentage(75, 100) == 75.0
        assert get_usage_percentage(100, 100) == 100.0

    def test_usage_percentage_zero_for_unlimited(self):
        """Returns 0 for unlimited quota."""
        assert get_usage_percentage(1000, -1) == 0.0

    def test_usage_percentage_capped_at_100(self):
        """Percentage is capped at 100%."""
        assert get_usage_percentage(150, 100) == 100.0

    def test_usage_percentage_zero_limit(self):
        """Returns 100% when limit is 0."""
        assert get_usage_percentage(0, 0) == 100.0


class TestAllTiersExist:
    """Verify all expected tiers are configured."""

    def test_all_expected_tiers_exist(self):
        """All three tiers (free, pro, enterprise) are defined."""
        assert "free" in PRICING_TIERS
        assert "pro" in PRICING_TIERS
        assert "enterprise" in PRICING_TIERS

    def test_only_expected_tiers_exist(self):
        """No unexpected tiers are defined."""
        assert len(PRICING_TIERS) == 3


class TestTierFeatures:
    """Verify tier features are populated."""

    def test_each_tier_has_features(self):
        """Each tier has a non-empty features list."""
        for tier_name, config in PRICING_TIERS.items():
            assert "features" in config
            assert isinstance(config["features"], list)
            assert len(config["features"]) > 0
