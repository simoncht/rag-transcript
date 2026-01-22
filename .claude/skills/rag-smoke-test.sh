#!/bin/bash
# Tests the RAG pipeline end-to-end with a sample query
# Triggers: After changes to RAG-related services (chunking, embeddings, vector_store, conversations, reranker)

set -e

echo "🧪 Running RAG Smoke Test..."
echo ""

# Check if backend is running
if ! curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend not running at localhost:8000"
    echo "   Start with: docker compose up -d"
    exit 1
fi

# Run the smoke test via Python script inside the container
docker compose exec -T app python -c "
import sys
import time
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup
from app.core.config import settings
from app.models.video import Video
from app.models.conversation import Conversation
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService

print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('RAG PIPELINE SMOKE TEST')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

# Test 1: Embedding Service
print('\n📊 Test 1: Embedding Service')
start = time.time()
try:
    embedding_service = EmbeddingService()
    test_text = 'What is the main topic of this video?'
    embedding = embedding_service.embed_text(test_text)
    elapsed = (time.time() - start) * 1000
    print(f'  ✓ Generated embedding: {len(embedding)} dimensions in {elapsed:.0f}ms')
    print(f'  ✓ Model: {settings.embedding_model}')
except Exception as e:
    print(f'  ✗ Embedding failed: {e}')
    sys.exit(1)

# Test 2: Vector Store Connection
print('\n🔍 Test 2: Vector Store (Qdrant)')
start = time.time()
try:
    import requests
    # Use REST API directly to avoid client version issues
    response = requests.get(f'http://{settings.qdrant_host}:{settings.qdrant_port}/collections')
    collections_data = response.json()
    elapsed = (time.time() - start) * 1000

    collection_names = [c['name'] for c in collections_data.get('result', {}).get('collections', [])]

    if 'transcript_chunks' in collection_names:
        # Get collection info via REST
        info_response = requests.get(f'http://{settings.qdrant_host}:{settings.qdrant_port}/collections/transcript_chunks')
        info_data = info_response.json()
        points_count = info_data.get('result', {}).get('points_count', 0)
        print(f'  ✓ Connected to Qdrant in {elapsed:.0f}ms')
        print(f'  ✓ Collection: transcript_chunks ({points_count} vectors)')
    else:
        print(f'  ⚠ Qdrant connected but no transcript_chunks collection')
        print(f'  → Index a video first to create the collection')
except Exception as e:
    print(f'  ✗ Vector store failed: {e}')
    sys.exit(1)

# Test 3: Database & Sample Data
print('\n🗄️  Test 3: Database Check')
start = time.time()
try:
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    video_count = db.query(Video).filter(Video.is_deleted.is_(False)).count()
    completed_videos = db.query(Video).filter(
        Video.is_deleted.is_(False),
        Video.status == 'completed'
    ).count()
    conversation_count = db.query(Conversation).count()

    elapsed = (time.time() - start) * 1000
    print(f'  ✓ Database connected in {elapsed:.0f}ms')
    print(f'  ✓ Videos: {completed_videos} completed / {video_count} total')
    print(f'  ✓ Conversations: {conversation_count}')

    db.close()
except Exception as e:
    print(f'  ✗ Database failed: {e}')
    sys.exit(1)

# Test 4: Retrieval Test (if data exists)
print('\n🎯 Test 4: Retrieval Test')
if completed_videos > 0:
    start = time.time()
    try:
        # Initialize vector service
        vector_service = VectorStoreService()

        # Get a sample video to test against
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        db = Session()

        sample_video = db.query(Video).filter(
            Video.is_deleted.is_(False),
            Video.status == 'completed'
        ).first()

        if sample_video:
            # Test retrieval
            import numpy as np
            test_query = 'What is discussed in this video?'
            # Use uncached embedding to get numpy array
            query_embedding = embedding_service.embed_text(test_query, use_cache=False)

            results = vector_service.search_chunks(
                query_embedding=query_embedding,
                video_ids=[sample_video.id],
                user_id=sample_video.user_id,
                top_k=5
            )

            elapsed = (time.time() - start) * 1000
            print(f'  ✓ Retrieved {len(results)} chunks in {elapsed:.0f}ms')

            if results:
                top_chunk = results[0]
                print(f'  ✓ Top result: score={top_chunk.score:.3f}')
                preview = top_chunk.text[:100].replace('\\n', ' ')
                print(f'  ✓ Preview: \"{preview}...\"')
            else:
                print(f'  ⚠ No chunks retrieved - check indexing')

        db.close()
    except Exception as e:
        print(f'  ✗ Retrieval failed: {e}')
        sys.exit(1)
else:
    print('  ⚠ Skipped - no completed videos to test against')
    print('  → Add and process a video first')

# Test 5: LLM Connection
print('\n🤖 Test 5: LLM Provider')
start = time.time()
try:
    from app.services.llm_providers import LLMService
    llm_service = LLMService()
    elapsed = (time.time() - start) * 1000
    print(f'  ✓ LLM service initialized in {elapsed:.0f}ms')
    print(f'  ✓ Model: {settings.llm_model}')
    print(f'  ✓ Provider: {type(llm_service.provider).__name__}')
except Exception as e:
    print(f'  ✗ LLM provider failed: {e}')
    print(f'  → Check if Ollama is running: curl http://localhost:11434/api/tags')
    sys.exit(1)

# Summary
print('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('✅ RAG Pipeline Smoke Test PASSED')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
"

echo ""
echo "✅ RAG smoke test completed successfully!"
