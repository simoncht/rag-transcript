#!/bin/bash
# Combined infrastructure + pipeline health check
# Section 1 (always): Docker containers + connectivity
# Section 2 (--pipeline flag): RAG pipeline smoke test (embedding, retrieval, LLM)
#
# Proactive trigger runs Section 1 only (~5s).
# Manual: /infra-health --pipeline for full check.

set -e

RUN_PIPELINE=false
for arg in "$@"; do
    if [[ "$arg" == "--pipeline" ]]; then
        RUN_PIPELINE=true
    fi
done

# ── Section 1: Docker Services ──────────────────────────────────────

echo "🐳 Checking Docker services health..."

EXPECTED_SERVICES=("postgres" "redis" "qdrant" "app" "worker" "beat" "frontend")
FAILED_SERVICES=()

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Start Docker Desktop first."
    exit 1
fi

for service in "${EXPECTED_SERVICES[@]}"; do
    status=$(docker compose ps --format "{{.Service}}:{{.Status}}" 2>/dev/null | grep "^${service}:" | cut -d':' -f2 || echo "not found")

    if [[ "$status" == "not found" ]] || [[ -z "$status" ]]; then
        FAILED_SERVICES+=("$service (not running)")
    elif [[ "$status" != *"Up"* ]]; then
        FAILED_SERVICES+=("$service ($status)")
    else
        echo "  ✓ $service: running"
    fi
done

# ── Section 1b: Connectivity ────────────────────────────────────────

echo ""
echo "🔍 Checking Qdrant vector store..."
if curl -s --max-time 5 http://localhost:6333/collections > /dev/null 2>&1; then
    collections=$(curl -s http://localhost:6333/collections | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
    if [[ -n "$collections" ]]; then
        echo "  ✓ Qdrant: running (collections: $collections)"
    else
        echo "  ✓ Qdrant: running (no collections yet)"
    fi
else
    FAILED_SERVICES+=("qdrant (API not responding)")
fi

echo ""
echo "🗄️  Checking PostgreSQL database..."
if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "  ✓ PostgreSQL: accepting connections"
else
    FAILED_SERVICES+=("postgres (not accepting connections)")
fi

echo ""
echo "📮 Checking Redis..."
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo "  ✓ Redis: responding to ping"
else
    FAILED_SERVICES+=("redis (not responding)")
fi

# ── Section 1 Results ───────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ ${#FAILED_SERVICES[@]} -gt 0 ]]; then
    echo "❌ Failed services:"
    for service in "${FAILED_SERVICES[@]}"; do
        echo "   - $service"
    done
    echo ""
    echo "Fix with: docker compose up -d"
    exit 1
else
    echo "✅ All services healthy!"
fi

# ── Section 2: RAG Pipeline Smoke Test (only with --pipeline) ───────

if [[ "$RUN_PIPELINE" != true ]]; then
    echo ""
    echo "Tip: Run with --pipeline for full RAG smoke test"
    exit 0
fi

echo ""
echo "🧪 Running RAG Pipeline Smoke Test..."

if ! curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend not responding at localhost:8000"
    exit 1
fi

docker compose exec -T app python -c "
import sys
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.video import Video
from app.models.conversation import Conversation
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService

print('')
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

# Test 2: Vector Store
print('\n🔍 Test 2: Vector Store (Qdrant)')
start = time.time()
try:
    import requests
    response = requests.get(f'http://{settings.qdrant_host}:{settings.qdrant_port}/collections')
    collections_data = response.json()
    elapsed = (time.time() - start) * 1000
    collection_names = [c['name'] for c in collections_data.get('result', {}).get('collections', [])]

    if 'transcript_chunks' in collection_names:
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

# Test 3: Database
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

# Test 4: Retrieval (if data exists)
print('\n🎯 Test 4: Retrieval Test')
if completed_videos > 0:
    start = time.time()
    try:
        vector_service = VectorStoreService()
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        sample_video = db.query(Video).filter(
            Video.is_deleted.is_(False),
            Video.status == 'completed'
        ).first()
        if sample_video:
            test_query = 'What is discussed in this video?'
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
                preview = top_chunk.text[:100].replace(chr(10), ' ')
                print(f'  ✓ Preview: \"{preview}...\"')
            else:
                print(f'  ⚠ No chunks retrieved - check indexing')
        db.close()
    except Exception as e:
        print(f'  ✗ Retrieval failed: {e}')
        sys.exit(1)
else:
    print('  ⚠ Skipped - no completed videos to test against')

# Test 5: LLM
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
    sys.exit(1)

print('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('✅ RAG Pipeline Smoke Test PASSED')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
"

echo ""
echo "✅ Full infrastructure + pipeline check passed!"
