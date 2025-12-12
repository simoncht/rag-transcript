"""
Embedding service for generating vector embeddings from text.

Supports multiple backends:
- Local sentence-transformers models (default, no API key required)
- OpenAI embeddings API
- Azure OpenAI embeddings

Includes batching, normalization, and caching for optimal performance.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import numpy as np
from functools import lru_cache
import hashlib

from app.core.config import settings


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector as numpy array
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict:
        """
        Get information about the embedding model.

        Returns:
            Dictionary with model name, dimensions, etc.
        """
        pass


class SentenceTransformerEmbedding(EmbeddingProvider):
    """
    Local sentence-transformers embedding provider.

    Uses sentence-transformers library for local embedding generation.
    Default model: all-MiniLM-L6-v2 (384 dimensions, fast, good quality).
    """

    def __init__(self, model_name: str = None):
        """
        Initialize sentence transformer model.

        Args:
            model_name: Model name (defaults to settings.embedding_model)
        """
        # SSL bypass is handled globally in app.core.ssl_patch
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name)
        self.dimensions = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        # Normalize to unit vector
        return self._normalize(embedding)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=False
        )
        # Normalize all embeddings
        return [self._normalize(emb) for emb in embeddings]

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "provider": "sentence-transformers",
            "model": self.model_name,
            "dimensions": self.dimensions,
            "max_sequence_length": self.model.max_seq_length,
        }

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        """Normalize embedding to unit length."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm


