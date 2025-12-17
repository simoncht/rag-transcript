"""Settings endpoints for runtime configuration."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import settings
from app.services.embeddings import (
    EMBEDDING_PRESETS,
    embedding_service,
    resolve_collection_name,
    set_active_embedding_model,
)
from app.services.vector_store import vector_store_service
from app.tasks.video_tasks import reembed_all_videos

router = APIRouter()


@router.get("/embedding-model")
async def get_embedding_model():
    """Return active embedding model and available presets."""
    collection_name = resolve_collection_name(embedding_service)
    return {
        "active_key": embedding_service.get_model_key(),
        "active_model": embedding_service.get_model_name(),
        "dimensions": embedding_service.get_dimensions(),
        "collection_name": collection_name,
        "presets": [
            {"key": key, "model": preset["model"], "dimensions": preset["dimensions"]}
            for key, preset in EMBEDDING_PRESETS.items()
        ],
    }


@router.post("/embedding-model")
async def set_embedding_model(payload: dict, user=Depends(get_current_user)):
    """
    Set the active embedding model key and trigger re-embedding.

    This currently requires authentication (reuse get_current_user).
    """
    key = payload.get("model_key")
    if not key or key not in EMBEDDING_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid model_key")

    # Switch embedding service and re-init vector store for this collection
    new_service = set_active_embedding_model(key)
    collection_name = resolve_collection_name(new_service)
    vector_store_service.initialize(
        new_service.get_dimensions(),
        collection_name=collection_name,
    )

    # Trigger background re-embed job
    task = reembed_all_videos.delay(key)

    return {
        "active_key": new_service.get_model_key(),
        "active_model": new_service.get_model_name(),
        "dimensions": new_service.get_dimensions(),
        "collection_name": collection_name,
        "presets": [
            {"key": k, "model": p["model"], "dimensions": p["dimensions"]}
            for k, p in EMBEDDING_PRESETS.items()
        ],
        "reembed_task_id": task.id,
        "message": "Embedding model updated; re-embed job started.",
    }
