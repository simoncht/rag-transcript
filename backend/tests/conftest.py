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
        if dialect.name == 'postgresql':
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
def sample_embedding():
    """Fixture providing a sample embedding vector."""
    import numpy as np
    return np.random.rand(384).astype(np.float32)


@pytest.fixture
def sample_video_id():
    """Fixture providing a sample video ID."""
    return "dQw4w9WgXcQ"


@pytest.fixture
def sample_query():
    """Fixture providing a sample search query."""
    return "What is this video about?"


@pytest.fixture
def sample_chunk_text():
    """Fixture providing sample chunk text."""
    return "This is a sample transcript chunk with relevant content about the video topic."


@pytest.fixture
def sample_chunks():
    """Fixture providing multiple sample chunks."""
    return [
        {
            "id": f"chunk_{i}",
            "text": f"This is sample chunk {i} with relevant content.",
            "start_timestamp": i * 10.0,
            "end_timestamp": (i + 1) * 10.0,
            "video_id": "sample_video_123",
        }
        for i in range(5)
    ]
