"""Unit tests for HyDE (Hypothetical Document Embeddings) service."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.services.hyde import HyDEService


@pytest.fixture
def disabled_service():
    with patch("app.services.hyde.settings") as mock_settings:
        mock_settings.enable_hyde = False
        return HyDEService()


@pytest.fixture
def enabled_service():
    with patch("app.services.hyde.settings") as mock_settings:
        mock_settings.enable_hyde = True
        svc = HyDEService()
        svc.enabled = True
        return svc


class TestDisabled:
    def test_returns_none_when_disabled(self, disabled_service):
        result = disabled_service.generate_hypothetical_passage("test query")
        assert result is None

    def test_embedding_returns_none_when_disabled(self, disabled_service):
        result = disabled_service.generate_hyde_embedding("test query")
        assert result is None


class TestPassageGeneration:
    def test_generates_passage(self, enabled_service):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            "Neural networks are computational models inspired by biological neurons. "
            "They consist of layers of interconnected nodes that process information. "
            "Deep learning uses multi-layer neural networks for complex pattern recognition."
        )
        mock_llm.complete.return_value = mock_response
        enabled_service.llm_service = mock_llm

        passage = enabled_service.generate_hypothetical_passage("What are neural networks?")
        assert passage is not None
        assert len(passage) > 20

    def test_short_passage_rejected(self, enabled_service):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Too short"
        mock_llm.complete.return_value = mock_response
        enabled_service.llm_service = mock_llm

        passage = enabled_service.generate_hypothetical_passage("test")
        assert passage is None

    def test_llm_failure_returns_none(self, enabled_service):
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = RuntimeError("LLM down")
        enabled_service.llm_service = mock_llm

        passage = enabled_service.generate_hypothetical_passage("test")
        assert passage is None


class TestEmbeddingGeneration:
    def test_generates_embedding(self, enabled_service):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "A detailed passage about machine learning algorithms and their applications in natural language processing."
        mock_llm.complete.return_value = mock_response
        enabled_service.llm_service = mock_llm

        mock_embed = MagicMock()
        mock_embed.embed_text.return_value = np.random.rand(768).astype(np.float32)
        enabled_service.embedding_service = mock_embed

        embedding = enabled_service.generate_hyde_embedding("What is ML?")
        assert embedding is not None
        assert embedding.shape == (768,)

    def test_returns_none_on_passage_failure(self, enabled_service):
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = RuntimeError("fail")
        enabled_service.llm_service = mock_llm

        embedding = enabled_service.generate_hyde_embedding("test")
        assert embedding is None

    def test_handles_tuple_embedding(self, enabled_service):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "A detailed passage about data science and statistical methods in research."
        mock_llm.complete.return_value = mock_response
        enabled_service.llm_service = mock_llm

        mock_embed = MagicMock()
        # Return tuple (from cached embeddings)
        mock_embed.embed_text.return_value = tuple(np.random.rand(768).astype(np.float32))
        enabled_service.embedding_service = mock_embed

        embedding = enabled_service.generate_hyde_embedding("What is data science?")
        assert embedding is not None
