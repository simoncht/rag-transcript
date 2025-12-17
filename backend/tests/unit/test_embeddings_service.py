import sys
from pathlib import Path

# Ensure backend package is importable when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest


def test_embedding_service_exposes_collection_and_key() -> None:
    from app.core.config import settings
    from app.services.embeddings import EmbeddingService, resolve_collection_name

    service = EmbeddingService()

    assert service.get_collection_name() == settings.qdrant_collection_name
    assert isinstance(service.get_model_key(), str)
    assert service.get_model_key()
    assert resolve_collection_name(service) == settings.qdrant_collection_name


def test_resolve_collection_name_falls_back() -> None:
    from app.core.config import settings
    from app.services.embeddings import resolve_collection_name

    class OldService:
        pass

    assert resolve_collection_name(OldService()) == settings.qdrant_collection_name


def test_set_active_embedding_model_returns_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    from app.services import embeddings as embeddings_module

    class DummyProvider:
        def embed_text(self, text: str) -> np.ndarray:  # noqa: ARG002
            return np.zeros(3, dtype=np.float32)

        def embed_batch(self, texts: list[str]) -> list[np.ndarray]:  # noqa: ARG002
            return [np.zeros(3, dtype=np.float32)]

        def get_model_info(self) -> dict:
            return {"provider": "dummy", "model": "dummy", "dimensions": 3}

    monkeypatch.setattr(
        embeddings_module.EmbeddingService,
        "_create_provider",
        lambda self: DummyProvider(),
        raising=True,
    )

    service = embeddings_module.set_active_embedding_model("all-MiniLM-L6-v2")

    assert service.get_model_name()
    assert service.get_collection_name()
