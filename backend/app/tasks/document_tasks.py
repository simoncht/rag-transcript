"""
Celery tasks for document processing pipeline.

Pipeline:
1. Extract text from document (Kreuzberg)
2. Chunk document (section/page-aware)
3. Enrich chunks (LLM summaries, titles, keywords)
4. Embed and index in vector store
5. Generate document summary
"""
import asyncio
import logging
from uuid import UUID
from datetime import datetime

from app.core.celery_app import celery_app
from app.db.base import SessionLocal
from app.models import Video, Chunk as ChunkModel
from app.services.storage import storage_service
from app.services.usage_tracker import UsageTracker
from app.core.config import settings

logger = logging.getLogger(__name__)


def _update_status(db, content_id: UUID, status: str, progress: float, error: str = None):
    """Helper to update content processing status."""
    video = db.query(Video).filter(Video.id == content_id).first()
    if video:
        video.status = status
        video.progress_percent = progress
        if error:
            video.error_message = error
        if status == "completed":
            video.completed_at = datetime.utcnow()
        db.commit()


def _extract_document(content_id: str):
    """Extract text from uploaded document."""
    db = SessionLocal()
    content_uuid = UUID(content_id)

    try:
        logger.info(f"[Document Pipeline] Extract start for content={content_id}")
        _update_status(db, content_uuid, "extracting", 10.0)

        video = db.query(Video).filter(Video.id == content_uuid).first()
        if not video or not video.document_file_path:
            raise ValueError(f"Document file not found for content={content_id}")

        # Run async extraction in sync context
        from app.services.document_extractor import document_extractor

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                document_extractor.extract(video.document_file_path, video.content_type)
            )
        finally:
            loop.close()

        # Save extracted text to storage
        extracted_data = {
            "full_text": result.full_text,
            "pages": [
                {
                    "page_number": p.page_number,
                    "text": p.text,
                    "headings": p.headings,
                }
                for p in result.pages
            ],
            "page_count": result.page_count,
            "word_count": result.word_count,
            "content_type": result.content_type,
            "metadata": result.metadata,
        }

        extracted_path = storage_service.save_extracted_text(
            video.user_id, content_uuid, extracted_data
        )

        # Update video record
        video.extracted_text_path = extracted_path
        video.page_count = result.page_count
        if result.metadata:
            video.source_metadata = result.metadata
        video.status = "extracted"
        video.progress_percent = 30.0
        db.commit()

        # Track extracted text storage (mirrors video_tasks.py transcript tracking)
        try:
            import json as _json
            extracted_size_bytes = len(_json.dumps(extracted_data).encode("utf-8"))
            extracted_size_mb = extracted_size_bytes / (1024 * 1024)
            usage_tracker = UsageTracker(db)
            usage_tracker.track_storage_usage(
                video.user_id,
                extracted_size_mb,
                reason="document_text_extracted",
                video_id=content_uuid,
                extra_metadata={"page_count": result.page_count, "word_count": result.word_count},
            )
        except Exception as e:
            logger.warning(f"[Document Pipeline] Failed to track extraction storage for content={content_id}: {e}")

        logger.info(
            f"[Document Pipeline] Extract complete for content={content_id}, "
            f"pages={result.page_count}, words={result.word_count}"
        )

        return extracted_data

    except Exception as e:
        _update_status(db, content_uuid, "failed", 0.0, f"Extraction failed: {str(e)}")
        raise
    finally:
        db.close()


