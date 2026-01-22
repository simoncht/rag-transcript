#!/bin/bash
# Shows current status of the video processing pipeline and system diagnostics
# Triggers: After changes to video_tasks.py, or manually for debugging

set -e

echo "📊 Pipeline Status Report"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if backend is running
if ! curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend not running at localhost:8000"
    exit 1
fi

# Run status check via Python script inside the container
docker compose exec -T app python -c "
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.video import Video
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.job import Job

# Setup database
engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
db = Session()

# ═══════════════════════════════════════════
# VIDEO PROCESSING STATUS
# ═══════════════════════════════════════════
print('📹 VIDEO PROCESSING STATUS')
print('─' * 40)

# Count by status
status_counts = db.query(
    Video.status,
    func.count(Video.id)
).filter(Video.is_deleted.is_(False)).group_by(Video.status).all()

status_dict = dict(status_counts)
total = sum(status_dict.values())

print(f'  Total videos: {total}')
for status in ['pending', 'downloading', 'transcribing', 'chunking', 'enriching', 'indexing', 'completed', 'failed']:
    count = status_dict.get(status, 0)
    if count > 0:
        emoji = '✓' if status == 'completed' else ('✗' if status == 'failed' else '⋯')
        print(f'  {emoji} {status}: {count}')

# Show stuck/failed videos
stuck_videos = db.query(Video).filter(
    Video.is_deleted.is_(False),
    Video.status.notin_(['completed', 'failed', 'pending']),
    Video.updated_at < datetime.utcnow() - timedelta(minutes=30)
).all()

if stuck_videos:
    print(f'\n  ⚠️  Potentially stuck videos ({len(stuck_videos)}):')
    for v in stuck_videos[:5]:
        print(f'     - {v.title[:40]}... (status: {v.status}, updated: {v.updated_at})')

failed_videos = db.query(Video).filter(
    Video.is_deleted.is_(False),
    Video.status == 'failed'
).order_by(Video.updated_at.desc()).limit(3).all()

if failed_videos:
    print(f'\n  ❌ Recent failures:')
    for v in failed_videos:
        error = (v.error_message or 'Unknown error')[:60]
        print(f'     - {v.title[:30]}...: {error}')

# ═══════════════════════════════════════════
# CHUNK & INDEX STATUS
# ═══════════════════════════════════════════
print('\n📦 CHUNK & INDEX STATUS')
print('─' * 40)

total_chunks = db.query(Chunk).count()
indexed_chunks = db.query(Chunk).filter(Chunk.is_indexed.is_(True)).count()
unindexed_chunks = total_chunks - indexed_chunks

print(f'  Total chunks: {total_chunks}')
print(f'  ✓ Indexed: {indexed_chunks}')
if unindexed_chunks > 0:
    print(f'  ⚠ Unindexed: {unindexed_chunks}')

# Check Qdrant
try:
    import requests
    # Use REST API directly to avoid client version issues
    info_response = requests.get(f'http://{settings.qdrant_host}:{settings.qdrant_port}/collections/transcript_chunks')
    info_data = info_response.json()
    points_count = info_data.get('result', {}).get('points_count', 0)
    print(f'\n  Qdrant vectors: {points_count}')

    if points_count != indexed_chunks:
        print(f'  ⚠ Mismatch: DB says {indexed_chunks} indexed, Qdrant has {points_count}')
except Exception as e:
    print(f'  ⚠ Could not check Qdrant: {e}')

# ═══════════════════════════════════════════
# CELERY QUEUE STATUS
# ═══════════════════════════════════════════
print('\n⚙️  CELERY QUEUE STATUS')
print('─' * 40)

try:
    import redis
    r = redis.from_url(settings.redis_url)

    # Check queue lengths
    queues = ['celery', 'video_processing']
    for queue in queues:
        length = r.llen(queue)
        if length > 0:
            print(f'  📬 {queue}: {length} pending tasks')
        else:
            print(f'  ✓ {queue}: empty')
except Exception as e:
    print(f'  ⚠ Could not check Redis: {e}')

# ═══════════════════════════════════════════
# CONVERSATION & USAGE STATS
# ═══════════════════════════════════════════
print('\n💬 CONVERSATION STATS')
print('─' * 40)

conversation_count = db.query(Conversation).count()
message_count = db.query(Message).count()
avg_messages = message_count / conversation_count if conversation_count > 0 else 0

print(f'  Conversations: {conversation_count}')
print(f'  Messages: {message_count}')
print(f'  Avg messages/conversation: {avg_messages:.1f}')

# Recent activity
recent_conversations = db.query(Conversation).filter(
    Conversation.last_message_at > datetime.utcnow() - timedelta(hours=24)
).count()
print(f'  Active (24h): {recent_conversations}')

# ═══════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════
print('\n⚙️  RAG CONFIGURATION')
print('─' * 40)
print(f'  Embedding model: {settings.embedding_model}')
print(f'  LLM model: {settings.llm_model}')
print(f'  Reranking enabled: {settings.enable_reranking}')
print(f'  Min relevance score: {settings.min_relevance_score}')
print(f'  Chunk target tokens: {settings.chunk_target_tokens}')

db.close()

print('\n' + '━' * 40)
print('✅ Pipeline status check complete')
"

echo ""
