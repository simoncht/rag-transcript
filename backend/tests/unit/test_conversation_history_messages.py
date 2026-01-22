import operator
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Iterator, Optional

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList, UnaryExpression
from sqlalchemy.sql import operators as sql_operators

from app.api.routes import conversations as conversations_routes
from app.core.auth import get_current_user
from app.db.base import get_db
from app.models import (
    Chunk,
    Conversation,
    ConversationSource,
    MessageChunkReference,
    Message,
    User,
    Video,
)


def _fake_user(user_id: uuid.UUID) -> User:
    return User(id=user_id, email="history@example.com", is_active=True)


def _extract_bound_value(expr: Any) -> Any:
    value = getattr(expr, "value", None)
    if value is not None:
        return value
    return expr


def _compile_filter(expr: Any) -> Callable[[Any], bool]:
    if isinstance(expr, BooleanClauseList):
        funcs = [_compile_filter(clause) for clause in expr.clauses]
        return lambda item: all(func(item) for func in funcs)

    if isinstance(expr, BinaryExpression):
        key = getattr(expr.left, "key", None) or getattr(expr.left, "name", None)
        op = expr.operator
        right_value = _extract_bound_value(expr.right)

        if op is operator.eq:
            return lambda item: getattr(item, key) == right_value
        if op is operator.ne:
            return lambda item: getattr(item, key) != right_value
        if op is sql_operators.in_op:
            allowed = set(right_value)
            return lambda item: getattr(item, key) in allowed
        if op is sql_operators.notin_op:
            blocked = set(right_value)
            return lambda item: getattr(item, key) not in blocked

    return lambda _item: True


def _parse_order_by(expr: Any) -> tuple[str, bool] | None:
    if isinstance(expr, UnaryExpression):
        key = getattr(expr.element, "key", None) or getattr(expr.element, "name", None)
        if not key:
            return None
        is_desc = expr.modifier is sql_operators.desc_op
        return key, is_desc
    return None


class _FakeQuery:
    def __init__(self, data: list[Any]):
        self._data = data
        self._filters: list[Callable[[Any], bool]] = []
        self._order_by: list[tuple[str, bool]] = []
        self._limit: Optional[int] = None

    def filter(self, *criteria: Any, **_kwargs: Any) -> "_FakeQuery":  # noqa: D401
        for expr in criteria:
            self._filters.append(_compile_filter(expr))
        return self

    def order_by(self, *expressions: Any) -> "_FakeQuery":  # noqa: D401
        for expr in expressions:
            parsed = _parse_order_by(expr)
            if parsed:
                self._order_by.append(parsed)
        return self

    def limit(self, n: int) -> "_FakeQuery":  # noqa: D401
        self._limit = n
        return self

    def _apply(self) -> list[Any]:
        results = [item for item in self._data if all(f(item) for f in self._filters)]
        for key, is_desc in reversed(self._order_by):
            results.sort(key=lambda item: getattr(item, key), reverse=is_desc)
        if self._limit is not None:
            results = results[: self._limit]
        return results

    def all(self) -> list[Any]:
        return self._apply()

    def first(self) -> Any | None:
        results = self.limit(1)._apply()
        return results[0] if results else None

    def count(self) -> int:
        return len(self._apply())

    def __iter__(self) -> Iterator[Any]:
        return iter(self._apply())


class _FakeSession:
    def __init__(
        self,
        *,
        conversation: Conversation,
        sources: list[ConversationSource],
        messages: list[Message],
        videos: list[Video],
        chunks: list[Chunk],
    ):
        self._conversation = conversation
        self._sources = sources
        self._messages = messages
        self._videos = videos
        self._chunks = chunks

    def query(self, *entities: Any) -> _FakeQuery:  # noqa: ANN401
        if len(entities) != 1:
            raise NotImplementedError(
                "FakeSession.query supports a single entity only."
            )

        entity = entities[0]
        if entity is Conversation:
            return _FakeQuery([self._conversation])
        if entity is ConversationSource:
            return _FakeQuery(self._sources)
        if entity is Message:
            return _FakeQuery(self._messages)
        if entity is Video:
            return _FakeQuery(self._videos)
        if entity is Chunk:
            return _FakeQuery(self._chunks)
        return _FakeQuery([])

    def add(self, instance: Any) -> None:  # noqa: ANN401
        if isinstance(instance, Message):
            if getattr(instance, "created_at", None) is None:
                instance.created_at = datetime.utcnow()
            self._messages.append(instance)

    def commit(self) -> None:
        return None

    def refresh(self, _instance: Any) -> None:  # noqa: ANN401
        return None


