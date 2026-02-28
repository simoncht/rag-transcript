"""
Integration tests for the streaming chat endpoint.

Tests the SSE (Server-Sent Events) streaming response from:
  POST /api/v1/conversations/{conversation_id}/messages/stream

Validates:
- SSE event format (content, done, error, followup_questions, status)
- Event ordering guarantees
- Done event completeness (sources, confidence, retrieval_metadata)
- Error handling (no sources, invalid conversation)
- Abort/disconnect handling
"""
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    User,
    Video,
    Conversation,
    ConversationSource as ConversationSourceModel,
    Message as MessageModel,
)
from app.core.nextauth import get_current_user
from app.db.base import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of JSON payloads."""
    events = []
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user(db: Session):
    """Create a test user for streaming tests."""
    user = User(
        email="streamtest@test.com",
        full_name="Stream Test User",
        oauth_provider="google",
        oauth_provider_id="stream_test_oauth_id",
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
def sample_video(db: Session, test_user):
    """Create a completed video for use as a conversation source."""
    video = Video(
        user_id=test_user.id,
        youtube_id="stream_test_vid",
        youtube_url="https://www.youtube.com/watch?v=stream_test_vid",
        title="Stream Test Video",
        description="A video for streaming tests",
        channel_name="Test Channel",
        channel_id="UC_stream_test",
        thumbnail_url="https://img.youtube.com/vi/stream_test_vid/default.jpg",
        duration_seconds=300,
        status="completed",
        progress_percent=100.0,
        chunk_count=10,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture
def conversation_with_source(db: Session, test_user, sample_video):
    """Create a conversation with a selected video source."""
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Stream Test Conversation",
        message_count=0,
        total_tokens_used=0,
    )
    db.add(conversation)
    db.flush()

    source = ConversationSourceModel(
        conversation_id=conversation.id,
        video_id=sample_video.id,
        is_selected=True,
    )
    db.add(source)
    db.commit()
    db.refresh(conversation)
    return conversation


@pytest.fixture
def conversation_no_sources(db: Session, test_user):
    """Create a conversation with no selected sources."""
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="No Sources Conversation",
        message_count=0,
        total_tokens_used=0,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _build_mock_retrieval_result(video_id: uuid.UUID, user_id: uuid.UUID):
    """Build a mock RetrievalResult with realistic chunk data."""
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = uuid.uuid4()
    mock_chunk.video_id = video_id
    mock_chunk.user_id = user_id
    mock_chunk.text = "This is a test chunk about streaming endpoints."
    mock_chunk.start_timestamp = 10.0
    mock_chunk.end_timestamp = 25.0
    mock_chunk.score = 0.85
    mock_chunk.chunk_index = 0
    mock_chunk.content_type = "youtube"
    mock_chunk.page_number = None
    mock_chunk.section_heading = None
    mock_chunk.title = "Test Chunk"
    mock_chunk.summary = "Summary of test chunk"
    mock_chunk.keywords = ["streaming", "test"]
    mock_chunk.chapter_title = None
    mock_chunk.speakers = None

    mock_video = MagicMock(spec=[])  # spec=[] prevents auto-creating attrs
    mock_video.id = video_id
    mock_video.title = "Stream Test Video"
    mock_video.youtube_id = "stream_test_vid"
    mock_video.youtube_url = "https://www.youtube.com/watch?v=stream_test_vid"
    mock_video.channel_name = "Test Channel"
    mock_video.content_type = "youtube"
    mock_video.source_url = None

    result = MagicMock()
    result.chunks = [mock_chunk]
    result.video_summaries = []
    result.retrieval_type = "chunks"
    result.context = "Source [1] (Stream Test Video, 00:10-00:25):\nThis is a test chunk about streaming endpoints."
    result.context_is_weak = False
    result.video_map = {video_id: mock_video}
    result.videos_missing_summaries = 0
    result.retrieval_stats = {
        "total_retrieved": 5,
        "after_filter": 3,
        "after_rerank": 1,
    }
    return result


def _make_stream_mocks(video_id, user_id):
    """Create all the mocks needed for the streaming endpoint.

    Returns dict of mocks.  The 'intent_classifier_cls' and 'rewriter_cls'
    entries are class-level mocks (IntentClassifier / QueryRewriterService)
    whose *instances* (`.return_value`) carry the method stubs.
    """
    retrieval_result = _build_mock_retrieval_result(video_id, user_id)

    # Mock intent classifier (patched as the *class* IntentClassifier)
    mock_intent = MagicMock()
    mock_intent.intent.value = "specific_detail"
    mock_intent.confidence = 0.9
    mock_intent_classifier_cls = MagicMock()
    mock_intent_classifier_cls.return_value.classify_sync.return_value = mock_intent

    # Mock query rewriter (patched as the *class* QueryRewriterService)
    mock_rewriter_cls = MagicMock()
    mock_rewriter_cls.return_value.rewrite_query.return_value = "What is streaming?"

    # Mock retriever (get_two_level_retriever returns the retriever instance)
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = retrieval_result

    # Mock LLM service streaming (yields chunks)
    mock_llm = MagicMock()
    mock_llm.stream_complete.return_value = iter([
        "This is ",
        "a streamed ",
        "response about ",
        "streaming.",
    ])
    mock_llm.get_last_stream_reasoning_content.return_value = None

    # Mock followup questions
    mock_followups = ["What else about streaming?", "How does SSE work?"]

    # Mock fact extraction (patched as the *class* FactExtractionService)
    mock_fact_cls = MagicMock()
    mock_fact_cls.return_value.extract_facts.return_value = []

    return {
        "intent_classifier_cls": mock_intent_classifier_cls,
        "rewriter_cls": mock_rewriter_cls,
        "retriever": mock_retriever,
        "llm": mock_llm,
        "followups": mock_followups,
        "retrieval_result": retrieval_result,
        "fact_cls": mock_fact_cls,
    }


def _make_patches(mocks, model_name, test_session_factory):
    """Build the standard list of mock.patch objects for the streaming endpoint."""
    return [
        patch("app.services.intent_classifier.IntentClassifier", mocks["intent_classifier_cls"]),
        patch("app.services.query_rewriter.QueryRewriterService", mocks["rewriter_cls"]),
        patch("app.api.routes.conversations.get_two_level_retriever", return_value=mocks["retriever"]),
        patch("app.services.llm_providers.llm_service", mocks["llm"]),
        patch("app.core.quota.check_message_quota", new_callable=AsyncMock),
        patch("app.api.routes.conversations.resolve_model", return_value=model_name),
        patch("app.services.followup_questions.generate_followup_questions", return_value=mocks["followups"]),
        patch("app.services.fact_extraction.FactExtractionService", mocks["fact_cls"]),
        patch("app.api.routes.conversations.log_chat_message"),
        # Patch SessionLocal so generate_stream()'s direct SessionLocal() calls
        # use the test SQLite engine instead of production PostgreSQL
        patch("app.db.base.SessionLocal", test_session_factory),
    ]


@pytest.fixture
def stream_client(test_user, db: Session, conversation_with_source, sample_video, test_session_factory):
    """
    Create a TestClient pre-configured with all mocks for streaming.

    Yields (client, conversation, mocks) so tests can inspect mock state.
    """
    mocks = _make_stream_mocks(sample_video.id, test_user.id)

    def override_get_current_user():
        return test_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    patches = _make_patches(mocks, "deepseek-chat", test_session_factory)

    for p in patches:
        p.start()

    client = TestClient(app)
    yield client, conversation_with_source, mocks

    for p in patches:
        p.stop()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStreamContentEventsFormat:
    """Test 1: Validate SSE content event JSON shape."""

    def test_stream_content_events_format(self, stream_client):
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = _parse_sse_events(response.text)
        content_events = [e for e in events if e.get("type") == "content"]

        # There should be at least one content event
        assert len(content_events) > 0, "Expected at least one content event"

        for event in content_events:
            # Each content event must have exactly "type" and "content" keys
            assert "type" in event, "Content event missing 'type' field"
            assert "content" in event, "Content event missing 'content' field"
            assert event["type"] == "content"
            assert isinstance(event["content"], str)
            assert len(event["content"]) > 0, "Content event has empty content"


class TestStreamDoneEventFields:
    """Test 2: Validate done event completeness."""

    def test_stream_done_event_has_required_fields(self, stream_client):
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e.get("type") == "done"]

        assert len(done_events) == 1, "Expected exactly one done event"
        done = done_events[0]

        # Required top-level fields
        required_fields = [
            "type",
            "message_id",
            "sources",
            "token_count",
            "response_time_seconds",
            "confidence",
            "retrieval_metadata",
            "new_facts_count",
        ]
        for field_name in required_fields:
            assert field_name in done, f"Done event missing required field: {field_name}"

        # Validate types
        assert done["type"] == "done"
        assert isinstance(done["message_id"], str)
        # message_id should be a valid UUID
        uuid.UUID(done["message_id"])
        assert isinstance(done["sources"], list)
        assert isinstance(done["token_count"], int)
        assert isinstance(done["response_time_seconds"], (int, float))
        assert isinstance(done["confidence"], dict)
        assert isinstance(done["retrieval_metadata"], dict)
        assert isinstance(done["new_facts_count"], int)

        # Sources should contain citation data
        assert len(done["sources"]) >= 1, "Expected at least one source in done event"
        source = done["sources"][0]
        assert "video_id" in source
        assert "video_title" in source
        assert "relevance_score" in source
        assert "rank" in source
        assert "text_snippet" in source


class TestStreamErrorOnNoSources:
    """Test 3: Validate error when no sources are selected."""

    def test_stream_error_on_no_sources(self, test_user, db: Session, conversation_no_sources):
        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        with patch("app.core.quota.check_message_quota", new_callable=AsyncMock):
            client = TestClient(app)
            response = client.post(
                f"/api/v1/conversations/{conversation_no_sources.id}/messages/stream",
                json={"message": "Hello?", "mode": "summarize"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = _parse_sse_events(response.text)
        assert len(events) >= 1, "Expected at least one event"

        # The only event should be an error event about no sources
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1, "Expected exactly one error event"
        assert "No sources selected" in error_events[0]["error"]


class TestStreamEventOrdering:
    """Test 4: Validate events come in correct order."""

    def test_stream_event_ordering(self, stream_client):
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        events = _parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        # Basic ordering: content events come before done, done comes before followup_questions
        # Find index boundaries
        content_indices = [i for i, t in enumerate(event_types) if t == "content"]
        done_indices = [i for i, t in enumerate(event_types) if t == "done"]
        followup_indices = [i for i, t in enumerate(event_types) if t == "followup_questions"]

        assert len(content_indices) > 0, "Must have content events"
        assert len(done_indices) == 1, "Must have exactly one done event"

        # All content events must come before the done event
        last_content_idx = max(content_indices)
        done_idx = done_indices[0]
        assert last_content_idx < done_idx, (
            f"Last content event (idx={last_content_idx}) must come before "
            f"done event (idx={done_idx})"
        )

        # If followup_questions exist, they must come after done
        if followup_indices:
            first_followup_idx = min(followup_indices)
            assert first_followup_idx > done_idx, (
                f"followup_questions (idx={first_followup_idx}) must come after "
                f"done event (idx={done_idx})"
            )

        # No error events in a successful stream
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 0, "Successful stream should not have error events"


class TestStreamStatusEvents:
    """Test 5: Validate status events shape and ordering.

    The streaming endpoint emits status events with "stage" field:
      {"type": "status", "stage": "analyzing", "message": "..."}
    """

    def test_stream_status_events(self, stream_client):
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        events = _parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        status_events = [e for e in events if e.get("type") == "status"]

        assert len(status_events) > 0, "Expected at least one status event"

        for event in status_events:
            assert "stage" in event, "Status event missing 'stage' field"
            assert isinstance(event["stage"], str)
            known_stages = {"analyzing", "searching", "generating", "reranking", "grading"}
            assert event["stage"] in known_stages, (
                f"Unknown stage '{event['stage']}', expected one of {known_stages}"
            )
            assert "message" in event, "Status event missing 'message' field"

        # Status events must appear before content events
        status_indices = [i for i, t in enumerate(event_types) if t == "status"]
        content_indices = [i for i, t in enumerate(event_types) if t == "content"]
        if content_indices:
            first_content_idx = min(content_indices)
            last_status_idx = max(status_indices)
            assert last_status_idx < first_content_idx, (
                "All status events should precede content events"
            )


class TestStreamIncludesConfidence:
    """Test 6: Validate confidence info in done event."""

    def test_stream_includes_confidence(self, stream_client):
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

        confidence = done_events[0]["confidence"]

        # Validate confidence shape
        assert "level" in confidence
        assert confidence["level"] in ("strong", "moderate", "limited"), (
            f"Unexpected confidence level: {confidence['level']}"
        )
        assert "avg_relevance" in confidence
        assert isinstance(confidence["avg_relevance"], (int, float))
        assert 0.0 <= confidence["avg_relevance"] <= 1.0

        assert "chunk_count" in confidence
        assert isinstance(confidence["chunk_count"], int)
        assert confidence["chunk_count"] >= 0

        assert "unique_videos" in confidence
        assert isinstance(confidence["unique_videos"], int)
        assert confidence["unique_videos"] >= 0

        # With our mock data (1 chunk, score=0.85), confidence should be computed
        assert confidence["chunk_count"] >= 1
        assert confidence["unique_videos"] >= 1


class TestStreamAbortHandling:
    """Test 7: Validate clean abort / error during streaming."""

    def test_stream_abort_handling(self, test_user, db: Session, conversation_with_source, sample_video, test_session_factory):
        """When the LLM raises an exception mid-stream, the endpoint emits an error event."""
        mocks = _make_stream_mocks(sample_video.id, test_user.id)

        # Make the LLM raise an exception after yielding one chunk
        def _exploding_generator(*args, **kwargs):
            yield "Partial response..."
            raise RuntimeError("LLM connection lost")

        mocks["llm"].stream_complete.side_effect = _exploding_generator

        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        patches = _make_patches(mocks, "deepseek-chat", test_session_factory)
        for p in patches:
            p.start()

        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/conversations/{conversation_with_source.id}/messages/stream",
                json={"message": "What is streaming?", "mode": "summarize"},
            )

            assert response.status_code == 200
            events = _parse_sse_events(response.text)

            # Should have at least one content event (the partial chunk) and one error event
            content_events = [e for e in events if e.get("type") == "content"]
            error_events = [e for e in events if e.get("type") == "error"]

            assert len(content_events) >= 1, "Should have at least one partial content event"
            assert len(error_events) == 1, "Should have exactly one error event"
            assert "error" in error_events[0]
            assert isinstance(error_events[0]["error"], str)
            assert len(error_events[0]["error"]) > 0

            # No done event should be emitted when an error occurs
            done_events = [e for e in events if e.get("type") == "done"]
            assert len(done_events) == 0, "Error stream should not have a done event"
        finally:
            for p in patches:
                p.stop()
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Reasoner max_tokens integration tests
# ---------------------------------------------------------------------------


def _build_stream_client(test_user, db, conversation_with_source, sample_video, test_session_factory, model_name):
    """Build a TestClient with all streaming mocks, parameterized by model_name.

    Returns (client, conversation, mocks, patches) — caller must stop patches.
    """
    mocks = _make_stream_mocks(sample_video.id, test_user.id)

    def override_get_current_user():
        return test_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    patches = _make_patches(mocks, model_name, test_session_factory)

    for p in patches:
        p.start()

    client = TestClient(app)
    return client, conversation_with_source, mocks, patches


@pytest.fixture
def stream_client_reasoner(test_user, db, conversation_with_source, sample_video, test_session_factory):
    """Create a TestClient where resolve_model returns 'deepseek-reasoner'."""
    client, conversation, mocks, patches = _build_stream_client(
        test_user, db, conversation_with_source, sample_video, test_session_factory,
        model_name="deepseek-reasoner",
    )
    yield client, conversation, mocks

    for p in patches:
        p.stop()
    app.dependency_overrides.clear()


class TestReasonerMaxTokensIntegration:
    """Integration tests verifying max_tokens passed to stream_complete matches the resolved model."""

    def test_reasoner_model_uses_higher_max_tokens(self, stream_client_reasoner):
        """stream_complete is called with max_tokens=8192 when model is deepseek-reasoner."""
        client, conversation, mocks = stream_client_reasoner
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "Explain quantum computing", "mode": "summarize"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        # Ensure the stream actually completed (no errors)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 0, f"Unexpected error: {error_events}"

        # Verify max_tokens passed to stream_complete
        mocks["llm"].stream_complete.assert_called_once()
        call_kwargs = mocks["llm"].stream_complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 8192, (
            f"Expected max_tokens=8192 for reasoner, got {call_kwargs['max_tokens']}"
        )

    def test_chat_model_uses_standard_max_tokens(self, stream_client):
        """stream_complete is called with max_tokens=1500 when model is deepseek-chat."""
        client, conversation, mocks = stream_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "What is streaming?", "mode": "summarize"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 0, f"Unexpected error: {error_events}"

        # Verify max_tokens passed to stream_complete
        mocks["llm"].stream_complete.assert_called_once()
        call_kwargs = mocks["llm"].stream_complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1500, (
            f"Expected max_tokens=1500 for chat model, got {call_kwargs['max_tokens']}"
        )

    def test_reasoner_stream_produces_valid_events(self, stream_client_reasoner):
        """Full SSE stream with reasoner model produces content + done events, no errors."""
        client, conversation, mocks = stream_client_reasoner
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/stream",
            json={"message": "Explain quantum computing", "mode": "summarize"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = _parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        # Must have content and done events
        assert "content" in event_types, "Reasoner stream missing content events"
        assert "done" in event_types, "Reasoner stream missing done event"

        # No errors
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 0, f"Reasoner stream had errors: {error_events}"

        # Done event should have standard fields
        done = [e for e in events if e.get("type") == "done"][0]
        assert "message_id" in done
        assert "sources" in done
        assert "confidence" in done
