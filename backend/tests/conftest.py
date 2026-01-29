"""
Pytest configuration and shared fixtures for RAG Transcript project.
"""
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Patch PostgreSQL UUID type BEFORE any imports
from sqlalchemy.dialects import postgresql
from sqlalchemy import JSON, TypeDecorator, CHAR
import uuid as uuid_module


class GUID(TypeDecorator):
    """Platform-independent GUID type. Uses PostgreSQL's UUID type, otherwise uses CHAR(36)."""

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid=True):
        """Accept as_uuid parameter for compatibility with PostgreSQL UUID."""
        self.as_uuid = as_uuid
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_original_uuid(as_uuid=self.as_uuid))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid_module.UUID):
            return str(value)
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid_module.UUID):
            return value
        else:
            return uuid_module.UUID(value)


# Monkey patch BEFORE models are imported
_original_uuid = postgresql.UUID
postgresql.UUID = GUID
_original_jsonb = postgresql.JSONB
_original_array = postgresql.ARRAY


def _to_jsonable(value):  # noqa: ANN001
    if value is None:
        return None
    if isinstance(value, uuid_module.UUID):
        return str(value)
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


class JSONB(TypeDecorator):
    """SQLite-friendly stand-in for PostgreSQL JSONB."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_original_jsonb())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return _to_jsonable(value)


class ARRAY(TypeDecorator):
    """SQLite-friendly stand-in for PostgreSQL ARRAY."""

    impl = JSON
    cache_ok = True

    def __init__(self, item_type=None, **kwargs):  # noqa: ANN001
        self.item_type = item_type
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_original_array(self.item_type))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return _to_jsonable(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # Convert UUID strings back to UUID objects when the array element is UUID.
        if isinstance(self.item_type, GUID):
            return [
                v if isinstance(v, uuid_module.UUID) else uuid_module.UUID(str(v))
                for v in value
            ]
        return value


postgresql.JSONB = JSONB
postgresql.ARRAY = ARRAY

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh database for each test.

    Uses an in-memory SQLite database for fast, isolated testing.
    UUID type has been patched at module level to work with SQLite.
    """
    from app.db.base import Base

    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def free_user(db):
    """Create a free tier user for testing."""
    from app.models import User

    user = User(
        email="free@test.com",
        full_name="Free User",
        oauth_provider="google",
        oauth_provider_id="free_oauth_id",
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
def pro_user(db):
    """Create a pro tier user for testing."""
    from app.models import User

    user = User(
        email="pro@test.com",
        full_name="Pro User",
        oauth_provider="google",
        oauth_provider_id="pro_oauth_id",
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
def enterprise_user(db):
    """Create an enterprise tier user for testing."""
    from app.models import User

    user = User(
        email="enterprise@test.com",
        full_name="Enterprise User",
        oauth_provider="google",
        oauth_provider_id="enterprise_oauth_id",
        is_superuser=False,
        is_active=True,
        subscription_tier="enterprise",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin (superuser) for testing."""
    from app.models import User

    user = User(
        email="admin@test.com",
        full_name="Admin User",
        oauth_provider="google",
        oauth_provider_id="admin_oauth_id",
        is_superuser=True,
        is_active=True,
        subscription_tier="free",  # Admin bypasses quotas regardless of tier
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_stripe():
    """Mock all Stripe API calls for testing."""
    from unittest.mock import patch, MagicMock

    with patch("stripe.checkout.Session.create") as mock_create, \
         patch("stripe.checkout.Session.retrieve") as mock_retrieve, \
         patch("stripe.Customer.create") as mock_customer, \
         patch("stripe.Subscription.retrieve") as mock_sub:

        mock_create.return_value = MagicMock(
            id="cs_test_123",
            url="https://checkout.stripe.com/test",
        )
        mock_retrieve.return_value = MagicMock(
            id="cs_test_123",
            payment_status="paid",
            metadata={"user_id": "test", "tier": "pro"},
            customer="cus_123",
            subscription="sub_123",
        )
        mock_customer.return_value = MagicMock(id="cus_123")
        mock_sub.return_value = MagicMock(
            id="sub_123",
            items={"data": [{"price": {"id": "price_123"}}]},
            current_period_start=1234567890,
            current_period_end=1237246290,
        )

        yield {
            "create": mock_create,
            "retrieve": mock_retrieve,
            "customer": mock_customer,
            "subscription": mock_sub,
        }