def _create_test_app(fake_db: _FakeSession, user_id: uuid.UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(conversations_routes.router, prefix="/api/v1/conversations")
    app.dependency_overrides[get_current_user] = lambda: _fake_user(user_id)

    def _override_db() -> Iterable[_FakeSession]:
        yield fake_db

    app.dependency_overrides[get_db] = _override_db
    return app


def test_send_message_logs_mode_and_model_changes_as_system_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    video_id = uuid.uuid4()
    now = datetime.utcnow()

    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Test Conversation",
        selected_video_ids=[video_id],
        message_count=0,
        total_tokens_used=0,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    sources = [
        ConversationSource(
            conversation_id=conversation_id,
            video_id=video_id,
            is_selected=True,
            added_via="manual",
        )
    ]

    previous_user_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content="Previous question",
        token_count=2,
        created_at=now - timedelta(minutes=4),
        message_metadata={"mode": "summarize", "model": "old-model"},
    )

    videos = [
        Video(
            id=video_id,
            user_id=user_id,
            youtube_id="abc123",
            youtube_url="https://youtube.com/watch?v=abc123",
            title="Sample Video",
            status="completed",
            is_deleted=False,
            tags=[],
        )
    ]

    chunks = [
        Chunk(
            id=uuid.uuid4(),
            video_id=video_id,
            user_id=user_id,
            chunk_index=0,
            text="A relevant transcript snippet.",
            token_count=5,
            start_timestamp=0.0,
            end_timestamp=10.0,
            duration_seconds=10.0,
        )
    ]

    fake_db = _FakeSession(
        conversation=conversation,
        sources=sources,
        messages=[previous_user_message],
        videos=videos,
        chunks=chunks,
    )

    captured_llm_messages: dict[str, Any] = {}

    def _fake_embed_text(_text: str) -> np.ndarray:
        return np.zeros(384, dtype=np.float32)

    def _fake_search_chunks(**_kwargs: Any) -> list[Any]:
        return [
            SimpleNamespace(
                chunk_id=None,
                chunk_index=0,
                video_id=video_id,
                text="Chunk text",
                start_timestamp=0.0,
                end_timestamp=10.0,
                score=0.99,
                speakers=[],
                chapter_title=None,
                title=None,
            )
        ]

    def _fake_complete(messages: list[Any], **_kwargs: Any) -> Any:
        captured_llm_messages["messages"] = messages
        return SimpleNamespace(
            content="Assistant response",
            model="new-model",
            provider="dummy",
            usage={"total_tokens": 10},
        )

    monkeypatch.setattr(
        "app.services.embeddings.embedding_service.embed_text",
        _fake_embed_text,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.vector_store.vector_store_service.search_chunks",
        _fake_search_chunks,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.llm_providers.llm_service.complete",
        _fake_complete,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.config.settings.enable_reranking",
        False,
        raising=False,
    )

    app = _create_test_app(fake_db, user_id)
    client = TestClient(app)

    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "message": "New question",
            "stream": False,
            "mode": "deep_dive",
            "model": "new-model",
        },
    )
    assert resp.status_code == 200

    system_contents = [m.content for m in fake_db._messages if m.role == "system"]
    assert any("Mode changed" in content for content in system_contents)
    assert any("Model changed" in content for content in system_contents)

    llm_messages = captured_llm_messages["messages"]
    assert all("FYI:" not in msg.content for msg in llm_messages)