def _chunk_and_enrich_document(content_id: str, extracted_data: dict):
    """Chunk extracted document text and enrich with LLM metadata."""
    db = SessionLocal()
    content_uuid = UUID(content_id)

    try:
        logger.info(f"[Document Pipeline] Chunk/enrich start for content={content_id}")
        _update_status(db, content_uuid, "chunking", 35.0)

        video = db.query(Video).filter(Video.id == content_uuid).first()

        # Reconstruct pages from extracted data
        from app.services.document_extractor import ExtractedPage
        pages = [
            ExtractedPage(
                page_number=p["page_number"],
                text=p["text"],
                headings=p.get("headings", []),
            )
            for p in extracted_data["pages"]
        ]

        # Chunk the document
        from app.services.document_chunker import DocumentChunker
        chunker = DocumentChunker()
        doc_chunks = chunker.chunk_document(pages)

        if not doc_chunks and pages:
            # Fallback: single chunk from all text
            from app.services.document_chunker import DocumentChunk
            full_text = extracted_data["full_text"]
            doc_chunks = [
                DocumentChunk(
                    text=full_text[:settings.chunk_max_tokens * 4],  # Rough limit
                    token_count=chunker.count_tokens(full_text[:settings.chunk_max_tokens * 4]),
                    chunk_index=0,
                    page_number=1,
                )
            ]

        _update_status(db, content_uuid, "enriching", 50.0)

        # Enrich chunks with full document text for contextual grounding
        from app.services.enrichment import ContextualEnricher
        full_document_text = extracted_data.get("full_text", "")
        enricher = ContextualEnricher(
            content_type=video.content_type,
            full_text=full_document_text,
        )
        enricher.set_source_context(video.title, video.description)

        # Convert DocumentChunks to Chunk-compatible objects for enrichment
        from app.services.chunking import Chunk as ChunkData
        enriched_chunks = []

        for i, doc_chunk in enumerate(doc_chunks):
            # Create a Chunk-compatible object
            chunk_data = ChunkData(
                text=doc_chunk.text,
                start_timestamp=doc_chunk.start_timestamp,
                end_timestamp=doc_chunk.end_timestamp,
                token_count=doc_chunk.token_count,
                chunk_index=doc_chunk.chunk_index,
            )
            # Attach document-specific attrs for enrichment prompt
            chunk_data.page_number = doc_chunk.page_number
            chunk_data.section_heading = doc_chunk.section_heading

            enriched = enricher.enrich_chunk(chunk_data)
            enriched_chunks.append((enriched, doc_chunk))

            progress = 50.0 + (i + 1) / len(doc_chunks) * 30.0
            _update_status(db, content_uuid, "enriching", progress)

        # Save chunks to database
        for enriched_chunk, doc_chunk in enriched_chunks:
            chunk = enriched_chunk.chunk
            db_chunk = ChunkModel(
                video_id=content_uuid,
                user_id=video.user_id,
                content_type=video.content_type,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
                duration_seconds=0.0,
                page_number=doc_chunk.page_number,
                section_heading=doc_chunk.section_heading,
                chunk_summary=enriched_chunk.summary,
                chunk_title=enriched_chunk.title,
                keywords=enriched_chunk.keywords,
                embedding_text=enriched_chunk.embedding_text,
                enriched_at=datetime.utcnow(),
            )
            db.add(db_chunk)

        video.chunk_count = len(enriched_chunks)
        video.status = "chunked"
        video.progress_percent = 80.0
        db.commit()

        logger.info(
            f"[Document Pipeline] Chunk/enrich complete for content={content_id}, "
            f"chunks={len(enriched_chunks)}"
        )
        return {"chunk_count": len(enriched_chunks)}

    except Exception as e:
        _update_status(db, content_uuid, "failed", 0.0, f"Chunking failed: {str(e)}")
        raise
    finally:
        db.close()


def _embed_and_index_document(content_id: str):
    """Embed document chunks and index in vector store."""
    db = SessionLocal()
    content_uuid = UUID(content_id)

    try:
        logger.info(f"[Document Pipeline] Embed/index start for content={content_id}")
        _update_status(db, content_uuid, "indexing", 85.0)

        video = db.query(Video).filter(Video.id == content_uuid).first()

        chunks = (
            db.query(ChunkModel)
            .filter(ChunkModel.video_id == content_uuid, ChunkModel.is_indexed.is_(False))
            .order_by(ChunkModel.chunk_index)
            .all()
        )

        if not chunks:
            _update_status(db, content_uuid, "completed", 100.0)
            return {"indexed_count": 0}

        # Generate embeddings
        from app.services.embeddings import embedding_service, resolve_collection_name

        embedding_texts = [chunk.embedding_text or chunk.text for chunk in chunks]
        embeddings = embedding_service.embed_batch(embedding_texts, show_progress=False)

        _update_status(db, content_uuid, "indexing", 92.0)

        # Prepare enriched chunks for indexing
        from app.services.enrichment import EnrichedChunk
        from app.services.chunking import Chunk as ChunkData

        enriched_chunks = []
        for db_chunk in chunks:
            chunk_data = ChunkData(
                text=db_chunk.text,
                start_timestamp=db_chunk.start_timestamp,
                end_timestamp=db_chunk.end_timestamp,
                token_count=db_chunk.token_count,
                chunk_index=db_chunk.chunk_index,
            )
            # Attach document-specific fields
            chunk_data.page_number = db_chunk.page_number
            chunk_data.section_heading = db_chunk.section_heading

            enriched = EnrichedChunk(
                chunk=chunk_data,
                summary=db_chunk.chunk_summary,
                title=db_chunk.chunk_title,
                keywords=db_chunk.keywords,
            )
            enriched_chunks.append(enriched)

        # Index in vector store
        from app.services.vector_store import vector_store_service

        collection_name = resolve_collection_name(embedding_service)
        vector_store_service.initialize(
            embedding_service.get_dimensions(),
            collection_name=collection_name,
        )
        vector_store_service.index_video_chunks(
            enriched_chunks=enriched_chunks,
            embeddings=embeddings,
            user_id=video.user_id,
            video_id=content_uuid,
            content_type=video.content_type,
        )

        # Mark chunks as indexed
        for chunk in chunks:
            chunk.is_indexed = True
            chunk.indexed_at = datetime.utcnow()

        video.status = "completed"
        video.progress_percent = 100.0
        video.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"[Document Pipeline] Embed/index complete for content={content_id}, "
            f"indexed={len(chunks)}"
        )
        return {"indexed_count": len(chunks)}

    except Exception as e:
        _update_status(db, content_uuid, "failed", 0.0, f"Indexing failed: {str(e)}")
        raise
    finally:
        db.close()


