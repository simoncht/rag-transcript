import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import insights as insights_routes
from app.core.nextauth import get_current_user
from app.db.base import get_db
from app.models import Conversation, User


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
    def __init__(self, conversation: Conversation):
        self._conversation = conversation

    def query(self, entity):  # noqa: ANN001
        from app.models import Conversation as ConversationModel

        if entity is ConversationModel:
            return _FakeQuery(first_result=self._conversation)
        return _FakeQuery(all_result=[])


def _fake_user() -> User:
    return User(id=uuid.uuid4(), email="integration@example.com", is_active=True)


def test_insights_endpoint_respects_cache_and_regenerate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid.uuid4()
    user = _fake_user()

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
            self.generation_time_seconds = 1.0
            self.created_at = datetime.utcnow()
            self.llm_provider = "dummy"
            self.llm_model = "dummy"
            self.extraction_prompt_version = 1

    state = {"has_cache": False}

    def _fake_get_or_generate_insights(
        *, force_regenerate: bool, **kwargs
    ):  # noqa: ANN003
        if force_regenerate or not state["has_cache"]:
            state["has_cache"] = True
            return DummyInsight(), False
        return DummyInsight(), True

    monkeypatch.setattr(
        insights_routes.insights_service,
        "get_or_generate_insights",
        _fake_get_or_generate_insights,
        raising=True,
    )

    app = FastAPI()
    app.include_router(insights_routes.router, prefix="/api/v1/conversations")
    app.dependency_overrides[get_current_user] = lambda: user

    def _override_db():
        yield _FakeSession(conversation)

    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)

    r1 = client.get(f"/api/v1/conversations/{conversation_id}/insights")
    assert r1.status_code == 200
    assert r1.json()["metadata"]["cached"] is False

    r2 = client.get(f"/api/v1/conversations/{conversation_id}/insights")
    assert r2.status_code == 200
    assert r2.json()["metadata"]["cached"] is True

    r3 = client.get(f"/api/v1/conversations/{conversation_id}/insights?regenerate=true")
    assert r3.status_code == 200
    assert r3.json()["metadata"]["cached"] is False