def test_update_sources_logs_added_and_removed_system_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()
    now = datetime.utcnow()

    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Sources Change",
        selected_video_ids=[video_a],
        message_count=0,
        total_tokens_used=0,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    sources = [
        ConversationSource(
            conversation_id=conversation_id,
            video_id=video_a,
            is_selected=True,
            added_via="manual",
        ),
        ConversationSource(
            conversation_id=conversation_id,
            video_id=video_b,
            is_selected=False,
            added_via="manual",
        ),
    ]

    videos = [
        Video(
            id=video_a,
            user_id=user_id,
            youtube_id="a1",
            youtube_url="https://youtube.com/watch?v=a1",
            title="Video A",
            status="completed",
            is_deleted=False,
            tags=[],
        ),
        Video(
            id=video_b,
            user_id=user_id,
            youtube_id="b2",
            youtube_url="https://youtube.com/watch?v=b2",
            title="Video B",
            status="completed",
            is_deleted=False,
            tags=[],
        ),
    ]

    fake_db = _FakeSession(
        conversation=conversation,
        sources=sources,
        messages=[],
        videos=videos,
        chunks=[],
    )

    async def _fake_list_sources(*_args: Any, **_kwargs: Any) -> Any:
        return {
            "total": 0,
            "selected": 0,
            "sources": [],
        }

    def _fake_validate(_db: Any, _user: Any, _ids: Any) -> list[Any]:
        return []

    def _fake_set_sources_selection(  # noqa: PLR0913
        *,
        db: Any,
        conversation: Any,
        selected_video_ids: Any,
        add_video_ids: Any,
        current_user: Any,
    ) -> None:
        selected_set = set(selected_video_ids or [])
        for src in sources:
            src.is_selected = src.video_id in selected_set

    monkeypatch.setattr(
        conversations_routes,
        "list_conversation_sources",
        _fake_list_sources,
        raising=True,
    )
    monkeypatch.setattr(
        conversations_routes, "_validate_videos", _fake_validate, raising=True
    )
    monkeypatch.setattr(
        conversations_routes,
        "_set_sources_selection",
        _fake_set_sources_selection,
        raising=True,
    )

    app = _create_test_app(fake_db, user_id)
    client = TestClient(app)

    resp = client.patch(
        f"/api/v1/conversations/{conversation_id}/sources",
        json={"selected_video_ids": [str(video_b)]},
    )
    assert resp.status_code == 200

    system_contents = [m.content for m in fake_db._messages if m.role == "system"]
    assert any(
        "Added to active sources" in content and "Video B" in content
        for content in system_contents
    )
    assert any(
        "Removed from active sources" in content and "Video A" in content
        for content in system_contents
    )


def test_send_message_resolves_chunk_by_db_id_without_timestamp_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    video_id = uuid.uuid4()
    now = datetime.utcnow()

    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Chunk ID conversation",
        selected_video_ids=[video_id],
        message_count=0,
        total_tokens_used=0,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    sources = [
        ConversationSource(
            conversation_id=conversation_id,
            video_id=video_id,
            is_selected=True,
            added_via="manual",
        )
    ]

    videos = [
        Video(
            id=video_id,
            user_id=user_id,
            youtube_id="chunk-db",
            youtube_url="https://youtube.com/watch?v=chunk-db",
            title="Chunk DB Video",
            status="completed",
            is_deleted=False,
            tags=[],
        )
    ]

    chunk = Chunk(
        id=uuid.uuid4(),
        video_id=video_id,
        user_id=user_id,
        chunk_index=0,
        text="Stored chunk text.",
        token_count=5,
        start_timestamp=0.0,
        end_timestamp=10.0,
        duration_seconds=10.0,
    )

    class RecordingSession(_FakeSession):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.chunk_refs: list[MessageChunkReference] = []

        def add(self, instance: Any) -> None:  # noqa: ANN401
            if isinstance(instance, MessageChunkReference):
                self.chunk_refs.append(instance)
                return
            super().add(instance)

    fake_db = RecordingSession(
        conversation=conversation,
        sources=sources,
        messages=[],
        videos=videos,
        chunks=[chunk],
    )

    def _fake_embed_text(_text: str) -> np.ndarray:
        return np.zeros(384, dtype=np.float32)

    def _fake_search_chunks(**_kwargs: Any) -> list[Any]:
        return [
            SimpleNamespace(
                chunk_id=chunk.id,  # DB id present
                chunk_index=chunk.chunk_index,
                video_id=video_id,
                user_id=user_id,
                text="Retrieved chunk text",
                start_timestamp=123.0,  # Intentionally different
                end_timestamp=456.0,
                score=0.9,
                speakers=[],
                chapter_title=None,
                title=None,
            )
        ]

    def _fake_complete(messages: list[Any], **_kwargs: Any) -> Any:
        return SimpleNamespace(
            content="Assistant response",
            model="db-model",
            provider="dummy",
            usage={"total_tokens": 10},
        )

    monkeypatch.setattr(
        "app.services.embeddings.embedding_service.embed_text",
        _fake_embed_text,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.vector_store.vector_store_service.search_chunks",
        _fake_search_chunks,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.llm_providers.llm_service.complete",
        _fake_complete,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.config.settings.enable_reranking", False, raising=False
    )

    app = _create_test_app(fake_db, user_id)
    client = TestClient(app)

    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "message": "New question",
            "stream": False,
            "mode": "deep_dive",
            "model": "db-model",
        },
    )
    assert resp.status_code == 200

    assert len(fake_db.chunk_refs) == 1
    ref = fake_db.chunk_refs[0]
    assert ref.chunk_id == chunk.id
    # Response should include the citation even though timestamps did not match the DB row
    resp_ref = resp.json()["chunk_references"][0]
    assert resp_ref["chunk_id"] == str(chunk.id)
    assert resp_ref["start_timestamp"] == 123.0


