"""
Integration tests for admin API endpoints.

Tests the full request/response cycle for admin routes.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    Chunk,
    Collection,
    CollectionVideo,
    Conversation,
    Message,
    MessageChunkReference,
    User,
    Video,
    AdminAuditLog,
)
from app.core.nextauth import get_current_user
from app.db.base import get_db


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


# Helpers


def _create_conversation_with_messages(db: Session, user: User):
    """Helper to create a conversation with user/assistant messages and a referenced chunk."""
    video = Video(
        user_id=user.id,
        youtube_id="sample123",
        youtube_url="https://example.com/watch?v=sample123",
        title="Sample Video",
        status="completed",
        duration_seconds=120,
        progress_percent=100.0,
        chunk_count=1,
        audio_file_size_mb=10.0,
        is_deleted=False,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    chunk = Chunk(
        video_id=video.id,
        user_id=user.id,
        chunk_index=0,
        text="This is a sample chunk about testing admin features.",
        token_count=30,
        start_timestamp=0.0,
        end_timestamp=10.0,
        duration_seconds=10.0,
        is_indexed=True,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    conversation = Conversation(
        user_id=user.id,
        title="Admin visibility test",
        selected_video_ids=[video.id],
        message_count=2,
        total_tokens_used=0,
        last_message_at=datetime.utcnow(),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    asked_at = datetime.utcnow()
    answered_at = asked_at + timedelta(seconds=1)

    question = Message(
        conversation_id=conversation.id,
        role="user",
        content="What is in this video?",
        created_at=asked_at,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    answer = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="The video covers admin monitoring.",
        created_at=answered_at,
        input_tokens=50,
        output_tokens=75,
        response_time_seconds=0.5,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)

    reference = MessageChunkReference(
        message_id=answer.id,
        chunk_id=chunk.id,
        relevance_score=0.92,
        rank=1,
        was_used_in_response=True,
    )
    db.add(reference)

    collection = Collection(
        user_id=user.id,
        name="Admin Test Collection",
        description="",
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)

    link = CollectionVideo(collection_id=collection.id, video_id=video.id)
    db.add(link)

    conversation.collection_id = collection.id
    conversation.message_count = 2
    conversation.total_tokens_used = 125
    conversation.last_message_at = answered_at

    db.commit()

    return conversation, question, answer


def test_admin_qa_feed_returns_items(client_with_admin, db: Session, regular_user):
    """QA feed returns question/answer pairs for admins."""
    _conversation, question, answer = _create_conversation_with_messages(
        db, regular_user
    )

    response = client_with_admin.get("/api/v1/admin/qa-feed")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["question_id"] == str(question.id)
    assert item["answer_id"] == str(answer.id)
    assert item["answer"].startswith("The video covers")
    assert item["sources"]
    assert item["response_latency_ms"] >= 0


def test_admin_audit_logs_endpoint(client_with_admin, db: Session, regular_user):
    """Audit log endpoint returns chat events for admins."""
    conversation, question, _answer = _create_conversation_with_messages(
        db, regular_user
    )

    log = AdminAuditLog(
        event_type="chat_message",
        user_id=regular_user.id,
        conversation_id=conversation.id,
        message_id=question.id,
        role="user",
        content=question.content,
        flags=["pii_detected"],
        message_metadata={"flags": ["pii_detected"]},
    )
    db.add(log)
    db.commit()

    response = client_with_admin.get("/api/v1/admin/audit/messages")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    first = payload["items"][0]
    assert first["message_id"] == str(question.id)
    assert "pii_detected" in first["flags"]

    flagged_only = client_with_admin.get(
        "/api/v1/admin/audit/messages?has_flags=true"
    )
    assert flagged_only.status_code == 200
    flagged_payload = flagged_only.json()
    assert flagged_payload["total"] >= 1


def test_admin_conversation_detail(client_with_admin, db: Session, regular_user):
    """Conversation detail returns message timeline."""
    conversation, _question, _answer = _create_conversation_with_messages(
        db, regular_user
    )

    response = client_with_admin.get(
        f"/api/v1/admin/conversations/{conversation.id}"
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(conversation.id)
    assert len(data["messages"]) == 2
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["user", "assistant"]
    assistant_msg = [m for m in data["messages"] if m["role"] == "assistant"][0]
    assert assistant_msg["sources"]


def test_admin_content_overview(client_with_admin, db: Session, regular_user):
    """Content overview returns video and collection stats."""
    _conversation, _question, _answer = _create_conversation_with_messages(
        db, regular_user
    )

    response = client_with_admin.get("/api/v1/admin/content/overview")
    assert response.status_code == 200
    data = response.json()

    videos = data["videos"]
    collections = data["collections"]

    assert videos["total"] >= 1
    assert videos["recent"]
    assert collections["total"] >= 1
    assert collections["with_videos"] >= 1

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
        f"/api/v1/admin/users/{regular_user.id}", json=update_data
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
        f"/api/v1/admin/users/{regular_user.id}", json=update_data
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
        f"/api/v1/admin/users/{regular_user.id}/quota", json=override_data
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
        costs["transcription_cost"]
        + costs["embedding_cost"]
        + costs["llm_cost"]
        + costs["storage_cost"]
    )
    assert abs(costs["total_cost"] - expected_total) < 0.0001  # Allow for rounding
