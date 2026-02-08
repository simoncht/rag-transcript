"""
Unit tests for the vector store service.

Tests indexing, search, MMR diversity, video guarantee, proximity, and filter building.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from app.services.vector_store import (
    QdrantVectorStore,
    VectorStoreService,
    ScoredChunk,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_scored_chunk(
    video_id=None, score=0.8, start=0.0, end=10.0, chunk_index=0,
    content_type="youtube", page_number=None, chunk_id=None,
):
    vid = video_id or uuid.uuid4()
    return ScoredChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        video_id=vid,
        user_id=uuid.uuid4(),
        text=f"chunk at {start}",
        start_timestamp=start,
        end_timestamp=end,
        score=score,
        chunk_index=chunk_index,
        content_type=content_type,
        page_number=page_number,
    )


class _DummyResult:
    def __init__(self, payload: dict, score: float):
        self.payload = payload
        self.score = score


def _dummy_qdrant_result(video_id=None, user_id=None, chunk_index=0, score=0.9, **extra):
    vid = video_id or uuid.uuid4()
    uid = user_id or uuid.uuid4()
    payload = {
        "chunk_id": str(chunk_index),
        "video_id": str(vid),
        "user_id": str(uid),
        "text": f"chunk {chunk_index} text",
        "start_timestamp": float(chunk_index * 10),
        "end_timestamp": float((chunk_index + 1) * 10),
        **extra,
    }
    return _DummyResult(payload, score)


# ── ScoredChunk Tests ─────────────────────────────────────────────────────


class TestScoredChunk:
    def test_source_id_alias(self):
        vid = uuid.uuid4()
        chunk = _make_scored_chunk(video_id=vid)
        assert chunk.source_id == vid

    def test_is_document_youtube(self):
        chunk = _make_scored_chunk(content_type="youtube")
        assert chunk.is_document is False

    def test_is_document_pdf(self):
        chunk = _make_scored_chunk(content_type="pdf")
        assert chunk.is_document is True


# ── Create Collection Tests ───────────────────────────────────────────────


class TestCreateCollection:
    def test_creates_new_collection(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        mock_client.get_collections.return_value = SimpleNamespace(collections=[])
        vs.client = mock_client

        vs.create_collection(384)

        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args
        assert call_kwargs.kwargs["collection_name"] == "test_col"

    def test_skips_existing_collection(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        existing = SimpleNamespace(name="test_col")
        mock_client = MagicMock()
        mock_client.get_collections.return_value = SimpleNamespace(collections=[existing])
        vs.client = mock_client

        vs.create_collection(384)

        mock_client.create_collection.assert_not_called()


# ── Index Chunks Tests ────────────────────────────────────────────────────


class TestIndexChunks:
    def test_basic_indexing(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.text = "Hello world"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 10.0
        chunk.duration_seconds = 10.0
        chunk.token_count = 3
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = "Greeting"
        enriched.summary = "A greeting"
        enriched.keywords = ["hello"]

        embedding = np.ones(384)
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        vs.index_chunks([enriched], [embedding], uid, vid)

        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        points = call_args.kwargs["points"]
        assert len(points) == 1
        assert points[0].payload["text"] == "Hello world"
        assert points[0].payload["title"] == "Greeting"

    def test_mismatched_chunks_embeddings_raises(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")

        with pytest.raises(ValueError, match="must match"):
            vs.index_chunks(
                [MagicMock(), MagicMock()],  # 2 chunks
                [np.ones(384)],  # 1 embedding
                uuid.uuid4(),
                uuid.uuid4(),
            )

    def test_includes_document_fields(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.text = "Page content"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 0.0
        chunk.duration_seconds = 0.0
        chunk.token_count = 5
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None
        chunk.page_number = 3
        chunk.section_heading = "Introduction"

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = None
        enriched.summary = None
        enriched.keywords = None

        vs.index_chunks([enriched], [np.ones(384)], uuid.uuid4(), uuid.uuid4(), content_type="pdf")

        points = mock_client.upsert.call_args.kwargs["points"]
        assert points[0].payload["content_type"] == "pdf"
        assert points[0].payload["page_number"] == 3
        assert points[0].payload["section_heading"] == "Introduction"


# ── Search Tests ──────────────────────────────────────────────────────────


class TestSearch:
    def test_basic_search(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        vs.client = SimpleNamespace(
            search=lambda **_: [_dummy_qdrant_result(video_id=vid, user_id=uid)]
        )

        results = vs.search(np.zeros(384), user_id=uid, video_ids=[vid])
        assert len(results) == 1
        assert results[0].video_id == vid

    def test_search_with_filters(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        captured = {}

        def mock_search(**kwargs):
            captured.update(kwargs)
            return []

        vs.client = SimpleNamespace(search=mock_search)

        uid = uuid.uuid4()
        vs.search(np.zeros(384), user_id=uid, filters={"chapter_title": "Introduction"})

        qf = captured["query_filter"]
        assert qf is not None
        # Should have user_id + chapter_title in must conditions
        assert len(qf.must) == 2

    def test_search_no_filters(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        captured = {}

        def mock_search(**kwargs):
            captured.update(kwargs)
            return []

        vs.client = SimpleNamespace(search=mock_search)

        vs.search(np.zeros(384))
        assert captured["query_filter"] is None


# ── Proximity Similarity Tests ────────────────────────────────────────────


class TestProximitySimilarity:
    def test_video_same_timestamp(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(start=10.0, end=20.0, content_type="youtube")
        b = _make_scored_chunk(start=10.0, end=20.0, content_type="youtube")

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(1.0)

    def test_video_far_apart(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(start=0.0, content_type="youtube")
        b = _make_scored_chunk(start=300.0, content_type="youtube")

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(0.0)

    def test_video_moderate_distance(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(start=0.0, content_type="youtube")
        b = _make_scored_chunk(start=150.0, content_type="youtube")

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(0.5)

    def test_document_same_page(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(content_type="pdf", page_number=5)
        b = _make_scored_chunk(content_type="pdf", page_number=5)

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(1.0)

    def test_document_far_pages(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(content_type="pdf", page_number=1)
        b = _make_scored_chunk(content_type="pdf", page_number=11)

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(0.0)


# ── MMR Diversity Tests ───────────────────────────────────────────────────


class TestMMRDiversity:
    def test_selects_diverse_chunks(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.95, start=0.0),
            _make_scored_chunk(video_id=vid1, score=0.90, start=5.0),
            _make_scored_chunk(video_id=vid1, score=0.85, start=10.0),
            _make_scored_chunk(video_id=vid2, score=0.80, start=0.0),
            _make_scored_chunk(video_id=vid2, score=0.75, start=5.0),
        ]

        result = vs._apply_mmr(
            query_embedding=np.zeros(384),
            candidates=candidates,
            top_k=3,
            diversity=0.5,
        )

        assert len(result) == 3
        # With diversity=0.5, should select from both videos
        result_video_ids = {c.video_id for c in result}
        assert len(result_video_ids) == 2

    def test_no_diversity_selects_top_scores(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        candidates = [
            _make_scored_chunk(video_id=vid, score=0.9, start=0.0),
            _make_scored_chunk(video_id=vid, score=0.8, start=100.0),
            _make_scored_chunk(video_id=vid, score=0.7, start=200.0),
        ]

        result = vs._apply_mmr(
            query_embedding=np.zeros(384),
            candidates=candidates,
            top_k=2,
            diversity=0.0,  # No diversity penalty
        )

        assert len(result) == 2
        # Should pick top 2 by score
        assert result[0].score == 0.9

    def test_empty_candidates(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        result = vs._apply_mmr(np.zeros(384), [], top_k=5, diversity=0.5)
        assert result == []


# ── Search With Diversity Tests ───────────────────────────────────────────


class TestSearchWithDiversity:
    def test_delegates_to_mmr(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        uid = uuid.uuid4()

        search_results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=i, score=0.9 - i * 0.05)
            for i in range(5)
        ] + [
            _dummy_qdrant_result(video_id=vid2, user_id=uid, chunk_index=i, score=0.8 - i * 0.05)
            for i in range(5)
        ]

        vs.client = SimpleNamespace(search=lambda **_: search_results)

        results = vs.search_with_diversity(
            np.zeros(384), user_id=uid, video_ids=[vid1, vid2],
            top_k=4, diversity=0.5,
        )

        assert len(results) == 4

    def test_returns_all_when_fewer_than_top_k(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vs.client = SimpleNamespace(
            search=lambda **_: [_dummy_qdrant_result(score=0.9)]
        )

        results = vs.search_with_diversity(np.zeros(384), top_k=5)
        assert len(results) == 1


# ── Search With Video Guarantee Tests ─────────────────────────────────────


class TestSearchWithVideoGuarantee:
    def test_guarantees_all_videos_represented(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        vid3 = uuid.uuid4()
        uid = uuid.uuid4()

        results = (
            [_dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=i, score=0.95 - i * 0.01) for i in range(5)]
            + [_dummy_qdrant_result(video_id=vid2, user_id=uid, chunk_index=i, score=0.7 - i * 0.01) for i in range(3)]
            + [_dummy_qdrant_result(video_id=vid3, user_id=uid, chunk_index=i, score=0.5) for i in range(2)]
        )
        vs.client = SimpleNamespace(search=lambda **_: results)

        output = vs.search_with_video_guarantee(
            np.zeros(384),
            video_ids=[vid1, vid2, vid3],
            user_id=uid,
            top_k=5,
        )

        video_ids_in_results = {c.video_id for c in output}
        assert vid1 in video_ids_in_results
        assert vid2 in video_ids_in_results
        assert vid3 in video_ids_in_results
        assert len(output) == 5

    def test_empty_search_returns_empty(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vs.client = SimpleNamespace(search=lambda **_: [])

        result = vs.search_with_video_guarantee(
            np.zeros(384), video_ids=[uuid.uuid4()], user_id=uuid.uuid4(),
        )
        assert result == []


# ── Delete Tests ──────────────────────────────────────────────────────────


class TestDeleteByVideoId:
    def test_deletes_video_chunks(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        mock_client = MagicMock()
        vs.client = mock_client

        vid = uuid.uuid4()
        vs.delete_by_video_id(vid)

        mock_client.delete.assert_called_once()


# ── Get Stats Tests ───────────────────────────────────────────────────────


class TestGetStats:
    def test_returns_stats(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        mock_client = MagicMock()
        mock_client.get_collection.return_value = SimpleNamespace(
            points_count=100,
            vectors_count=100,
            indexed_vectors_count=95,
        )
        vs.client = mock_client

        stats = vs.get_stats()
        assert stats["total_points"] == 100
        assert stats["collection_name"] == "test"


# ── Fetch Video Chunk Vectors Tests ───────────────────────────────────────


class TestFetchVideoChunkVectors:
    def test_empty_video_ids_returns_empty(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[])
        assert result == {}

    def test_fetches_and_maps_vectors(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector=[0.1, 0.2, 0.3],
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uid, video_ids=[vid])

        assert (vid, 0) in result
        np.testing.assert_array_almost_equal(result[(vid, 0)], [0.1, 0.2, 0.3])

    def test_handles_named_vectors_dict(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "1"},
            vector={"default": [0.4, 0.5, 0.6]},
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        assert (vid, 1) in result

    def test_pagination(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        rec1 = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector=[0.1],
        )
        rec2 = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "1"},
            vector=[0.2],
        )

        mock_client = MagicMock()
        # First call returns records + offset, second returns empty
        mock_client.scroll.side_effect = [
            ([rec1], "next_offset"),
            ([rec2], None),
        ]
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        assert len(result) == 2
        assert mock_client.scroll.call_count == 2


# ── VectorStoreService Tests ─────────────────────────────────────────────


class TestVectorStoreService:
    def test_initialize_creates_collection(self):
        mock_store = MagicMock()
        service = VectorStoreService(vector_store=mock_store)
        service.initialize(384)

        mock_store.create_collection.assert_called_once_with(384)

    def test_delete_video(self):
        mock_store = MagicMock()
        service = VectorStoreService(vector_store=mock_store)
        vid = uuid.uuid4()
        service.delete_video(vid)

        mock_store.delete_by_video_id.assert_called_once_with(vid)

    def test_get_stats(self):
        mock_store = MagicMock()
        mock_store.get_stats.return_value = {"total_points": 50}
        service = VectorStoreService(vector_store=mock_store)

        stats = service.get_stats()
        assert stats["total_points"] == 50
