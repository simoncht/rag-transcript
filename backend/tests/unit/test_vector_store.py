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
    user_id=None, title=None, summary=None, keywords=None,
    chapter_title=None, speakers=None, section_heading=None,
):
    vid = video_id or uuid.uuid4()
    return ScoredChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        video_id=vid,
        user_id=user_id or uuid.uuid4(),
        text=f"chunk at {start}",
        start_timestamp=start,
        end_timestamp=end,
        score=score,
        chunk_index=chunk_index,
        content_type=content_type,
        page_number=page_number,
        title=title,
        summary=summary,
        keywords=keywords,
        chapter_title=chapter_title,
        speakers=speakers,
        section_heading=section_heading,
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


def _make_enriched_chunk(
    chunk_index=0,
    text="Hello world",
    start_ts=0.0,
    end_ts=10.0,
    token_count=3,
    title="Greeting",
    summary="A greeting",
    keywords=None,
    speakers=None,
    chapter_title=None,
    chapter_index=None,
    page_number=None,
    section_heading=None,
):
    """Create a mock enriched chunk for indexing tests."""
    chunk = MagicMock()
    chunk.chunk_index = chunk_index
    chunk.text = text
    chunk.start_timestamp = start_ts
    chunk.end_timestamp = end_ts
    chunk.duration_seconds = end_ts - start_ts
    chunk.token_count = token_count
    chunk.speakers = speakers
    chunk.chapter_title = chapter_title
    chunk.chapter_index = chapter_index

    # Use spec-like behavior for getattr calls on optional fields
    if page_number is not None:
        chunk.page_number = page_number
    else:
        # Make getattr(chunk, "page_number", None) return None
        del chunk.page_number
        chunk.configure_mock(**{})
        type(chunk).page_number = PropertyMock(side_effect=AttributeError)

    if section_heading is not None:
        chunk.section_heading = section_heading
    else:
        type(chunk).section_heading = PropertyMock(side_effect=AttributeError)

    enriched = MagicMock()
    enriched.chunk = chunk
    enriched.title = title
    enriched.summary = summary
    enriched.keywords = keywords or (["hello"] if title else None)
    return enriched


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

    def test_is_document_docx(self):
        chunk = _make_scored_chunk(content_type="docx")
        assert chunk.is_document is True

    def test_default_optional_fields(self):
        """Verify default None for optional enrichment fields."""
        chunk = ScoredChunk(
            chunk_id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            text="test",
            start_timestamp=0.0,
            end_timestamp=10.0,
            score=0.5,
        )
        assert chunk.title is None
        assert chunk.summary is None
        assert chunk.keywords is None
        assert chunk.chapter_title is None
        assert chunk.speakers is None
        assert chunk.page_number is None
        assert chunk.section_heading is None
        assert chunk.chunk_index is None
        assert chunk.content_type == "youtube"

    def test_enrichment_fields_populated(self):
        """Verify enrichment fields are stored correctly."""
        chunk = _make_scored_chunk(
            title="My Title",
            summary="My Summary",
            keywords=["kw1", "kw2"],
            chapter_title="Chapter 1",
            speakers=["Alice", "Bob"],
            section_heading="Intro",
        )
        assert chunk.title == "My Title"
        assert chunk.summary == "My Summary"
        assert chunk.keywords == ["kw1", "kw2"]
        assert chunk.chapter_title == "Chapter 1"
        assert chunk.speakers == ["Alice", "Bob"]
        assert chunk.section_heading == "Intro"


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

    def test_uses_cosine_distance(self):
        """Verify the collection is created with cosine distance."""
        from qdrant_client.models import Distance

        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        mock_client.get_collections.return_value = SimpleNamespace(collections=[])
        vs.client = mock_client

        vs.create_collection(768)

        call_kwargs = mock_client.create_collection.call_args.kwargs
        vectors_config = call_kwargs["vectors_config"]
        assert vectors_config.size == 768
        assert vectors_config.distance == Distance.COSINE


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

    def test_includes_speakers_and_chapter(self):
        """Verify speaker and chapter metadata is included in payload."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.text = "Speaker content"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 30.0
        chunk.duration_seconds = 30.0
        chunk.token_count = 10
        chunk.speakers = ["Alice", "Bob"]
        chunk.chapter_title = "Chapter 1"
        chunk.chapter_index = 0

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = "Discussion"
        enriched.summary = "A discussion"
        enriched.keywords = ["talk"]

        vs.index_chunks([enriched], [np.ones(384)], uuid.uuid4(), uuid.uuid4())

        points = mock_client.upsert.call_args.kwargs["points"]
        payload = points[0].payload
        assert payload["speakers"] == ["Alice", "Bob"]
        assert payload["chapter_title"] == "Chapter 1"
        assert payload["chapter_index"] == 0

    def test_excludes_none_enrichment_fields(self):
        """When enrichment title/summary/keywords are None, they should not be in payload."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.text = "Raw text"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 5.0
        chunk.duration_seconds = 5.0
        chunk.token_count = 2
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = None
        enriched.summary = None
        enriched.keywords = None

        vs.index_chunks([enriched], [np.ones(384)], uuid.uuid4(), uuid.uuid4())

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert "title" not in payload
        assert "summary" not in payload
        assert "keywords" not in payload

    def test_batch_splitting_over_500(self):
        """Chunks over 500 should be split into multiple upsert batches."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        num_chunks = 750
        enriched_chunks = []
        embeddings = []
        for i in range(num_chunks):
            chunk = MagicMock()
            chunk.chunk_index = i
            chunk.text = f"Chunk {i}"
            chunk.start_timestamp = float(i * 10)
            chunk.end_timestamp = float((i + 1) * 10)
            chunk.duration_seconds = 10.0
            chunk.token_count = 5
            chunk.speakers = None
            chunk.chapter_title = None
            chunk.chapter_index = None

            enriched = MagicMock()
            enriched.chunk = chunk
            enriched.title = None
            enriched.summary = None
            enriched.keywords = None

            enriched_chunks.append(enriched)
            embeddings.append(np.ones(384))

        vs.index_chunks(enriched_chunks, embeddings, uuid.uuid4(), uuid.uuid4())

        # 750 chunks / 500 batch = 2 upsert calls
        assert mock_client.upsert.call_count == 2
        # First batch: 500 points
        first_batch = mock_client.upsert.call_args_list[0].kwargs["points"]
        assert len(first_batch) == 500
        # Second batch: 250 points
        second_batch = mock_client.upsert.call_args_list[1].kwargs["points"]
        assert len(second_batch) == 250

    def test_exactly_500_single_batch(self):
        """Exactly 500 chunks should produce one upsert call."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        num_chunks = 500
        enriched_chunks = []
        embeddings = []
        for i in range(num_chunks):
            chunk = MagicMock()
            chunk.chunk_index = i
            chunk.text = f"Chunk {i}"
            chunk.start_timestamp = float(i)
            chunk.end_timestamp = float(i + 1)
            chunk.duration_seconds = 1.0
            chunk.token_count = 2
            chunk.speakers = None
            chunk.chapter_title = None
            chunk.chapter_index = None

            enriched = MagicMock()
            enriched.chunk = chunk
            enriched.title = None
            enriched.summary = None
            enriched.keywords = None

            enriched_chunks.append(enriched)
            embeddings.append(np.ones(384))

        vs.index_chunks(enriched_chunks, embeddings, uuid.uuid4(), uuid.uuid4())

        assert mock_client.upsert.call_count == 1

    def test_point_id_is_uuid5_deterministic(self):
        """Point IDs should be deterministic uuid5(video_id, chunk_index)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        vid = uuid.uuid4()
        chunk = MagicMock()
        chunk.chunk_index = 7
        chunk.text = "Test"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 10.0
        chunk.duration_seconds = 10.0
        chunk.token_count = 1
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = None
        enriched.summary = None
        enriched.keywords = None

        vs.index_chunks([enriched], [np.ones(384)], uuid.uuid4(), vid)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        expected_id = str(uuid.uuid5(vid, "7"))
        assert point.id == expected_id

    def test_default_content_type_is_youtube(self):
        """Without specifying content_type, payload should default to 'youtube'."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test_col")
        mock_client = MagicMock()
        vs.client = mock_client

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.text = "Video content"
        chunk.start_timestamp = 0.0
        chunk.end_timestamp = 10.0
        chunk.duration_seconds = 10.0
        chunk.token_count = 2
        chunk.speakers = None
        chunk.chapter_title = None
        chunk.chapter_index = None

        enriched = MagicMock()
        enriched.chunk = chunk
        enriched.title = None
        enriched.summary = None
        enriched.keywords = None

        vs.index_chunks([enriched], [np.ones(384)], uuid.uuid4(), uuid.uuid4())

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert payload["content_type"] == "youtube"


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

    def test_search_video_ids_create_should_conditions(self):
        """Video IDs should create 'should' (OR) filter conditions."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        captured = {}

        def mock_search(**kwargs):
            captured.update(kwargs)
            return []

        vs.client = SimpleNamespace(search=mock_search)

        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        vs.search(np.zeros(384), video_ids=[vid1, vid2])

        qf = captured["query_filter"]
        assert qf is not None
        assert qf.should is not None
        assert len(qf.should) == 2

    def test_search_parses_chunk_db_id(self):
        """When chunk_db_id is present in payload, it should be used as chunk_id."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()
        db_id = uuid.uuid4()

        result = _dummy_qdrant_result(
            video_id=vid, user_id=uid, chunk_index=0,
            chunk_db_id=str(db_id),
        )
        vs.client = SimpleNamespace(search=lambda **_: [result])

        results = vs.search(np.zeros(384))
        assert results[0].chunk_id == db_id

    def test_search_fallback_chunk_id_when_no_db_id(self):
        """Without chunk_db_id, chunk_id should be uuid5(video_id, chunk_index)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        result = _dummy_qdrant_result(video_id=vid, user_id=uid, chunk_index=3)
        vs.client = SimpleNamespace(search=lambda **_: [result])

        results = vs.search(np.zeros(384))
        expected_id = uuid.uuid5(vid, "3")
        assert results[0].chunk_id == expected_id

    def test_search_fallback_to_video_uuid_when_no_chunk_index(self):
        """Without chunk_index, chunk_id should fall back to video_id."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        payload = {
            "video_id": str(vid),
            "user_id": str(uid),
            "text": "no chunk index",
            "start_timestamp": 0.0,
            "end_timestamp": 10.0,
        }
        # Remove chunk_id key entirely
        result = _DummyResult(payload, 0.9)
        vs.client = SimpleNamespace(search=lambda **_: [result])

        results = vs.search(np.zeros(384))
        assert results[0].chunk_id == vid
        assert results[0].chunk_index is None

    def test_search_parses_enrichment_metadata(self):
        """Enrichment metadata (title, summary, keywords, speakers, chapter) should be parsed."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        result = _dummy_qdrant_result(
            video_id=vid, user_id=uid, chunk_index=0,
            content_type="pdf",
            page_number=5,
            section_heading="Methods",
            title="Research Methods",
            summary="Describes research methodology",
            keywords=["research", "methods"],
            chapter_title="Methodology",
            speakers=["Dr. Smith"],
        )
        vs.client = SimpleNamespace(search=lambda **_: [result])

        results = vs.search(np.zeros(384))
        chunk = results[0]
        assert chunk.content_type == "pdf"
        assert chunk.page_number == 5
        assert chunk.section_heading == "Methods"
        assert chunk.title == "Research Methods"
        assert chunk.summary == "Describes research methodology"
        assert chunk.keywords == ["research", "methods"]
        assert chunk.chapter_title == "Methodology"
        assert chunk.speakers == ["Dr. Smith"]

    def test_search_defaults_content_type_to_youtube(self):
        """When content_type is missing from payload, default to 'youtube'."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        payload = {
            "chunk_id": "0",
            "video_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "text": "legacy chunk",
            "start_timestamp": 0.0,
            "end_timestamp": 10.0,
            # no content_type key
        }
        vs.client = SimpleNamespace(search=lambda **_: [_DummyResult(payload, 0.8)])

        results = vs.search(np.zeros(384))
        assert results[0].content_type == "youtube"

    def test_search_returns_correct_score(self):
        """Search results should carry the Qdrant score."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        result = _dummy_qdrant_result(score=0.73)
        vs.client = SimpleNamespace(search=lambda **_: [result])

        results = vs.search(np.zeros(384))
        assert results[0].score == pytest.approx(0.73)

    def test_search_empty_results(self):
        """Search with no matches returns empty list."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vs.client = SimpleNamespace(search=lambda **_: [])

        results = vs.search(np.zeros(384), user_id=uuid.uuid4())
        assert results == []

    def test_search_multiple_results_ordering(self):
        """Multiple results should maintain Qdrant ordering."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        raw_results = [
            _dummy_qdrant_result(video_id=vid, user_id=uid, chunk_index=0, score=0.95),
            _dummy_qdrant_result(video_id=vid, user_id=uid, chunk_index=1, score=0.80),
            _dummy_qdrant_result(video_id=vid, user_id=uid, chunk_index=2, score=0.65),
        ]
        vs.client = SimpleNamespace(search=lambda **_: raw_results)

        results = vs.search(np.zeros(384))
        assert len(results) == 3
        assert results[0].score == pytest.approx(0.95)
        assert results[1].score == pytest.approx(0.80)
        assert results[2].score == pytest.approx(0.65)

    def test_search_top_k_passed_to_client(self):
        """The top_k parameter should be forwarded as limit to Qdrant client."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        captured = {}

        def mock_search(**kwargs):
            captured.update(kwargs)
            return []

        vs.client = SimpleNamespace(search=mock_search)

        vs.search(np.zeros(384), top_k=25)
        assert captured["limit"] == 25


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

    def test_document_none_pages_treated_as_zero(self):
        """When page_number is None, it should be treated as page 0."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(content_type="pdf", page_number=None)
        b = _make_scored_chunk(content_type="pdf", page_number=None)

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(1.0)

    def test_document_moderate_page_distance(self):
        """5-page difference should give 0.5 similarity."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(content_type="pdf", page_number=1)
        b = _make_scored_chunk(content_type="pdf", page_number=6)

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == pytest.approx(0.5)

    def test_video_beyond_max_distance_clamped(self):
        """Timestamps >300s apart should clamp to 0.0 (not go negative)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(start=0.0, content_type="youtube")
        b = _make_scored_chunk(start=600.0, content_type="youtube")

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == 0.0

    def test_document_beyond_max_pages_clamped(self):
        """Pages >10 apart should clamp to 0.0 (not go negative)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        a = _make_scored_chunk(content_type="pdf", page_number=1)
        b = _make_scored_chunk(content_type="pdf", page_number=50)

        sim = vs._compute_proximity_similarity(a, b)
        assert sim == 0.0


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

    def test_max_diversity_strongly_penalizes_same_video(self):
        """With diversity=1.0, same-video chunks should be heavily penalized."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.99, start=0.0),
            _make_scored_chunk(video_id=vid1, score=0.98, start=5.0),
            _make_scored_chunk(video_id=vid2, score=0.50, start=0.0),
        ]

        result = vs._apply_mmr(
            query_embedding=np.zeros(384),
            candidates=candidates,
            top_k=2,
            diversity=1.0,
        )

        # With max diversity, the second chunk should be from vid2 despite lower score
        assert result[0].video_id == vid1
        assert result[1].video_id == vid2

    def test_single_candidate(self):
        """MMR with a single candidate should return it."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        chunk = _make_scored_chunk(score=0.5)

        result = vs._apply_mmr(np.zeros(384), [chunk], top_k=5, diversity=0.5)
        assert len(result) == 1
        assert result[0].score == 0.5

    def test_top_k_greater_than_candidates(self):
        """When top_k > len(candidates), return all candidates."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        candidates = [
            _make_scored_chunk(video_id=vid, score=0.9, start=0.0),
            _make_scored_chunk(video_id=vid, score=0.8, start=100.0),
        ]

        result = vs._apply_mmr(np.zeros(384), candidates, top_k=10, diversity=0.5)
        assert len(result) == 2

    def test_mmr_first_selected_is_highest_score(self):
        """The first chunk selected by MMR should always be the highest-scoring one."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.70, start=0.0),
            _make_scored_chunk(video_id=vid2, score=0.95, start=0.0),
            _make_scored_chunk(video_id=vid1, score=0.60, start=100.0),
        ]

        result = vs._apply_mmr(np.zeros(384), candidates, top_k=2, diversity=0.5)
        # First selected should be the highest score regardless of diversity
        assert result[0].score == 0.95

    def test_mmr_three_videos_selects_all(self):
        """With 3 videos and top_k=3, moderate diversity should select one from each."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        vid3 = uuid.uuid4()

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.95, start=0.0),
            _make_scored_chunk(video_id=vid1, score=0.94, start=5.0),
            _make_scored_chunk(video_id=vid2, score=0.80, start=0.0),
            _make_scored_chunk(video_id=vid2, score=0.79, start=5.0),
            _make_scored_chunk(video_id=vid3, score=0.70, start=0.0),
        ]

        result = vs._apply_mmr(np.zeros(384), candidates, top_k=3, diversity=0.7)
        result_vids = {c.video_id for c in result}
        assert len(result_vids) == 3


# ── MMR With Preselected Tests ───────────────────────────────────────────


class TestMMRWithPreselected:
    def test_empty_candidates_returns_empty(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        result = vs._apply_mmr_with_preselected(
            candidates=[],
            top_k=3,
            diversity=0.5,
            preselected=[_make_scored_chunk()],
        )
        assert result == []

    def test_preselected_influences_diversity(self):
        """Candidates from same video as preselected should be penalized."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        preselected = [_make_scored_chunk(video_id=vid1, score=0.95, start=0.0)]

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.90, start=5.0),
            _make_scored_chunk(video_id=vid2, score=0.60, start=0.0),
        ]

        result = vs._apply_mmr_with_preselected(
            candidates=candidates,
            top_k=1,
            diversity=0.7,
            preselected=preselected,
        )

        assert len(result) == 1
        # With high diversity and vid1 already preselected, vid2 should be preferred
        assert result[0].video_id == vid2

    def test_preselected_with_no_diversity(self):
        """With diversity=0, preselected should not affect selection (top score wins)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()

        preselected = [_make_scored_chunk(video_id=vid1, score=0.95, start=0.0)]

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.90, start=5.0),
            _make_scored_chunk(video_id=vid2, score=0.60, start=0.0),
        ]

        result = vs._apply_mmr_with_preselected(
            candidates=candidates,
            top_k=1,
            diversity=0.0,
            preselected=preselected,
        )

        assert len(result) == 1
        assert result[0].score == 0.90  # Highest score wins

    def test_selects_multiple_with_preselected(self):
        """Should fill slots considering both preselected and newly selected chunks."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        vid3 = uuid.uuid4()

        preselected = [_make_scored_chunk(video_id=vid1, score=0.95, start=0.0)]

        candidates = [
            _make_scored_chunk(video_id=vid1, score=0.88, start=10.0),
            _make_scored_chunk(video_id=vid2, score=0.85, start=0.0),
            _make_scored_chunk(video_id=vid3, score=0.70, start=0.0),
            _make_scored_chunk(video_id=vid2, score=0.82, start=10.0),
        ]

        result = vs._apply_mmr_with_preselected(
            candidates=candidates,
            top_k=3,
            diversity=0.5,
            preselected=preselected,
        )

        assert len(result) == 3
        # Should have good diversity across videos
        result_vids = {c.video_id for c in result}
        assert len(result_vids) >= 2


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

    def test_empty_candidates(self):
        """Empty search results should return empty list."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vs.client = SimpleNamespace(search=lambda **_: [])

        results = vs.search_with_diversity(np.zeros(384), top_k=5)
        assert results == []

    def test_exact_top_k_candidates_returns_all(self):
        """When candidates == top_k, return all without MMR (early return path)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        uid = uuid.uuid4()

        search_results = [
            _dummy_qdrant_result(user_id=uid, chunk_index=i, score=0.9 - i * 0.1)
            for i in range(3)
        ]
        vs.client = SimpleNamespace(search=lambda **_: search_results)

        results = vs.search_with_diversity(np.zeros(384), top_k=3)
        assert len(results) == 3

    def test_prefetch_limit_forwarded(self):
        """The prefetch_limit should be passed as top_k to the inner search call."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        captured = {}

        def mock_search(**kwargs):
            captured.update(kwargs)
            return []

        vs.client = SimpleNamespace(search=mock_search)

        vs.search_with_diversity(np.zeros(384), top_k=5, prefetch_limit=200)
        assert captured["limit"] == 200


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

    def test_top_k_equals_num_videos_no_mmr_fill(self):
        """When top_k == num_videos, Phase 1 fills all slots (no Phase 2)."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        uid = uuid.uuid4()

        results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=0, score=0.9),
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=1, score=0.8),
            _dummy_qdrant_result(video_id=vid2, user_id=uid, chunk_index=0, score=0.7),
        ]
        vs.client = SimpleNamespace(search=lambda **_: results)

        output = vs.search_with_video_guarantee(
            np.zeros(384), video_ids=[vid1, vid2], user_id=uid, top_k=2,
        )

        assert len(output) == 2
        vids = {c.video_id for c in output}
        assert vid1 in vids
        assert vid2 in vids

    def test_top_k_less_than_num_videos(self):
        """When top_k < num_videos, only first top_k videos get represented."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid2 = uuid.uuid4()
        vid3 = uuid.uuid4()
        uid = uuid.uuid4()

        results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=0, score=0.9),
            _dummy_qdrant_result(video_id=vid2, user_id=uid, chunk_index=0, score=0.8),
            _dummy_qdrant_result(video_id=vid3, user_id=uid, chunk_index=0, score=0.7),
        ]
        vs.client = SimpleNamespace(search=lambda **_: results)

        output = vs.search_with_video_guarantee(
            np.zeros(384), video_ids=[vid1, vid2, vid3], user_id=uid, top_k=2,
        )

        # Only 2 videos fit in top_k=2
        assert len(output) == 2

    def test_picks_best_chunk_per_video(self):
        """Phase 1 should select the highest-scoring chunk from each video."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        uid = uuid.uuid4()

        results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=0, score=0.5),
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=1, score=0.9),
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=2, score=0.7),
        ]
        vs.client = SimpleNamespace(search=lambda **_: results)

        output = vs.search_with_video_guarantee(
            np.zeros(384), video_ids=[vid1], user_id=uid, top_k=1,
        )

        assert len(output) == 1
        assert output[0].score == pytest.approx(0.9)

    def test_video_not_in_candidates_is_skipped(self):
        """If a requested video_id has no candidates, it is simply skipped."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        vid_missing = uuid.uuid4()
        uid = uuid.uuid4()

        results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=0, score=0.9),
        ]
        vs.client = SimpleNamespace(search=lambda **_: results)

        output = vs.search_with_video_guarantee(
            np.zeros(384),
            video_ids=[vid1, vid_missing],
            user_id=uid,
            top_k=5,
        )

        # vid_missing has no candidates, so only vid1 appears
        vids = {c.video_id for c in output}
        assert vid1 in vids
        assert vid_missing not in vids


# ── Delete Tests ──────────────────────────────────────────────────────────


class TestDeleteByVideoId:
    def test_deletes_video_chunks(self):
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        mock_client = MagicMock()
        vs.client = mock_client

        vid = uuid.uuid4()
        vs.delete_by_video_id(vid)

        mock_client.delete.assert_called_once()

    def test_delete_passes_correct_filter(self):
        """Delete should filter by video_id in the must conditions."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        mock_client = MagicMock()
        vs.client = mock_client

        vid = uuid.uuid4()
        vs.delete_by_video_id(vid)

        call_kwargs = mock_client.delete.call_args.kwargs
        selector = call_kwargs["points_selector"]
        assert len(selector.must) == 1
        assert selector.must[0].key == "video_id"
        assert selector.must[0].match.value == str(vid)

    def test_delete_uses_correct_collection(self):
        """Delete should use the store's collection name."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="my_collection")
        mock_client = MagicMock()
        vs.client = mock_client

        vs.delete_by_video_id(uuid.uuid4())

        call_kwargs = mock_client.delete.call_args.kwargs
        assert call_kwargs["collection_name"] == "my_collection"


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

    def test_returns_all_stat_fields(self):
        """Stats should include total_points, vectors_count, indexed_vectors_count, collection_name."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="prod")
        mock_client = MagicMock()
        mock_client.get_collection.return_value = SimpleNamespace(
            points_count=500,
            vectors_count=500,
            indexed_vectors_count=490,
        )
        vs.client = mock_client

        stats = vs.get_stats()
        assert stats["total_points"] == 500
        assert stats["vectors_count"] == 500
        assert stats["indexed_vectors_count"] == 490
        assert stats["collection_name"] == "prod"


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

    def test_skips_records_with_missing_video_id(self):
        """Records without video_id in payload should be skipped."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        record = SimpleNamespace(
            payload={"chunk_id": "0"},  # no video_id
            vector=[0.1, 0.2],
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[uuid.uuid4()])
        assert result == {}

    def test_skips_records_with_missing_chunk_id(self):
        """Records without chunk_id in payload should be skipped."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid)},  # no chunk_id
            vector=[0.1, 0.2],
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        assert result == {}

    def test_skips_records_with_none_vector(self):
        """Records with None vector should be skipped."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector=None,
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        assert result == {}

    def test_skips_empty_named_vectors_dict(self):
        """Records with empty named vectors dict should be skipped."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector={},
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        assert result == {}

    def test_skips_records_with_none_payload(self):
        """Records with None payload should be handled gracefully."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")

        record = SimpleNamespace(
            payload=None,
            vector=[0.1],
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[uuid.uuid4()])
        assert result == {}

    def test_returns_float32_arrays(self):
        """Returned vectors should be float32 numpy arrays."""
        vs = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector=[0.1, 0.2, 0.3],
        )

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        vs.client = mock_client

        result = vs.fetch_video_chunk_vectors(user_id=uuid.uuid4(), video_ids=[vid])
        vec = result[(vid, 0)]
        assert vec.dtype == np.float32


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

    def test_index_video_chunks_delegates(self):
        """index_video_chunks should delegate to the underlying store."""
        mock_store = MagicMock()
        service = VectorStoreService(vector_store=mock_store)

        chunks = [MagicMock()]
        embeddings = [np.ones(384)]
        uid = uuid.uuid4()
        vid = uuid.uuid4()

        service.index_video_chunks(chunks, embeddings, uid, vid, content_type="pdf")

        mock_store.index_chunks.assert_called_once_with(
            chunks, embeddings, uid, vid, content_type="pdf"
        )

    def test_search_chunks_delegates(self):
        """search_chunks should delegate to the underlying store."""
        mock_store = MagicMock()
        mock_store.search.return_value = [_make_scored_chunk()]
        service = VectorStoreService(vector_store=mock_store)

        uid = uuid.uuid4()
        vid = uuid.uuid4()
        query = np.zeros(384)

        results = service.search_chunks(
            query, user_id=uid, video_ids=[vid], top_k=5
        )

        mock_store.search.assert_called_once()
        assert len(results) == 1

    def test_search_with_diversity_delegates_to_qdrant(self):
        """search_with_diversity should call QdrantVectorStore.search_with_diversity."""
        qdrant_store = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        uid = uuid.uuid4()

        search_results = [
            _dummy_qdrant_result(user_id=uid, chunk_index=i, score=0.9 - i * 0.05)
            for i in range(5)
        ]
        qdrant_store.client = SimpleNamespace(search=lambda **_: search_results)

        service = VectorStoreService(vector_store=qdrant_store)

        results = service.search_with_diversity(
            np.zeros(384), user_id=uid, top_k=3, diversity=0.5
        )

        assert len(results) == 3

    def test_search_with_diversity_fallback_for_non_qdrant(self):
        """For non-Qdrant stores, search_with_diversity should fall back to regular search."""
        mock_store = MagicMock(spec=[])  # No isinstance check passes
        mock_store.search = MagicMock(return_value=[_make_scored_chunk()])
        service = VectorStoreService(vector_store=mock_store)

        results = service.search_with_diversity(np.zeros(384), top_k=3)

        mock_store.search.assert_called_once()
        assert len(results) == 1

    def test_search_with_video_guarantee_delegates_to_qdrant(self):
        """search_with_video_guarantee should call QdrantVectorStore method."""
        qdrant_store = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid1 = uuid.uuid4()
        uid = uuid.uuid4()

        search_results = [
            _dummy_qdrant_result(video_id=vid1, user_id=uid, chunk_index=0, score=0.9),
        ]
        qdrant_store.client = SimpleNamespace(search=lambda **_: search_results)

        service = VectorStoreService(vector_store=qdrant_store)

        results = service.search_with_video_guarantee(
            np.zeros(384), video_ids=[vid1], user_id=uid, top_k=3,
        )

        assert len(results) == 1

    def test_search_with_video_guarantee_fallback_for_non_qdrant(self):
        """For non-Qdrant stores, should fall back to regular search."""
        mock_store = MagicMock(spec=[])
        mock_store.search = MagicMock(return_value=[_make_scored_chunk()])
        service = VectorStoreService(vector_store=mock_store)

        results = service.search_with_video_guarantee(
            np.zeros(384), video_ids=[uuid.uuid4()], user_id=uuid.uuid4(),
        )

        mock_store.search.assert_called_once()
        assert len(results) == 1

    def test_fetch_video_chunk_vectors_delegates_to_qdrant(self):
        """fetch_video_chunk_vectors should delegate to QdrantVectorStore."""
        qdrant_store = QdrantVectorStore(host="localhost", port=6333, collection_name="test")
        vid = uuid.uuid4()
        uid = uuid.uuid4()

        record = SimpleNamespace(
            payload={"video_id": str(vid), "chunk_id": "0"},
            vector=[0.1, 0.2],
        )
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        qdrant_store.client = mock_client

        service = VectorStoreService(vector_store=qdrant_store)

        result = service.fetch_video_chunk_vectors(user_id=uid, video_ids=[vid])
        assert (vid, 0) in result

    def test_fetch_video_chunk_vectors_empty_for_non_qdrant(self):
        """For non-Qdrant stores, should return empty dict."""
        mock_store = MagicMock(spec=[])
        service = VectorStoreService(vector_store=mock_store)

        result = service.fetch_video_chunk_vectors(
            user_id=uuid.uuid4(), video_ids=[uuid.uuid4()]
        )
        assert result == {}

    def test_initialize_with_collection_name(self):
        """initialize() with collection_name should replace the store and create collection."""
        qdrant_store = QdrantVectorStore(host="localhost", port=6333, collection_name="old")
        mock_client = MagicMock()
        mock_client.get_collections.return_value = SimpleNamespace(collections=[])
        qdrant_store.client = mock_client

        service = VectorStoreService(vector_store=qdrant_store)

        # Patch QdrantClient to avoid real connection when QdrantVectorStore is recreated
        with patch('app.services.vector_store.QdrantClient') as MockClient:
            mock_new_client = MagicMock()
            mock_new_client.get_collections.return_value = SimpleNamespace(collections=[])
            MockClient.return_value = mock_new_client

            service.initialize(384, collection_name="new_collection")

        # After initialize with collection_name, the store should have the new name
        assert service.vector_store.collection_name == "new_collection"
        # create_collection should have been called on the new store
        mock_new_client.create_collection.assert_called_once()

    def test_default_qdrant_store_when_none_provided(self):
        """VectorStoreService should default to QdrantVectorStore when none is provided."""
        with patch('app.services.vector_store.QdrantVectorStore') as MockQdrant:
            service = VectorStoreService()
            MockQdrant.assert_called_once()


# ── Init / Constructor Tests ─────────────────────────────────────────────


class TestQdrantVectorStoreInit:
    def test_uses_default_settings(self):
        """When no host/port/collection provided, should use settings defaults."""
        with patch('app.services.vector_store.settings') as mock_settings:
            mock_settings.qdrant_host = "qdrant-host"
            mock_settings.qdrant_port = 6333
            mock_settings.qdrant_collection_name = "transcripts"
            mock_settings.qdrant_api_key = None

            with patch('app.services.vector_store.QdrantClient'):
                vs = QdrantVectorStore()
                assert vs.host == "qdrant-host"
                assert vs.port == 6333
                assert vs.collection_name == "transcripts"

    def test_explicit_params_override_settings(self):
        """Explicit host/port/collection should override settings."""
        with patch('app.services.vector_store.settings') as mock_settings:
            mock_settings.qdrant_api_key = None

            with patch('app.services.vector_store.QdrantClient'):
                vs = QdrantVectorStore(
                    host="custom-host", port=9999, collection_name="custom"
                )
                assert vs.host == "custom-host"
                assert vs.port == 9999
                assert vs.collection_name == "custom"

    def test_api_key_included_when_set(self):
        """When qdrant_api_key is set, it should be passed to QdrantClient."""
        with patch('app.services.vector_store.settings') as mock_settings:
            mock_settings.qdrant_host = "localhost"
            mock_settings.qdrant_port = 6333
            mock_settings.qdrant_collection_name = "test"
            mock_settings.qdrant_api_key = "my-secret-key"

            with patch('app.services.vector_store.QdrantClient') as MockClient:
                vs = QdrantVectorStore()
                MockClient.assert_called_once_with(
                    host="localhost",
                    port=6333,
                    api_key="my-secret-key",
                    prefer_grpc=True,
                    https=False,
                )

    def test_no_api_key_excluded(self):
        """When qdrant_api_key is falsy, api_key should not be passed."""
        with patch('app.services.vector_store.settings') as mock_settings:
            mock_settings.qdrant_host = "localhost"
            mock_settings.qdrant_port = 6333
            mock_settings.qdrant_collection_name = "test"
            mock_settings.qdrant_api_key = ""

            with patch('app.services.vector_store.QdrantClient') as MockClient:
                vs = QdrantVectorStore()
                MockClient.assert_called_once_with(
                    host="localhost",
                    port=6333,
                    prefer_grpc=True,
                    https=False,
                )
