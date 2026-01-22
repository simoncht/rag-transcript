import uuid
from types import SimpleNamespace

import numpy as np
import pytest

from app.services.vector_store import QdrantVectorStore


class _DummyResult:
    def __init__(self, payload: dict, score: float) -> None:
        self.payload = payload
        self.score = score


def test_search_prefers_chunk_db_id(monkeypatch: pytest.MonkeyPatch) -> None:
    vs = QdrantVectorStore(host="localhost", port=6333, collection_name="dummy")

    chunk_id = uuid.uuid4()
    video_id = uuid.uuid4()
    user_id = uuid.uuid4()

    def _search(**_kwargs: object) -> list[_DummyResult]:
        return [
            _DummyResult(
                {
                    "chunk_db_id": str(chunk_id),
                    "chunk_id": "5",
                    "video_id": str(video_id),
                    "user_id": str(user_id),
                    "text": "payload text",
                    "start_timestamp": 1.0,
                    "end_timestamp": 2.0,
                },
                score=0.9,
            )
        ]

    monkeypatch.setattr(vs, "client", SimpleNamespace(search=_search), raising=False)

    results = vs.search(
        np.zeros(3, dtype=np.float32), user_id=user_id, video_ids=[video_id]
    )
    assert len(results) == 1
    first = results[0]
    assert first.chunk_id == chunk_id
    assert first.chunk_index == 5
    assert first.video_id == video_id
    assert first.user_id == user_id


def test_search_derives_chunk_id_from_video_and_index() -> None:
    vs = QdrantVectorStore(host="localhost", port=6333, collection_name="dummy")

    video_id = uuid.uuid4()
    user_id = uuid.uuid4()

    def _search(**_kwargs: object) -> list[_DummyResult]:
        return [
            _DummyResult(
                {
                    "chunk_id": "2",  # Legacy payload without chunk_db_id
                    "video_id": str(video_id),
                    "user_id": str(user_id),
                    "text": "legacy text",
                    "start_timestamp": 3.0,
                    "end_timestamp": 4.0,
                },
                score=0.8,
            )
        ]

    vs.client = SimpleNamespace(search=_search)

    results = vs.search(
        np.zeros(3, dtype=np.float32), user_id=user_id, video_ids=[video_id]
    )
    assert len(results) == 1
    first = results[0]
    expected_fallback_id = uuid.uuid5(video_id, "2")
    assert first.chunk_id == expected_fallback_id
    assert first.chunk_index == 2
