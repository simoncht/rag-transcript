"""
Integration tests for subscription API endpoints.

Tests the full request/response cycle for subscription routes including:
- POST /subscriptions/checkout
- GET /subscriptions/quota
- GET /subscriptions/pricing
- GET /subscriptions/verify-checkout
"""
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import User
from app.core.nextauth import get_current_user
from app.db.base import get_db


# Test fixtures


@pytest.fixture
def subscription_test_user(db: Session):
    """Create a test user for subscription operations."""
    user = User(
        email="subtest@test.com",
        full_name="Subscription Test User",
        oauth_provider="google",
        oauth_provider_id="sub_test_oauth_id",
        is_superuser=False,
        is_active=True,
        subscription_tier="free",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def pro_subscription_user(db: Session):
    """Create a Pro tier test user."""
    user = User(
        email="prosubtest@test.com",
        full_name="Pro Subscription Test User",
        oauth_provider="google",
        oauth_provider_id="pro_sub_test_oauth_id",
        is_superuser=False,
        is_active=True,
        subscription_tier="pro",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_with_free_user(subscription_test_user, db: Session):
    """Create a test client with free user authentication."""
    client = TestClient(app)

    def override_get_current_user():
        return subscription_test_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_pro_user(pro_subscription_user, db: Session):
    """Create a test client with pro user authentication."""
    client = TestClient(app)

    def override_get_current_user():
        return pro_subscription_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield client

    app.dependency_overrides.clear()


class TestCheckoutEndpoint:
    """Test POST /subscriptions/checkout endpoint."""

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_checkout_with_monthly_billing(
        self, mock_customer, mock_stripe, client_with_free_user
    ):
        """Checkout with monthly billing cycle succeeds."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            response = client_with_free_user.post(
                "/api/v1/subscriptions/checkout",
                json={
                    "tier": "pro",
                    "billing_cycle": "monthly",
                    "success_url": "http://test.com/success",
                    "cancel_url": "http://test.com/cancel",
                },
            )

        assert response.status_code == 200
        assert "checkout_url" in response.json()
        assert "session_id" in response.json()

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_checkout_with_yearly_billing(
        self, mock_customer, mock_stripe, client_with_free_user
    ):
        """Checkout with yearly billing cycle succeeds."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            response = client_with_free_user.post(
                "/api/v1/subscriptions/checkout",
                json={
                    "tier": "pro",
                    "billing_cycle": "yearly",
                    "success_url": "http://test.com/success",
                    "cancel_url": "http://test.com/cancel",
                },
            )

        assert response.status_code == 200

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_checkout_defaults_to_monthly(
        self, mock_customer, mock_stripe, client_with_free_user
    ):
        """Missing billing_cycle defaults to monthly."""
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_stripe.return_value = MagicMock(
            id="cs_123",
            url="https://checkout.stripe.com/test",
        )

        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            response = client_with_free_user.post(
                "/api/v1/subscriptions/checkout",
                json={
                    "tier": "pro",
                    # billing_cycle omitted - should default to monthly
                    "success_url": "http://test.com/success",
                    "cancel_url": "http://test.com/cancel",
                },
            )

        assert response.status_code == 200

    def test_checkout_free_tier_rejected(self, client_with_free_user):
        """Cannot checkout for free tier."""
        response = client_with_free_user.post(
            "/api/v1/subscriptions/checkout",
            json={
                "tier": "free",
                "billing_cycle": "monthly",
                "success_url": "http://test.com/success",
                "cancel_url": "http://test.com/cancel",
            },
        )

        assert response.status_code == 400
        assert "Cannot create checkout session for free tier" in response.json()["detail"]


class TestQuotaEndpoint:
    """Test GET /subscriptions/quota endpoint."""

    def test_free_user_quota(self, client_with_free_user):
        """Free user sees correct quota limits."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                response = client_with_free_user.get("/api/v1/subscriptions/quota")

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert data["videos_limit"] == 10
        assert data["messages_limit"] == 200
        assert data["storage_limit_mb"] == 1000
        assert data["minutes_limit"] == 1000

    def test_pro_user_quota(self, client_with_pro_user):
        """Pro user sees unlimited limits."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                response = client_with_pro_user.get("/api/v1/subscriptions/quota")

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "pro"
        assert data["videos_limit"] == -1
        assert data["messages_limit"] == -1
        assert data["storage_limit_mb"] == 50000
        assert data["minutes_limit"] == -1


class TestPricingEndpoint:
    """Test GET /subscriptions/pricing endpoint."""

    def test_pricing_returns_all_tiers(self, client_with_free_user):
        """Pricing endpoint returns all three tiers."""
        response = client_with_free_user.get("/api/v1/subscriptions/pricing")

        assert response.status_code == 200
        tiers = response.json()
        tier_names = [t["tier"] for t in tiers]
        assert "free" in tier_names
        assert "pro" in tier_names
        assert "enterprise" in tier_names

    def test_pricing_contains_required_fields(self, client_with_free_user):
        """Each tier has required pricing fields."""
        response = client_with_free_user.get("/api/v1/subscriptions/pricing")

        assert response.status_code == 200
        tiers = response.json()

        for tier in tiers:
            assert "tier" in tier
            assert "name" in tier
            assert "price_monthly" in tier
            assert "price_yearly" in tier
            assert "features" in tier
            assert "video_limit" in tier
            assert "message_limit" in tier
            assert "storage_limit_mb" in tier
            assert "minutes_limit" in tier


class TestVerifyCheckoutEndpoint:
    """Test GET /subscriptions/verify-checkout endpoint."""

    def test_verify_missing_session_id(self, client_with_free_user):
        """Missing session_id returns 422 validation error."""
        response = client_with_free_user.get("/api/v1/subscriptions/verify-checkout")
        assert response.status_code == 422

    def test_verify_invalid_session_returns_error(self, client_with_free_user):
        """Invalid session ID returns 400 or 500 error."""
        with patch("app.services.subscription.stripe.api_key", "sk_test_123"):
            with patch("stripe.checkout.Session.retrieve") as mock_session:
                # Simulate Stripe returning an invalid request error
                import stripe
                mock_session.side_effect = stripe.error.InvalidRequestError(
                    "No such checkout.session: invalid_session",
                    param="session_id",
                )

                response = client_with_free_user.get(
                    "/api/v1/subscriptions/verify-checkout?session_id=invalid_session"
                )

        # Should return 400 for invalid session
        assert response.status_code == 400

    def test_verify_endpoint_exists(self, client_with_free_user):
        """Verify endpoint exists and requires authentication."""
        # When Stripe is not configured, should return error
        with patch("app.services.subscription.stripe.api_key", None):
            response = client_with_free_user.get(
                "/api/v1/subscriptions/verify-checkout?session_id=cs_test"
            )
        # Should return an error (400 or 500) but not 404
        assert response.status_code != 404


class TestQuotaResponseSchema:
    """Regression tests for quota response schema."""

    def test_quota_endpoint_returns_correct_schema(self, client_with_free_user):
        """Quota endpoint response matches expected schema."""
        with patch("app.services.subscription.storage_service.get_storage_usage", return_value=0):
            with patch("app.services.subscription.StorageCalculator") as mock_calc:
                mock_calc.return_value.calculate_total_storage_mb.return_value = {
                    "database_mb": 0,
                    "vector_mb": 0,
                }

                response = client_with_free_user.get("/api/v1/subscriptions/quota")

        data = response.json()
        required_fields = [
            "tier",
            "videos_used",
            "videos_limit",
            "videos_remaining",
            "messages_used",
            "messages_limit",
            "messages_remaining",
            "storage_used_mb",
            "storage_limit_mb",
            "storage_remaining_mb",
            "minutes_used",
            "minutes_limit",
            "minutes_remaining",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
