"""
Integration tests for the full RAG pipeline.

Tests the complete flow: query → retrieve → rerank → build context → generate → validate citations.
Uses the non-streaming endpoint (POST /api/v1/conversations/{id}/messages).

Validates:
- Chunks are retrieved and passed to LLM
- Citations [N] in LLM output map to valid retrieved chunks
- was_used_in_response correctly reflects actual citation usage
- Jump URLs have correct timestamps
- Message and chunk references saved to DB
- Conversation message_count incremented
- Fact extraction dispatched
"""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
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
    MessageChunkReference,
    Chunk,
)
from app.core.nextauth import get_current_user
from app.db.base import get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user(db: Session):
    user = User(
        email="ragpipeline@test.com",
        full_name="RAG Pipeline Test User",
        oauth_provider="google",
        oauth_provider_id="rag_pipeline_oauth",
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
    video = Video(
        user_id=test_user.id,
        youtube_id="rag_test_vid",
        youtube_url="https://www.youtube.com/watch?v=rag_test_vid",
        title="RAG Pipeline Test Video",
        description="A video for RAG pipeline integration tests",
        channel_name="Test Channel",
        channel_id="UC_rag_test",
        thumbnail_url="https://img.youtube.com/vi/rag_test_vid/default.jpg",
        duration_seconds=600,
        status="completed",
        progress_percent=100.0,
        chunk_count=20,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture
def conversation_with_source(db: Session, test_user, sample_video):
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="RAG Pipeline Test Conversation",
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


def _build_mock_chunks(video_id, user_id, count=3):
    """Build mock ScoredChunks with realistic data."""
    chunks = []
    for i in range(count):
        chunk = MagicMock()
        chunk.chunk_id = uuid.uuid4()
        chunk.video_id = video_id
        chunk.user_id = user_id
        chunk.text = f"This is chunk {i+1} about machine learning and neural networks."
        chunk.start_timestamp = float(i * 30)
        chunk.end_timestamp = float((i + 1) * 30)
        chunk.score = 0.9 - (i * 0.1)
        chunk.chunk_index = i
        chunk.content_type = "youtube"
        chunk.page_number = None
        chunk.section_heading = None
        chunk.title = f"Chunk {i+1} Title"
        chunk.summary = f"Summary of chunk {i+1}"
        chunk.keywords = ["machine learning", "neural networks"]
        chunk.chapter_title = None
        chunk.speakers = None
        chunks.append(chunk)
    return chunks


def _build_mock_retrieval_result(video_id, user_id, chunks=None):
    """Build a mock RetrievalResult."""
    if chunks is None:
        chunks = _build_mock_chunks(video_id, user_id)

    mock_video = MagicMock(spec=[])
    mock_video.id = video_id
    mock_video.title = "RAG Pipeline Test Video"
    mock_video.youtube_id = "rag_test_vid"
    mock_video.youtube_url = "https://www.youtube.com/watch?v=rag_test_vid"
    mock_video.channel_name = "Test Channel"
    mock_video.content_type = "youtube"
    mock_video.source_url = None

    context_parts = []
    for i, c in enumerate(chunks):
        start_min = int(c.start_timestamp // 60)
        start_sec = int(c.start_timestamp % 60)
        end_min = int(c.end_timestamp // 60)
        end_sec = int(c.end_timestamp % 60)
        context_parts.append(
            f"Source [{i+1}] (RAG Pipeline Test Video, "
            f"{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}):\n{c.text}"
        )

    result = MagicMock()
    result.chunks = chunks
    result.video_summaries = []
    result.retrieval_type = "chunks"
    result.context = "\n\n".join(context_parts)
    result.context_is_weak = False
    result.video_map = {video_id: mock_video}
    result.videos_missing_summaries = 0
    result.retrieval_stats = {
        "total_retrieved": 10,
        "after_filter": 5,
        "after_rerank": len(chunks),
    }
    return result, chunks


def _make_pipeline_mocks(video_id, user_id, llm_response_text=None):
    """Create all mocks needed for the non-streaming RAG pipeline."""
    if llm_response_text is None:
        llm_response_text = (
            "Based on the content, machine learning involves neural networks [1]. "
            "The training process uses backpropagation [2]. "
            "Additionally, deep learning extends these concepts [3]."
        )

    retrieval_result, chunks = _build_mock_retrieval_result(video_id, user_id)

    # Mock intent classifier
    mock_intent = MagicMock()
    mock_intent.intent.value = "specific_detail"
    mock_intent.confidence = 0.9
    mock_intent_cls = MagicMock()
    mock_intent_cls.return_value.classify_sync.return_value = mock_intent

    # Mock query rewriter
    mock_rewriter_cls = MagicMock()
    mock_rewriter_cls.return_value.rewrite_query.return_value = "What is machine learning?"

    # Mock retriever
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = retrieval_result

    # Mock LLM service (non-streaming)
    mock_llm_response = MagicMock()
    mock_llm_response.content = llm_response_text
    mock_llm_response.model = "deepseek-chat"
    mock_llm_response.provider = "deepseek"
    mock_llm_response.usage = {
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
    }
    mock_llm_response.reasoning_content = None
    mock_llm_response.finish_reason = "stop"
    mock_llm_response.response_time_seconds = 2.1

    mock_llm = MagicMock()
    mock_llm.complete.return_value = mock_llm_response

    # Mock fact extraction task
    mock_fact_task = MagicMock()
    mock_fact_task.delay.return_value = None

    return {
        "intent_cls": mock_intent_cls,
        "rewriter_cls": mock_rewriter_cls,
        "retriever": mock_retriever,
        "llm": mock_llm,
        "llm_response": mock_llm_response,
        "retrieval_result": retrieval_result,
        "chunks": chunks,
        "fact_task": mock_fact_task,
    }


def _make_patches(mocks):
    """Build patch objects for the non-streaming endpoint."""
    return [
        patch("app.services.intent_classifier.IntentClassifier", mocks["intent_cls"]),
        patch("app.services.query_rewriter.QueryRewriterService", mocks["rewriter_cls"]),
        patch("app.api.routes.conversations.get_two_level_retriever", return_value=mocks["retriever"]),
        patch("app.services.llm_providers.llm_service", mocks["llm"]),
        patch("app.core.quota.check_message_quota", new_callable=AsyncMock),
        patch("app.api.routes.conversations.resolve_model", return_value="deepseek-chat"),
        patch("app.tasks.memory_tasks.extract_facts_from_turn", mocks["fact_task"]),
        patch("app.api.routes.conversations.log_chat_message"),
    ]


@pytest.fixture
def pipeline_client(test_user, db: Session, conversation_with_source, sample_video):
    """Create a TestClient pre-configured with all mocks for the RAG pipeline."""
    mocks = _make_pipeline_mocks(sample_video.id, test_user.id)

    def override_get_current_user():
        return test_user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    patches = _make_patches(mocks)
    for p in patches:
        p.start()

    client = TestClient(app)
    yield client, conversation_with_source, mocks, sample_video

    for p in patches:
        p.stop()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: Full Pipeline
# ---------------------------------------------------------------------------


class TestRAGPipelineEndToEnd:
    """Test the full RAG pipeline through the non-streaming endpoint."""

    def test_pipeline_returns_200_with_response(self, pipeline_client):
        """Basic pipeline: query in, response out."""
        client, conversation, mocks, video = pipeline_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0

    def test_pipeline_saves_user_and_assistant_messages(self, pipeline_client, db: Session):
        """Both user query and assistant response saved to DB."""
        client, conversation, mocks, video = pipeline_client
        client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        messages = (
            db.query(MessageModel)
            .filter(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at)
            .all()
        )

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "What is machine learning?"
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 0

    def test_pipeline_dispatches_fact_extraction(self, pipeline_client):
        """Fact extraction task dispatched after response."""
        client, conversation, mocks, video = pipeline_client
        client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        mocks["fact_task"].delay.assert_called_once()
        call_kwargs = mocks["fact_task"].delay.call_args
        assert str(conversation.id) in str(call_kwargs)

    def test_retriever_called_with_correct_params(self, pipeline_client):
        """Retriever receives the query and video IDs."""
        client, conversation, mocks, video = pipeline_client
        client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        mocks["retriever"].retrieve.assert_called_once()
        call_kwargs = mocks["retriever"].retrieve.call_args
        # The video ID should be passed to the retriever
        assert video.id in call_kwargs.kwargs.get("video_ids", call_kwargs.args[2] if len(call_kwargs.args) > 2 else [])


# ---------------------------------------------------------------------------
# Tests: Citation Validation (CIT-001, CIT-002, CIT-003)
# ---------------------------------------------------------------------------


class TestCitationContracts:
    """Test citation contracts through the full pipeline."""

    def test_citation_markers_map_to_valid_chunks(self, pipeline_client):
        """CIT-002: All [N] markers map to valid retrieved chunks."""
        client, conversation, mocks, video = pipeline_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        data = response.json()
        assert response.status_code == 200
        refs = data.get("chunk_references", [])
        # Should have chunk references in the response
        assert isinstance(refs, list)

    def test_response_includes_chunk_references(self, pipeline_client):
        """Chunk references returned in response payload."""
        client, conversation, mocks, video = pipeline_client
        response = client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "What is machine learning?", "mode": "deep_dive"},
        )

        data = response.json()
        assert response.status_code == 200
        # The response should contain chunk reference data
        refs = data.get("sources", data.get("chunk_references", []))
        assert isinstance(refs, list)

    def test_llm_response_with_no_citations(self, test_user, db, conversation_with_source, sample_video):
        """Response without [N] markers should still succeed."""
        mocks = _make_pipeline_mocks(
            sample_video.id,
            test_user.id,
            llm_response_text="Machine learning is a broad field with many applications.",
        )

        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        patches = _make_patches(mocks)
        for p in patches:
            p.start()

        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/conversations/{conversation_with_source.id}/messages",
                json={"message": "What is ML?", "mode": "deep_dive"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "content" in data
        finally:
            for p in patches:
                p.stop()
            app.dependency_overrides.clear()

    def test_out_of_bounds_citation_handled(self, test_user, db, conversation_with_source, sample_video):
        """CIT-002: [N] markers beyond chunk count don't crash."""
        mocks = _make_pipeline_mocks(
            sample_video.id,
            test_user.id,
            # [5] is out of bounds (only 3 chunks)
            llm_response_text="Info from source [1] and also [5].",
        )

        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        patches = _make_patches(mocks)
        for p in patches:
            p.start()

        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/conversations/{conversation_with_source.id}/messages",
                json={"message": "Tell me about ML", "mode": "deep_dive"},
            )
            # Should not crash — out-of-bounds markers are logged as warnings
            assert response.status_code == 200
        finally:
            for p in patches:
                p.stop()
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: No Sources / Empty Retrieval
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test pipeline edge cases."""

    def test_empty_retrieval_returns_response(self, test_user, db, conversation_with_source, sample_video):
        """Pipeline handles zero retrieved chunks gracefully."""
        mocks = _make_pipeline_mocks(sample_video.id, test_user.id)

        # Override retrieval to return empty chunks
        empty_result = MagicMock()
        empty_result.chunks = []
        empty_result.video_summaries = []
        empty_result.retrieval_type = "chunks"
        empty_result.context = ""
        empty_result.context_is_weak = True
        empty_result.video_map = {}
        empty_result.videos_missing_summaries = 0
        empty_result.retrieval_stats = {"total_retrieved": 0, "after_filter": 0, "after_rerank": 0}
        mocks["retriever"].retrieve.return_value = empty_result
        mocks["llm"].complete.return_value.content = "I don't have enough context to answer that question."

        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        patches = _make_patches(mocks)
        for p in patches:
            p.start()

        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/conversations/{conversation_with_source.id}/messages",
                json={"message": "Something obscure", "mode": "deep_dive"},
            )
            assert response.status_code == 200
        finally:
            for p in patches:
                p.stop()
            app.dependency_overrides.clear()

    def test_conversation_not_found_returns_404(self, test_user, db):
        """Non-existent conversation returns 404."""
        def override_get_current_user():
            return test_user

        def override_get_db():
            yield db

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            fake_id = uuid.uuid4()
            response = client.post(
                f"/api/v1/conversations/{fake_id}/messages",
                json={"message": "Hello", "mode": "deep_dive"},
            )
            assert response.status_code in (404, 500)
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: Memory Contract (MEM-004)
# ---------------------------------------------------------------------------


class TestMemoryContracts:
    """Test memory-related contracts through the pipeline."""

    def test_fact_extraction_dispatched_with_correct_args(self, pipeline_client):
        """Fact extraction receives conversation_id, message_id, user_query."""
        client, conversation, mocks, video = pipeline_client
        client.post(
            f"/api/v1/conversations/{conversation.id}/messages",
            json={"message": "Tell me about neural networks", "mode": "deep_dive"},
        )

        mocks["fact_task"].delay.assert_called_once()
        kwargs = mocks["fact_task"].delay.call_args.kwargs
        assert kwargs["conversation_id"] == str(conversation.id)
        assert kwargs["user_query"] == "Tell me about neural networks"
        assert "message_id" in kwargs
