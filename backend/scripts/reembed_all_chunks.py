#!/usr/bin/env python3
"""
Re-embed all chunks after an embedding model change.

Loads chunks from the database, embeds with the current model,
and upserts to Qdrant. Processes per-video atomically.

Usage:
    python scripts/reembed_all_chunks.py                     # Re-embed all
    python scripts/reembed_all_chunks.py --dry-run            # Preview scope
    python scripts/reembed_all_chunks.py --batch-size 50      # Custom batch size
    python scripts/reembed_all_chunks.py --video-id <uuid>    # Single video
"""
import argparse
import os
import sys
import time
import uuid as uuid_mod
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models import Video
from app.models.chunk import Chunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import QdrantVectorStore, VectorStoreService
from app.services.enrichment import EnrichedChunk
from app.services.chunking import Chunk as ChunkData
from app.core.config import settings


def reembed_all_chunks(
    batch_size: int = 100,
    dry_run: bool = False,
    video_id: str = None,
):
    """
    Re-embed all chunks with the current embedding model.

    Args:
        batch_size: Number of chunks to embed per batch
        dry_run: If True, just print what would be done
        video_id: Optional single video UUID to process
    """
    db: Session = SessionLocal()
    embedding_service = EmbeddingService()
    vector_store = QdrantVectorStore()

    model_info = embedding_service.get_model_name()
    print(f"Embedding model: {model_info}")
    print(f"Batch size: {batch_size}")

    try:
        # Find videos with indexed chunks
        query = (
            db.query(Video)
            .filter(
                Video.status == "completed",
                Video.is_deleted == False,
            )
            .order_by(Video.created_at.desc())
        )

        if video_id:
            query = query.filter(Video.id == UUID(video_id))

        videos = query.all()
        print(f"Found {len(videos)} videos to re-embed")

        if dry_run:
            total_chunks = 0
            for video in videos:
                chunk_count = (
                    db.query(func.count(Chunk.id))
                    .filter(Chunk.video_id == video.id)
                    .scalar()
                )
                total_chunks += chunk_count
                print(f"  - {video.title[:60]}... ({chunk_count} chunks)")
            print(f"\nTotal: {total_chunks} chunks would be re-embedded")
            return

        # Process each video atomically
        success = 0
        failed = 0
        total_chunks_processed = 0
        start_time = time.time()

        for i, video in enumerate(videos, 1):
            print(f"\n[{i}/{len(videos)}] Processing: {video.title[:60]}...")

            try:
                # Load chunks for this video
                chunks = (
                    db.query(Chunk)
                    .filter(Chunk.video_id == video.id)
                    .order_by(Chunk.chunk_index)
                    .all()
                )

                if not chunks:
                    print(f"  No chunks found, skipping")
                    continue

                # Get embedding texts
                texts = []
                for chunk in chunks:
                    # Use stored embedding_text if available, otherwise chunk text
                    text = chunk.embedding_text or chunk.text
                    texts.append(text)

                # Embed in batches
                all_embeddings = embedding_service.embed_batch(
                    texts, batch_size=batch_size
                )

                # Build EnrichedChunk objects for vector store
                enriched_chunks = []
                for chunk in chunks:
                    chunk_data = ChunkData(
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        start_timestamp=chunk.start_timestamp,
                        end_timestamp=chunk.end_timestamp,
                        token_count=chunk.token_count,
                        duration_seconds=chunk.duration_seconds,
                        speakers=chunk.speakers,
                        chapter_title=chunk.chapter_title,
                        chapter_index=chunk.chapter_index,
                    )
                    enriched = EnrichedChunk(
                        chunk=chunk_data,
                        title=chunk.chunk_title,
                        summary=chunk.chunk_summary,
                        keywords=chunk.keywords,
                    )
                    enriched_chunks.append(enriched)

                # Delete old vectors and insert new ones (atomic per video)
                vector_store.delete_by_video_id(video.id)

                # Determine content type
                content_type = getattr(video, "content_type", "youtube") or "youtube"

                vector_store.index_chunks(
                    enriched_chunks=enriched_chunks,
                    embeddings=all_embeddings,
                    user_id=video.user_id,
                    video_id=video.id,
                    content_type=content_type,
                )

                total_chunks_processed += len(chunks)
                success += 1
                print(f"  Re-embedded {len(chunks)} chunks")

                if total_chunks_processed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = total_chunks_processed / elapsed if elapsed > 0 else 0
                    print(f"  [Progress] {total_chunks_processed} chunks, {rate:.1f} chunks/s")

            except Exception as e:
                print(f"  Error: {e}")
                failed += 1

        elapsed = time.time() - start_time
        print(f"\n{'='*50}")
        print(f"Re-embedding complete: {success} videos, {total_chunks_processed} chunks")
        print(f"Failed: {failed}")
        print(f"Time: {elapsed:.1f}s ({total_chunks_processed/elapsed:.1f} chunks/s)" if elapsed > 0 else "")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-embed all chunks")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="Preview scope")
    parser.add_argument("--video-id", type=str, help="Single video UUID")

    args = parser.parse_args()
    reembed_all_chunks(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        video_id=args.video_id,
    )
