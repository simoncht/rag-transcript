import uuid
from datetime import datetime

import numpy as np
import pytest

from app.models import Chunk
from app.services.insights import ConversationInsightsService, TopicChunk, TopicNode


class _FakeEmbeddingService:
    def embed_batch(
        self, texts: list[str], batch_size=None, show_progress: bool = False
    ):  # noqa: ANN001
        vectors: list[np.ndarray] = []
        for text in texts:
            t = (text or "").lower()
            if "alpha" in t:
                vec = np.array([1.0, 0.0, 0.0], dtype=float)
            elif "beta" in t:
                vec = np.array([0.0, 1.0, 0.0], dtype=float)
            elif "gamma" in t:
                vec = np.array([0.0, 0.0, 1.0], dtype=float)
            else:
                vec = np.array([1.0, 1.0, 1.0], dtype=float)
            norm = float(np.linalg.norm(vec))
            vectors.append(vec if norm == 0 else vec / norm)
        return vectors


def _make_chunk(
    *,
    video_id: uuid.UUID,
    user_id: uuid.UUID,
    chunk_index: int,
    keywords: list[str] | None = None,
    chapter_index: int | None = None,
    chapter_title: str | None = None,
) -> Chunk:
    start = float(chunk_index * 10)
    end = float(start + 10)
    return Chunk(
        id=uuid.uuid4(),
        video_id=video_id,
        user_id=user_id,
        chunk_index=chunk_index,
        text=f"Chunk {chunk_index} text about {keywords[0] if keywords else 'misc'}",
        token_count=10,
        start_timestamp=start,
        end_timestamp=end,
        duration_seconds=end - start,
        chapter_index=chapter_index,
        chapter_title=chapter_title,
        chunk_title=f"Title {chunk_index}",
        chunk_summary=f"Summary {chunk_index}",
        keywords=keywords or [],
        created_at=datetime.utcnow(),
    )


def test_parse_topics_response_strips_markdown_code_fences() -> None:
    service = ConversationInsightsService(embedding_service=_FakeEmbeddingService())

    topics = service._parse_topics_response(
        "```json\n"
        '{ "topics": ['
        '{"id":"topic-1","label":"Neural Nets","description":"Basics","keywords":["layers","activation"]}'
        "] }\n"
        "```"
    )

    assert len(topics) == 1
    assert topics[0].id == "topic-1"
    assert topics[0].label == "Neural Nets"
    assert "activation" in topics[0].keywords


def test_sample_chunks_for_extraction_evenly_distributes_across_videos() -> None:
    service = ConversationInsightsService(embedding_service=_FakeEmbeddingService())
    user_id = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()

    chunks: list[Chunk] = []
    for i in range(30):
        chunks.append(
            _make_chunk(
                video_id=video_a, user_id=user_id, chunk_index=i, keywords=["alpha"]
            )
        )
        chunks.append(
            _make_chunk(
                video_id=video_b, user_id=user_id, chunk_index=i, keywords=["beta"]
            )
        )

    sampled = service._sample_chunks_for_extraction(chunks, max_chunks=10)

    assert len(sampled) == 10
    video_ids = {c.video_id for c in sampled}
    assert video_a in video_ids
    assert video_b in video_ids


def test_build_graph_structure_creates_mind_map_tree() -> None:
    service = ConversationInsightsService(embedding_service=_FakeEmbeddingService())

    video_a_id = uuid.uuid4()
    video_b_id = uuid.uuid4()

    topics = [
        TopicNode(
            id="topic-1", label="Topic One", description="Desc", keywords=["alpha"]
        ),
        TopicNode(
            id="topic-2", label="Topic Two", description="Desc", keywords=["beta"]
        ),
    ]

    tc_a = TopicChunk(
        chunk_id=uuid.uuid4(),
        video_id=video_a_id,
        video_title="Video A",
        start_timestamp=0.0,
        end_timestamp=10.0,
        timestamp_display="00:00 - 00:10",
        text="text",
        chunk_title=None,
        chapter_title="Chapter Alpha",
        chunk_summary="About alpha",
    )
    tc_b = TopicChunk(
        chunk_id=uuid.uuid4(),
        video_id=video_b_id,
        video_title="Video B",
        start_timestamp=0.0,
        end_timestamp=10.0,
        timestamp_display="00:00 - 00:10",
        text="text",
        chunk_title=None,
        chapter_title="Chapter Beta",
        chunk_summary="About beta",
    )
    tc_c = TopicChunk(
        chunk_id=uuid.uuid4(),
        video_id=video_b_id,
        video_title="Video B",
        start_timestamp=10.0,
        end_timestamp=20.0,
        timestamp_display="00:10 - 00:20",
        text="text",
        chunk_title=None,
        chapter_title="Chapter Gamma",
        chunk_summary="About gamma",
    )

    nodes, edges, expanded = service._build_graph_structure(
        root_label="Conversation",
        topics=topics,
        topic_chunks={"topic-1": [tc_a], "topic-2": [tc_b, tc_c]},
        enable_llm_labels=False,
    )

    assert any(n["type"] == "root" for n in nodes)
    assert sum(1 for n in nodes if n["type"] == "topic") == 2
    assert sum(1 for n in nodes if n["type"] == "subtopic") == 2
    assert sum(1 for n in nodes if n["type"] == "point") == 2
    assert sum(1 for n in nodes if n["type"] == "moment") == 3

    assert len(edges) == 9
    assert any(
        e["source"] == "insights-root" and e["target"] == "topic-1" for e in edges
    )
    assert any(
        e["source"] == "insights-root" and e["target"] == "topic-2" for e in edges
    )

    assert len(expanded["topic-1-sub-1"]) >= 1


