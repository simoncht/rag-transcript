"""
Integration tests for admin API endpoints.

Tests the full request/response cycle for admin routes.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import User, Video, Conversation, Message, Collection
from app.core.auth import get_current_user
from app.db.base import get_db
from datetime import datetime, timedelta


# Test fixtures

@pytest.fixture
def admin_user(db: Session):
    """Create an admin user for testing."""
    user = User(
        email="admin@test.com",
        full_name="Admin User",
        clerk_user_id="admin_clerk_id",
        is_superuser=True,
        is_active=True,
        subscription_tier="enterprise",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db: Session):
    """Create a regular (non-admin) user for testing."""
    user = User(
        email="user@test.com",
        full_name="Regular User",
        clerk_user_id="user_clerk_id",
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
def test_users(db: Session):
    """Create multiple test users with different tiers."""
    users = []
    tiers = ["free", "starter", "pro", "business"]

    for i, tier in enumerate(tiers):
        user = User(
            email=f"user{i}@test.com",
            full_name=f"Test User {i}",
            clerk_user_id=f"clerk_id_{i}",
            is_superuser=False,
            is_active=True,
            subscription_tier=tier,
            subscription_status="active",
        )
        db.add(user)
        users.append(user)

    db.commit()
    for user in users:
        db.refresh(user)

    return users


@pytest.fixture
def client_with_admin(admin_user, db: Session):
    """Create a test client with admin authentication."""
    client = TestClient(app)

    # Override the get_current_user dependency to return admin user
    def override_get_current_user():
        return admin_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_regular_user(regular_user, db: Session):
    """Create a test client with regular user authentication."""
    client = TestClient(app)

    # Override the get_current_user dependency to return regular user
    def override_get_current_user():
        return regular_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield client

    # Clean up
    app.dependency_overrides.clear()


# Tests

def test_get_dashboard_as_admin(client_with_admin, test_users):
    """Admin can access dashboard stats."""
    response = client_with_admin.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "system_stats" in data
    assert "engagement_stats" in data
    assert "generated_at" in data

    # Verify system stats
    system_stats = data["system_stats"]
    assert "total_users" in system_stats
    assert "active_users" in system_stats
    assert system_stats["total_users"] >= 4  # We created 4 test users


def test_get_dashboard_as_regular_user(client_with_regular_user):
    """Regular user gets 403 on admin routes."""
    response = client_with_regular_user.get("/api/v1/admin/dashboard")

    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


def test_list_users_with_pagination(client_with_admin, test_users):
    """User list returns paginated results with stats."""
    response = client_with_admin.get("/api/v1/admin/users?page=1&page_size=2")

    assert response.status_code == 200
    data = response.json()

    # Verify pagination structure
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "users" in data

    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["users"]) <= 2

    # Verify user structure
    if data["users"]:
        user = data["users"][0]
        assert "id" in user
        assert "email" in user
        assert "subscription_tier" in user
        assert "video_count" in user
        assert "total_tokens_used" in user


def test_list_users_with_search(client_with_admin, test_users):
    """User list search functionality works."""
    response = client_with_admin.get("/api/v1/admin/users?search=user0@test.com")

    assert response.status_code == 200
    data = response.json()

    # Should find the user with email user0@test.com
    assert data["total"] >= 1
    emails = [u["email"] for u in data["users"]]
    assert "user0@test.com" in emails


def test_list_users_with_tier_filter(client_with_admin, test_users):
    """User list can be filtered by subscription tier."""
    response = client_with_admin.get("/api/v1/admin/users?tier=pro")

    assert response.status_code == 200
    data = response.json()

    # All returned users should have pro tier
    for user in data["users"]:
        assert user["subscription_tier"] == "pro"


def test_get_user_detail_includes_metrics(client_with_admin, regular_user, db):
    """User detail includes videos, conversations, usage, and costs."""
    # Create some test data for the user
    video = Video(
        user_id=regular_user.id,
        youtube_id="test_video_id",
        youtube_url="https://youtube.com/watch?v=test",
        title="Test Video",
        status="completed",
        duration_seconds=600,
    )
    db.add(video)

    conversation = Conversation(
        user_id=regular_user.id,
        title="Test Conversation",
    )
    db.add(conversation)
    db.commit()

    # Get user detail
    response = client_with_admin.get(f"/api/v1/admin/users/{regular_user.id}")

    assert response.status_code == 200
    data = response.json()

    # Verify basic user info
    assert data["email"] == regular_user.email
    assert data["id"] == str(regular_user.id)

    # Verify metrics
    assert "metrics" in data
    metrics = data["metrics"]
    assert metrics["videos_total"] >= 1
    assert metrics["conversations_total"] >= 1

    # Verify costs
    assert "costs" in data
    costs = data["costs"]
    assert "total_cost" in costs
    assert "subscription_revenue" in costs
    assert "net_profit" in costs


def test_update_user_subscription_tier(client_with_admin, regular_user, db):
    """Admin can change user's subscription tier."""
    update_data = {
        "subscription_tier": "pro",
        "subscription_status": "active",
    }

    response = client_with_admin.patch(
        f"/api/v1/admin/users/{regular_user.id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()

    assert data["subscription_tier"] == "pro"
    assert data["subscription_status"] == "active"

    # Verify database was updated
    db.refresh(regular_user)
    assert regular_user.subscription_tier == "pro"


def test_update_user_active_status(client_with_admin, regular_user, db):
    """Admin can activate or deactivate user accounts."""
    update_data = {
        "is_active": False,
    }

    response = client_with_admin.patch(
        f"/api/v1/admin/users/{regular_user.id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()

    assert data["is_active"] is False

    # Verify database was updated
    db.refresh(regular_user)
    assert regular_user.is_active is False


def test_quota_override_applies_correctly(client_with_admin, regular_user, db):
    """Manual quota override reflects in user's limits."""
    from datetime import datetime, timedelta
    from decimal import Decimal
    from app.models import UserQuota

    # Create initial quota
    now = datetime.utcnow()
    quota = UserQuota(
        user_id=regular_user.id,
        quota_period_start=now,
        quota_period_end=now + timedelta(days=30),
        videos_limit=5,
        minutes_limit=Decimal(60),
        messages_limit=50,
        storage_mb_limit=Decimal(1000),
    )
    db.add(quota)
    db.commit()

    # Override quota
    override_data = {
        "videos_limit": 100,
        "minutes_limit": 500.0,
    }

    response = client_with_admin.patch(
        f"/api/v1/admin/users/{regular_user.id}/quota",
        json=override_data
    )

    assert response.status_code == 200

    # Verify quota was updated
    db.refresh(quota)
    assert quota.videos_limit == 100
    assert float(quota.minutes_limit) == 500.0


def test_get_nonexistent_user_returns_404(client_with_admin):
    """Getting a non-existent user returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"

    response = client_with_admin.get(f"/api/v1/admin/users/{fake_uuid}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_dashboard_includes_tier_breakdown(client_with_admin, test_users):
    """Dashboard shows breakdown of users by subscription tier."""
    response = client_with_admin.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    data = response.json()

    system_stats = data["system_stats"]

    # Verify tier counts are present
    assert "users_free" in system_stats
    assert "users_starter" in system_stats
    assert "users_pro" in system_stats
    assert "users_business" in system_stats

    # Since we created one of each tier
    assert system_stats["users_free"] >= 1
    assert system_stats["users_starter"] >= 1
    assert system_stats["users_pro"] >= 1
    assert system_stats["users_business"] >= 1


def test_user_cost_calculation_is_accurate(client_with_admin, regular_user, db):
    """Cost calculation accurately reflects user's resource usage."""
    # Create conversation with messages
    conversation = Conversation(
        user_id=regular_user.id,
        title="Test Conversation",
    )
    db.add(conversation)
    db.flush()

    # Create message with known token counts
    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Test response",
        input_tokens=1000,
        output_tokens=500,
        llm_provider="anthropic",
        llm_model="claude-3-sonnet",
    )
    db.add(message)
    db.commit()

    # Get user detail
    response = client_with_admin.get(f"/api/v1/admin/users/{regular_user.id}")

    assert response.status_code == 200
    data = response.json()

    costs = data["costs"]

    # LLM cost should be calculated: (1000/1M * $3) + (500/1M * $15) = $0.0105
    assert costs["llm_input_tokens"] == 1000
    assert costs["llm_output_tokens"] == 500
    assert costs["llm_cost"] > 0  # Should have some cost

    # Total cost should be sum of all costs
    expected_total = (
        costs["transcription_cost"] +
        costs["embedding_cost"] +
        costs["llm_cost"] +
        costs["storage_cost"]
    )
    assert abs(costs["total_cost"] - expected_total) < 0.0001  # Allow for rounding