class BertEmbedding(EmbeddingProvider):
    """
    BERT embedding provider using transformers library directly.

    Uses bert-base-uncased from local cache without sentence-transformers wrapper.
    """

    def __init__(self, model_name: str = None):
        """Initialize BERT model."""
        from transformers import AutoModel, AutoTokenizer
        import torch

        self.model_name = model_name or settings.embedding_model
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
        self.model = AutoModel.from_pretrained(self.model_name, local_files_only=True)
        self.model.eval()  # Set to evaluation mode
        self.dimensions = self.model.config.hidden_size
        self.max_length = 512

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        import torch

        inputs = self.tokenizer(
            text,
            return_tensors='pt',
            padding=True,
            truncation=True,
            max_length=self.max_length
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use [CLS] token embedding
            embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()

        return self._normalize(embedding)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        import torch

        inputs = self.tokenizer(
            texts,
            return_tensors='pt',
            padding=True,
            truncation=True,
            max_length=self.max_length
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use [CLS] token embeddings for all texts
            embeddings = outputs.last_hidden_state[:, 0, :].numpy()

        return [self._normalize(emb) for emb in embeddings]

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "provider": "bert",
            "model": self.model_name,
            "dimensions": self.dimensions,
            "max_sequence_length": self.max_length,
        }

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        """Normalize embedding to unit length."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm


class OpenAIEmbedding(EmbeddingProvider):
    """
    OpenAI embeddings API provider.

    Uses OpenAI's text-embedding models via their API.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI embeddings.

        Args:
            api_key: OpenAI API key (defaults to settings.openai_api_key)
            model: Model name (defaults to settings.openai_embedding_model)
        """
        import openai

        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.model = model or settings.openai_embedding_model
        self.client = openai.OpenAI(api_key=self.api_key)

        # Model dimensions mapping
        self.dimensions_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        self.dimensions = self.dimensions_map.get(self.model, 1536)

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        return self._normalize(embedding)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        # OpenAI API supports batching natively
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )

        embeddings = [
            np.array(item.embedding, dtype=np.float32)
            for item in response.data
        ]

        return [self._normalize(emb) for emb in embeddings]

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "provider": "openai",
            "model": self.model,
            "dimensions": self.dimensions,
        }

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        """Normalize embedding to unit length."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm


class AzureOpenAIEmbedding(EmbeddingProvider):
    """
    Azure OpenAI embeddings provider.

    Uses Azure-hosted OpenAI embedding models.
    """

    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        deployment_name: str = None,
        api_version: str = None
    ):
        """
        Initialize Azure OpenAI embeddings.

        Args:
            endpoint: Azure OpenAI endpoint
            api_key: Azure OpenAI API key
            deployment_name: Deployment name
            api_version: API version
        """
        import openai

        self.endpoint = endpoint or settings.azure_openai_endpoint
        self.api_key = api_key or settings.azure_openai_api_key
        self.deployment_name = deployment_name or settings.azure_openai_deployment_name
        self.api_version = api_version or settings.azure_openai_api_version

        if not all([self.endpoint, self.api_key, self.deployment_name]):
            raise ValueError("Azure OpenAI configuration is incomplete")

        self.client = openai.AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )

        self.dimensions = 1536  # Default for most Azure OpenAI embedding models

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self.deployment_name,
            input=text
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        return self._normalize(embedding)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        response = self.client.embeddings.create(
            model=self.deployment_name,
            input=texts
        )

        embeddings = [
            np.array(item.embedding, dtype=np.float32)
            for item in response.data
        ]

        return [self._normalize(emb) for emb in embeddings]

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "provider": "azure-openai",
            "deployment": self.deployment_name,
            "dimensions": self.dimensions,
            "endpoint": self.endpoint,
        }

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        """Normalize embedding to unit length."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm


class EmbeddingService:
    """
    High-level embedding service with caching and batch processing.

    Provides a unified interface for embedding generation regardless of backend.
    """

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider (defaults to configured provider)
        """
        if provider:
            self.provider = provider
        else:
            self.provider = self._create_provider()

        self.model_info = self.provider.get_model_info()

    def _create_provider(self) -> EmbeddingProvider:
        """Create embedding provider based on configuration."""
        provider_type = settings.embedding_provider

        if provider_type == "local":
            # Check if model is BERT-based (use custom BERT class)
            if "bert" in settings.embedding_model.lower():
                return BertEmbedding()
            else:
                return SentenceTransformerEmbedding()
        elif provider_type == "openai":
            return OpenAIEmbedding()
        elif provider_type == "azure":
            return AzureOpenAIEmbedding()
        else:
            raise ValueError(f"Unknown embedding provider: {provider_type}")

    def embed_text(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Input text
            use_cache: Whether to use caching (default: True)

        Returns:
            Embedding vector
        """
        if use_cache:
            return self._cached_embed(text)
        else:
            return self.provider.embed_text(text)

    @lru_cache(maxsize=1000)
    def _cached_embed(self, text: str) -> tuple:
        """
        Cached embedding generation.

        Note: Returns tuple because numpy arrays are not hashable for lru_cache.
        """
        embedding = self.provider.embed_text(text)
        # Convert to tuple for caching
        return tuple(embedding)

    def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts
            batch_size: Batch size (defaults to settings.embedding_batch_size)
            show_progress: Whether to show progress (default: False)

        Returns:
            List of embedding vectors
        """
        batch_size = batch_size or settings.embedding_batch_size

        if len(texts) <= batch_size:
            return self.provider.embed_batch(texts)

        # Process in batches
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.provider.embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

            if show_progress:
                progress = min(100, int((i + batch_size) / len(texts) * 100))
                print(f"Embedding progress: {progress}%")

        return all_embeddings

    def get_dimensions(self) -> int:
        """Get embedding dimensions."""
        return self.model_info["dimensions"]

    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.model_info["provider"]

    def get_model_name(self) -> str:
        """Get model name."""
        return self.model_info.get("model") or self.model_info.get("deployment")


# Global embedding service instance
embedding_service = EmbeddingService()


def set_active_embedding_model(model_name: str):
    """
    Change the active embedding model.

    Args:
        model_name: New model name to use
    """
    global embedding_service
    from app.core import config

    # Update settings
    config.settings.embedding_model = model_name

    # Reinitialize embedding service with new model
    embedding_service = EmbeddingService()