def _generate_document_summary(content_id: str):
    """Generate document-level summary for two-level retrieval."""
    db = SessionLocal()
    content_uuid = UUID(content_id)

    try:
        video = db.query(Video).filter(Video.id == content_uuid).first()
        if not video:
            return {"success": False, "error": "Content not found"}

        # Get first few chunks for summary context
        chunks = (
            db.query(ChunkModel)
            .filter(ChunkModel.video_id == content_uuid)
            .order_by(ChunkModel.chunk_index)
            .limit(10)
            .all()
        )

        if not chunks:
            return {"success": False, "error": "No chunks to summarize"}

        # Build context from chunks
        chunk_texts = [c.text for c in chunks]
        combined_text = "\n\n".join(chunk_texts)[:8000]  # Limit to ~8K chars

        from app.services.llm_providers import llm_service, Message

        messages = [
            Message(
                role="system",
                content=(
                    "You are an expert document summarizer. Generate a concise summary "
                    "(200-500 words) and list 3-7 key topics for the following document content. "
                    "Return JSON: {\"summary\": \"...\", \"key_topics\": [\"topic1\", ...]}"
                ),
            ),
            Message(
                role="user",
                content=f"Document title: {video.title}\n\nContent:\n{combined_text}",
            ),
        ]

        try:
            response = llm_service.complete(
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

            import json
            text = response.content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            data = json.loads(text.strip())
            video.summary = data.get("summary", "")
            video.key_topics = data.get("key_topics", [])
            video.summary_generated_at = datetime.utcnow()
            db.commit()

            logger.info(f"[Document Pipeline] Summary generated for content={content_id}")
            return {"success": True}

        except Exception as e:
            logger.warning(f"[Document Pipeline] Summary generation failed: {e}")
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"[Document Pipeline] Summary error for content={content_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task
def process_document_pipeline(content_id: str):
    """
    Orchestrate the full document processing pipeline.

    Pipeline:
    1. Extract text (Kreuzberg)
    2. Chunk and enrich (section/page-aware + LLM)
    3. Embed and index (vector store)
    4. Generate summary (optional, non-blocking)

    Args:
        content_id: Content UUID (video table, content_type != 'youtube')
    """
    db = SessionLocal()

    try:
        logger.info(f"[Document Pipeline] Starting pipeline for content={content_id}")

        # Step 1: Extract text
        extracted_data = _extract_document(content_id)

        # Step 2: Chunk and enrich
        chunk_result = _chunk_and_enrich_document(content_id, extracted_data)

        # Step 3: Embed and index
        index_result = _embed_and_index_document(content_id)

        # Step 4: Generate summary (non-blocking)
        summary_result = _generate_document_summary(content_id)

        logger.info(
            f"[Document Pipeline] Complete for content={content_id}, "
            f"chunks={chunk_result['chunk_count']}, indexed={index_result['indexed_count']}"
        )

        return {
            "status": "completed",
            "chunk_count": chunk_result["chunk_count"],
            "indexed_count": index_result["indexed_count"],
            "summary_generated": summary_result.get("success", False),
        }

    except Exception as e:
        logger.error(f"[Document Pipeline] Failed for content={content_id}: {e}")
        # Status already updated by individual steps
        return {
            "status": "failed",
            "error": str(e),
        }

    finally:
        db.close()