def test_map_topics_to_chunks_tracks_totals_across_all_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.vector_store.vector_store_service.fetch_video_chunk_vectors",
        lambda **kwargs: {},
        raising=True,
    )

    service = ConversationInsightsService(embedding_service=_FakeEmbeddingService())
    user_id = uuid.uuid4()
    video_a = uuid.uuid4()
    video_b = uuid.uuid4()

    topics = [
        TopicNode(id="topic-1", label="Alpha Topic", description="Desc", keywords=["alpha"]),
        TopicNode(id="topic-2", label="Beta Topic", description="Desc", keywords=["beta"]),
    ]

    chunks: list[Chunk] = []
    for i in range(20):
        chunks.append(_make_chunk(video_id=video_a, user_id=user_id, chunk_index=i, keywords=["alpha"]))
    for i in range(10):
        chunks.append(_make_chunk(video_id=video_b, user_id=user_id, chunk_index=i, keywords=["beta"]))

    videos_by_id = {
        video_a: type("V", (), {"title": "Video A"})(),
        video_b: type("V", (), {"title": "Video B"})(),
    }

    topic_chunks, _, diagnostics, totals = service._map_topics_to_chunks(
        topics,
        chunks,
        videos_by_id,
        user_id=user_id,
        max_chunks_per_topic=3,
    )

    assert diagnostics["total_chunks_considered"] == 30
    assert diagnostics["assigned_chunks"] == 30
    assert totals["topic-1"] == 20
    assert totals["topic-2"] == 10
    assert len(topic_chunks["topic-1"]) == 3
    assert len(topic_chunks["topic-2"]) == 3

    nodes, _, _ = service._build_graph_structure(
        root_label="Conversation",
        topics=topics,
        topic_chunks=topic_chunks,
        topic_total_counts=totals,
        enable_llm_labels=False,
    )

    topic_nodes = {n["id"]: n for n in nodes if n["type"] == "topic"}
    assert topic_nodes["topic-1"]["data"]["chunk_count"] == 20
    assert topic_nodes["topic-1"]["data"]["evidence_chunk_count"] == 3
    assert topic_nodes["topic-2"]["data"]["chunk_count"] == 10
    assert topic_nodes["topic-2"]["data"]["evidence_chunk_count"] == 3


def test_map_topics_to_chunks_reuses_qdrant_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CountingEmbeddingService(_FakeEmbeddingService):
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed_batch(self, texts: list[str], batch_size=None, show_progress: bool = False):  # noqa: ANN001
            self.calls.append(list(texts))
            return super().embed_batch(texts, batch_size=batch_size, show_progress=show_progress)

    user_id = uuid.uuid4()
    video_a = uuid.uuid4()

    topics = [
        TopicNode(id="topic-1", label="Alpha Topic", description="Desc", keywords=["alpha"]),
    ]

    chunks: list[Chunk] = []
    for i in range(8):
        chunks.append(_make_chunk(video_id=video_a, user_id=user_id, chunk_index=i, keywords=["alpha"]))

    # Pretend Qdrant already has vectors for all chunks.
    indexed = {(c.video_id, int(c.chunk_index)): np.array([1.0, 0.0, 0.0], dtype=float) for c in chunks}

    monkeypatch.setattr(
        "app.services.vector_store.vector_store_service.fetch_video_chunk_vectors",
        lambda **kwargs: indexed,
        raising=True,
    )

    service = ConversationInsightsService(embedding_service=CountingEmbeddingService())
    videos_by_id = {video_a: type("V", (), {"title": "Video A"})()}

    _, _, diagnostics, totals = service._map_topics_to_chunks(
        topics,
        chunks,
        videos_by_id,
        user_id=user_id,
        max_chunks_per_topic=2,
    )

    assert diagnostics["reused_vectors"] == 8
    assert totals["topic-1"] == 8
    # Only the topic embedding call should be needed (chunk embeddings reused).
    assert len(service.embedding_service.calls) == 1
    assert len(service.embedding_service.calls[0]) == 1
