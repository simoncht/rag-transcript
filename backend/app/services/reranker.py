"""
Re-ranking service using cross-encoder models.

This module must be safe to import in offline / test environments:
- No model downloads at import time.
- Loading failures degrade gracefully (reranking becomes a no-op).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from app.core.config import settings


logger = logging.getLogger(__name__)


class _CrossEncoder(Protocol):
    def predict(self, sentences: Sequence[Tuple[str, str]]) -> Any:
        ...


def _coerce_scores(scores: Any) -> List[float]:
    if scores is None:
        return []

    if isinstance(scores, np.ndarray):
        return [float(x) for x in scores.tolist()]

    if isinstance(scores, (list, tuple)):
        return [float(x) for x in scores]

    try:
        return [float(scores)]
    except Exception:  # noqa: BLE001
        return []


class RerankerService:
    """
    Lazily loads a sentence-transformers CrossEncoder and re-orders chunks.

    The public API uses `rerank(...)`. `rerank_chunks(...)` is kept as a
    backwards-compatible alias for older callsites.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or getattr(
            settings, "reranking_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self._model: Optional[_CrossEncoder] = None
        self._load_error: Optional[BaseException] = None

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "enable_reranking", False))

    def _ensure_model(self) -> None:
        if self._model is not None or self._load_error is not None:
            return

        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            self._model = CrossEncoder(self.model_name)
        except Exception as exc:  # noqa: BLE001
            self._load_error = exc
            logger.warning(
                "Re-ranking disabled: unable to load model '%s' (%s)",
                self.model_name,
                exc,
            )

    def rerank(
        self,
        *,
        query: str,
        chunks: Sequence[Any],
        top_k: Optional[int] = None,
    ) -> List[Any]:
        """
        Re-rank chunks using a cross-encoder model, returning chunks in new order.

        If reranking is disabled or the model cannot be loaded, returns the
        original ordering.
        """
        if not chunks:
            return []

        if not self.enabled:
            return list(chunks[:top_k] if top_k else chunks)

        self._ensure_model()
        if self._model is None:
            return list(chunks[:top_k] if top_k else chunks)

        try:
            pairs = [(query, getattr(chunk, "text", "")) for chunk in chunks]
            scores = _coerce_scores(self._model.predict(pairs))
            if len(scores) != len(chunks):
                raise ValueError("CrossEncoder returned unexpected score count")

            ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
            reranked_chunks = [chunk for chunk, _score in ranked]
            return reranked_chunks[:top_k] if top_k else reranked_chunks
        except Exception as exc:  # noqa: BLE001
            logger.warning("Re-ranking failed (%s); returning original ordering", exc)
            return list(chunks[:top_k] if top_k else chunks)

    def rerank_chunks(
        self,
        query: str,
        chunks: Sequence[Any],
        top_k: Optional[int] = None,
    ) -> List[Any]:
        return self.rerank(query=query, chunks=chunks, top_k=top_k)

    def get_model_info(self) -> dict:
        return {"model": self.model_name, "enabled": self.enabled}


reranker_service = RerankerService()
