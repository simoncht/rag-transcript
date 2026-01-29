"""
Unit tests for subscription service.

Tests checkout session creation, verification, and quota management.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.subscription import subscription_service
from app.schemas import QuotaUsage


class TestCheckoutSessionCreation:
    """Test Stripe checkout session creation."""

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_monthly_checkout_uses_monthly_price(self, mock_customer, mock_stripe, db, free_user):
        """Monthly billing cycle uses monthly Stripe price."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        # Patch Stripe API key
        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            result = subscription_service.create_checkout_session(
                user=free_user,
                tier="pro",
                billing_cycle="monthly",
                success_url="http://test.com/success",
                cancel_url="http://test.com/cancel",
                db=db,
            )

        # Verify correct price ID was used
        call_args = mock_stripe.call_args
        assert call_args.kwargs["line_items"][0]["price"] == "price_1SugDfRmTkZwB6fLSa2jHi9B"
        assert result["session_id"] == "cs_123"

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_yearly_checkout_uses_yearly_price(self, mock_customer, mock_stripe, db, free_user):
        """Yearly billing cycle uses yearly Stripe price."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            result = subscription_service.create_checkout_session(
                user=free_user,
                tier="pro",
                billing_cycle="yearly",
                success_url="http://test.com/success",
                cancel_url="http://test.com/cancel",
                db=db,
            )

        call_args = mock_stripe.call_args
        assert call_args.kwargs["line_items"][0]["price"] == "price_1SugDlRmTkZwB6fLQRsvGWqN"

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_enterprise_monthly_price(self, mock_customer, mock_stripe, db, free_user):
        """Enterprise monthly uses correct price."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            subscription_service.create_checkout_session(
                user=free_user,
                tier="enterprise",
                billing_cycle="monthly",
                success_url="http://test.com/success",
                cancel_url="http://test.com/cancel",
                db=db,
            )

        call_args = mock_stripe.call_args
        assert call_args.kwargs["line_items"][0]["price"] == "price_1SugDnRmTkZwB6fLFOyPjWIK"

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_enterprise_yearly_price(self, mock_customer, mock_stripe, db, free_user):
        """Enterprise yearly uses correct price."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            subscription_service.create_checkout_session(
                user=free_user,
                tier="enterprise",
                billing_cycle="yearly",
                success_url="http://test.com/success",
                cancel_url="http://test.com/cancel",
                db=db,
            )

        call_args = mock_stripe.call_args
        assert call_args.kwargs["line_items"][0]["price"] == "price_1SugDoRmTkZwB6fLgO05P9wH"

    def test_invalid_billing_cycle_raises_error(self, db, free_user):
        """Invalid billing cycle raises ValueError."""
        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            with pytest.raises(ValueError, match="Invalid billing cycle"):
                subscription_service.create_checkout_session(
                    user=free_user,
                    tier="pro",
                    billing_cycle="quarterly",  # Invalid
                    success_url="http://test.com/success",
                    cancel_url="http://test.com/cancel",
                    db=db,
                )

    def test_no_stripe_api_key_raises_error(self, db, free_user):
        """Missing Stripe API key raises ValueError."""
        with patch("app.services.subscription.stripe.api_key", None):
            with pytest.raises(ValueError, match="Stripe API key not configured"):
                subscription_service.create_checkout_session(
                    user=free_user,
                    tier="pro",
                    billing_cycle="monthly",
                    success_url="http://test.com/success",
                    cancel_url="http://test.com/cancel",
                    db=db,
                )

    @patch("stripe.checkout.Session.create")
    def test_reuses_existing_stripe_customer(self, mock_stripe, db, free_user):
        """Uses existing Stripe customer ID if present."""
        free_user.stripe_customer_id = "cus_existing"
        db.commit()

        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            subscription_service.create_checkout_session(
                user=free_user,
                tier="pro",
                billing_cycle="monthly",
                success_url="http://test.com/success",
                cancel_url="http://test.com/cancel",
                db=db,
            )

        # Should use existing customer
        call_args = mock_stripe.call_args
        assert call_args.kwargs["customer"] == "cus_existing"


class TestQuotaCalculation:
    """Test user quota calculation."""

    def test_free_user_quota_limits(self, db, free_user):
        """Free user has correct quota limits."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                quota = subscription_service.get_user_quota(free_user.id, db)

        assert quota.tier == "free"
        assert quota.videos_limit == 10
        assert quota.messages_limit == 200
        assert quota.storage_limit_mb == 1000
        assert quota.minutes_limit == 1000

    def test_pro_user_quota_limits(self, db, pro_user):
        """Pro user has correct quota limits (mostly unlimited)."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                quota = subscription_service.get_user_quota(pro_user.id, db)

        assert quota.tier == "pro"
        assert quota.videos_limit == -1  # unlimited
        assert quota.messages_limit == -1
        assert quota.storage_limit_mb == 50000
        assert quota.minutes_limit == -1

    def test_admin_user_has_unlimited_quotas(self, db, admin_user):
        """Admin user has unlimited quotas regardless of tier."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                quota = subscription_service.get_user_quota(admin_user.id, db)

        assert quota.videos_limit == -1
        assert quota.messages_limit == -1
        assert quota.storage_limit_mb == -1
        assert quota.minutes_limit == -1


class TestCheckQuotaMethods:
    """Test individual quota check methods."""

    def test_check_video_quota_under_limit(self, db, free_user):
        """check_video_quota returns True when under limit."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                result = subscription_service.check_video_quota(free_user.id, db)

        assert result is True

    def test_check_storage_quota_with_remaining(self, db, free_user):
        """check_storage_quota returns True when space available."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=500):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                # 500MB used, 100MB requested, 1000MB limit = should pass
                result = subscription_service.check_storage_quota(free_user.id, 100, db)

        assert result is True

    def test_check_storage_quota_insufficient(self, db, free_user):
        """check_storage_quota returns False when insufficient space."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=950):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                # 950MB used, 100MB requested, 1000MB limit = should fail
                result = subscription_service.check_storage_quota(free_user.id, 100, db)

        assert result is False


class TestPricingTiersRetrieval:
    """Test pricing tiers retrieval."""

    def test_get_pricing_tiers_returns_all_tiers(self):
        """Returns all three pricing tiers."""
        tiers = subscription_service.get_pricing_tiers()

        tier_names = [t.tier for t in tiers]
        assert "free" in tier_names
        assert "pro" in tier_names
        assert "enterprise" in tier_names
        assert len(tiers) == 3

    def test_pricing_tiers_have_required_fields(self):
        """Each tier has required fields."""
        tiers = subscription_service.get_pricing_tiers()

        for tier in tiers:
            assert tier.tier is not None
            assert tier.name is not None
            assert tier.price_monthly is not None
            assert tier.price_yearly is not None
            assert tier.features is not None
            assert tier.video_limit is not None
            assert tier.message_limit is not None
            assert tier.storage_limit_mb is not None
            assert tier.minutes_limit is not None
