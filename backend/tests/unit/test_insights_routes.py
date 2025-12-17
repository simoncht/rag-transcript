import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import insights as insights_routes
from app.core.auth import get_current_user
from app.db.base import get_db
from app.models import Conversation, User


def _fake_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="insights@example.com",
        is_active=True,
    )


class _FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first = first_result
        self._all = all_result or []

    def filter(self, *args, **kwargs):  # noqa: ANN002, D401
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, D401
        return self

    def first(self):  # noqa: ANN001, D401
        return self._first

    def all(self):  # noqa: ANN001, D401
        return self._all


class _FakeSession:
    def __init__(self, conversation: Conversation | None):
        self._conversation = conversation

    def query(self, entity):  # noqa: ANN001
        # The insights routes only need:
        # - Conversation lookup via .first()
        # - ConversationSource selection via .all() (we return empty -> fallback to conversation.selected_video_ids)
        from app.models import Conversation as ConversationModel

        if entity is ConversationModel:
            return _FakeQuery(first_result=self._conversation)
        return _FakeQuery(all_result=[])


def _create_test_app(fake_db: _FakeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(insights_routes.router, prefix="/api/v1/conversations")
    app.dependency_overrides[get_current_user] = _fake_user

    def _override_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_db
    return app


def test_get_conversation_insights_returns_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    conversation_id = uuid.uuid4()

    conversation = Conversation(
        id=conversation_id,
        user_id=user.id,
        selected_video_ids=[uuid.uuid4()],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        message_count=0,
        total_tokens_used=0,
    )

    class DummyInsight:
        def __init__(self) -> None:
            self.graph_data = {
                "nodes": [
                    {
                        "id": "topic-1",
                        "type": "topic",
                        "position": {"x": 0.0, "y": 0.0},
                        "data": {
                            "label": "Topic",
                            "description": "Desc",
                            "chunk_count": 3,
                        },
                    }
                ],
                "edges": [],
            }
            self.topics_count = 1
            self.total_chunks_analyzed = 10
            self.generation_time_seconds = 1.234
            self.created_at = datetime.utcnow()
            self.llm_provider = "dummy"
            self.llm_model = "dummy"
            self.extraction_prompt_version = 1

    def _fake_get_or_generate_insights(**kwargs):  # noqa: ANN003
        return DummyInsight(), True

    monkeypatch.setattr(
        insights_routes.insights_service,
        "get_or_generate_insights",
        _fake_get_or_generate_insights,
        raising=True,
    )

    app = _create_test_app(_FakeSession(conversation))
    client = TestClient(app)

    resp = client.get(f"/api/v1/conversations/{conversation_id}/insights")
    assert resp.status_code == 200

    data = resp.json()
    assert data["conversation_id"] == str(conversation_id)
    assert "graph" in data
    assert data["graph"]["nodes"][0]["id"] == "topic-1"
    assert data["metadata"]["cached"] is True
    assert data["metadata"]["topics_count"] == 1


def test_get_conversation_insights_400_when_no_videos_selected() -> None:
    user = _fake_user()
    conversation_id = uuid.uuid4()

    conversation = Conversation(
        id=conversation_id,
        user_id=user.id,
        selected_video_ids=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        message_count=0,
        total_tokens_used=0,
    )

    app = _create_test_app(_FakeSession(conversation))
    client = TestClient(app)

    resp = client.get(f"/api/v1/conversations/{conversation_id}/insights")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No videos selected for this conversation"


def test_get_topic_chunks_returns_cached_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    conversation_id = uuid.uuid4()

    conversation = Conversation(
        id=conversation_id,
        user_id=user.id,
        selected_video_ids=[uuid.uuid4()],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        message_count=0,
        total_tokens_used=0,
    )

    def _fake_get_topic_chunks(**kwargs):  # noqa: ANN003
        return {
            "topic_id": "topic-1",
            "topic_label": "Topic One",
            "chunks": [
                {
                    "chunk_id": str(uuid.uuid4()),
                    "video_id": str(uuid.uuid4()),
                    "video_title": "Video",
                    "start_timestamp": 0.0,
                    "end_timestamp": 10.0,
                    "timestamp_display": "00:00 - 00:10",
                    "text": "text",
                    "chunk_title": None,
                }
            ],
        }

    monkeypatch.setattr(
        insights_routes.insights_service,
        "get_topic_chunks",
        _fake_get_topic_chunks,
        raising=True,
    )

    app = _create_test_app(_FakeSession(conversation))
    client = TestClient(app)

    resp = client.get(
        f"/api/v1/conversations/{conversation_id}/insights/topics/topic-1/chunks"
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["topic_id"] == "topic-1"
    assert payload["topic_label"] == "Topic One"
    assert len(payload["chunks"]) == 1


def test_get_topic_chunks_404_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _fake_user()
    conversation_id = uuid.uuid4()

    conversation = Conversation(
        id=conversation_id,
        user_id=user.id,
        selected_video_ids=[uuid.uuid4()],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        message_count=0,
        total_tokens_used=0,
    )

    def _raise_missing(**kwargs):  # noqa: ANN003
        raise ValueError("Topic not found in cached insights")

    monkeypatch.setattr(
        insights_routes.insights_service,
        "get_topic_chunks",
        _raise_missing,
        raising=True,
    )

    app = _create_test_app(_FakeSession(conversation))
    client = TestClient(app)

    resp = client.get(
        f"/api/v1/conversations/{conversation_id}/insights/topics/topic-999/chunks"
    )
    assert resp.status_code == 404