def test_send_message_resolves_chunk_by_index_when_db_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    video_id = uuid.uuid4()
    now = datetime.utcnow()

    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Chunk index conversation",
        selected_video_ids=[video_id],
        message_count=0,
        total_tokens_used=0,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    sources = [
        ConversationSource(
            conversation_id=conversation_id,
            video_id=video_id,
            is_selected=True,
            added_via="manual",
        )
    ]

    videos = [
        Video(
            id=video_id,
            user_id=user_id,
            youtube_id="chunk-index",
            youtube_url="https://youtube.com/watch?v=chunk-index",
            title="Chunk Index Video",
            status="completed",
            is_deleted=False,
            tags=[],
        )
    ]

    chunk = Chunk(
        id=uuid.uuid4(),
        video_id=video_id,
        user_id=user_id,
        chunk_index=1,
        text="Stored chunk index text.",
        token_count=5,
        start_timestamp=0.0,
        end_timestamp=10.0,
        duration_seconds=10.0,
    )

    class RecordingSession(_FakeSession):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.chunk_refs: list[MessageChunkReference] = []

        def add(self, instance: Any) -> None:  # noqa: ANN401
            if isinstance(instance, MessageChunkReference):
                self.chunk_refs.append(instance)
                return
            super().add(instance)

    fake_db = RecordingSession(
        conversation=conversation,
        sources=sources,
        messages=[],
        videos=videos,
        chunks=[chunk],
    )

    def _fake_embed_text(_text: str) -> np.ndarray:
        return np.zeros(384, dtype=np.float32)

    def _fake_search_chunks(**_kwargs: Any) -> list[Any]:
        return [
            SimpleNamespace(
                chunk_id=None,  # Legacy payload without DB id
                chunk_index=chunk.chunk_index,
                video_id=video_id,
                user_id=user_id,
                text="Retrieved chunk text",
                start_timestamp=321.0,  # Different from DB timestamps
                end_timestamp=654.0,
                score=0.88,
                speakers=[],
                chapter_title=None,
                title=None,
            )
        ]

    def _fake_complete(messages: list[Any], **_kwargs: Any) -> Any:
        return SimpleNamespace(
            content="Assistant response",
            model="index-model",
            provider="dummy",
            usage={"total_tokens": 10},
        )

    monkeypatch.setattr(
        "app.services.embeddings.embedding_service.embed_text",
        _fake_embed_text,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.vector_store.vector_store_service.search_chunks",
        _fake_search_chunks,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.llm_providers.llm_service.complete",
        _fake_complete,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.config.settings.enable_reranking", False, raising=False
    )

    app = _create_test_app(fake_db, user_id)
    client = TestClient(app)

    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "message": "Another question",
            "stream": False,
            "mode": "deep_dive",
            "model": "index-model",
        },
    )
    assert resp.status_code == 200

    assert len(fake_db.chunk_refs) == 1
    ref = fake_db.chunk_refs[0]
    assert ref.chunk_id == chunk.id
    resp_ref = resp.json()["chunk_references"][0]
    assert resp_ref["chunk_id"] == str(chunk.id)
    assert resp_ref["start_timestamp"] == 321.0
    assert resp_ref["jump_url"] == "https://youtube.com/watch?v=chunk-index&t=321"
