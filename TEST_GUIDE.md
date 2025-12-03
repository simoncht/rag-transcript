# Testing Guide - RAG Transcript System

Complete testing guide for the YouTube RAG transcript system.

## Pre-Flight Checks

### 1. Verify Prerequisites

Check that you have Docker installed:
```bash
docker --version
docker-compose --version
```

Check available disk space (need ~5GB):
```bash
# Windows
dir
# Linux/Mac
df -h .
```

### 2. Review Configuration

Check the `.env` file exists:
```bash
ls backend/.env
```

If not, create it:
```bash
cp backend/.env.example backend/.env
```

## Step 1: Start Services

### Start all containers:
```bash
cd C:\Users\PW278WC\ai\rag-transcript
docker-compose up -d
```

### Check all services are running:
```bash
docker-compose ps
```

You should see 6 services running:
- rag_transcript_postgres (port 5432)
- rag_transcript_redis (port 6379)
- rag_transcript_qdrant (ports 6333, 6334)
- rag_transcript_app (port 8000)
- rag_transcript_worker
- rag_transcript_beat

### View logs (in separate terminal):
```bash
# All services
docker-compose logs -f

# Or specific services
docker-compose logs -f app
docker-compose logs -f worker
```

## Step 2: Initialize Database

### Run database migrations:
```bash
docker-compose exec app alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> xxxxx, Initial migration
```

### Verify database tables:
```bash
docker-compose exec postgres psql -U postgres -d rag_transcript -c "\dt"
```

Should see tables:
- users
- videos
- transcripts
- chunks
- conversations
- messages
- message_chunk_references
- usage_events
- user_quotas
- jobs

## Step 3: Test API Health

### Health check:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "RAG Transcript System",
  "version": "0.1.0",
  "environment": "development"
}
```

### Root endpoint:
```bash
curl http://localhost:8000/
```

### API documentation:
Open in browser:
```
http://localhost:8000/docs
```

## Step 4: Test Video Ingestion

### Choose a test video:
Use a short video for testing (2-5 minutes recommended):
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ  # Classic (3:33)
https://www.youtube.com/watch?v=jNQXAC9IVRw  # "Me at the zoo" (0:19)
```

### Ingest video:
```bash
curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}' \
  | jq
```

Save the `video_id` and `job_id` from the response:
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Video ingestion started. Use the job_id to track progress."
}
```

## Step 5: Monitor Processing

### Check job status (replace {job_id}):
```bash
curl "http://localhost:8000/api/v1/jobs/660e8400-e29b-41d4-a716-446655440000" | jq
```

You should see progress updates:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "job_type": "full_pipeline",
  "status": "running",
  "progress_percent": 45.0,
  "current_step": "Transcribing audio",
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Watch worker logs:
```bash
docker-compose logs -f worker
```

You should see:
1. "Task starting: download_youtube_audio"
2. "Task starting: transcribe_audio"
3. "Task starting: chunk_and_enrich"
4. "Task starting: embed_and_index"

### Poll status every 10 seconds:
```bash
# Linux/Mac
watch -n 10 'curl -s "http://localhost:8000/api/v1/jobs/{job_id}" | jq ".status, .progress_percent, .current_step"'

# Windows PowerShell
while($true) {
  curl "http://localhost:8000/api/v1/jobs/{job_id}" | ConvertFrom-Json | Select status,progress_percent,current_step
  Start-Sleep -Seconds 10
}
```

## Step 6: Verify Completion

### Check video status:
```bash
curl "http://localhost:8000/api/v1/videos/550e8400-e29b-41d4-a716-446655440000" | jq
```

Expected (when completed):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress_percent": 100.0,
  "chunk_count": 5,
  "transcription_language": "en",
  ...
}
```

### List all videos:
```bash
curl "http://localhost:8000/api/v1/videos?skip=0&limit=10" | jq
```

### Check storage directory:
```bash
# Linux/Mac
ls -lh storage/audio/
ls -lh storage/transcripts/

# Windows
dir storage\audio
dir storage\transcripts
```

### Verify Qdrant indexing:
```bash
curl "http://localhost:6333/collections/transcript_chunks" | jq
```

Should show:
```json
{
  "result": {
    "status": "green",
    "vectors_count": 5,  # Number of chunks
    "points_count": 5
  }
}
```

## Step 7: Test Conversation Management

### Create a conversation:
```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test conversation",
    "selected_video_ids": ["550e8400-e29b-41d4-a716-446655440000"]
  }' | jq
```

Save the `conversation_id`:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "title": "Test conversation",
  "selected_video_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "message_count": 0
}
```

### List conversations:
```bash
curl "http://localhost:8000/api/v1/conversations" | jq
```

### Get conversation details:
```bash
curl "http://localhost:8000/api/v1/conversations/770e8400-e29b-41d4-a716-446655440000" | jq
```

## Step 8: Verify Database Contents

### Check database records:
```bash
# Count videos
docker-compose exec postgres psql -U postgres -d rag_transcript -c "SELECT COUNT(*) FROM videos;"

# Count chunks
docker-compose exec postgres psql -U postgres -d rag_transcript -c "SELECT COUNT(*) FROM chunks;"

# View chunk details
docker-compose exec postgres psql -U postgres -d rag_transcript -c "SELECT chunk_index, token_count, chunk_title FROM chunks ORDER BY chunk_index LIMIT 5;"

# Check usage events
docker-compose exec postgres psql -U postgres -d rag_transcript -c "SELECT event_type, event_timestamp FROM usage_events ORDER BY event_timestamp DESC LIMIT 10;"

# Check user quotas
docker-compose exec postgres psql -U postgres -d rag_transcript -c "SELECT videos_used, videos_limit, minutes_used, minutes_limit FROM user_quotas;"
```

## Step 9: Test Edge Cases

### Test invalid YouTube URL:
```bash
curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://invalid-url.com"}' | jq
```

Should return 400 error:
```json
{
  "detail": "Could not extract video ID from URL: https://invalid-url.com"
}
```

### Test video deletion:
```bash
curl -X DELETE "http://localhost:8000/api/v1/videos/550e8400-e29b-41d4-a716-446655440000" | jq
```

Should return:
```json
{
  "message": "Video deleted successfully",
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Verify video is soft-deleted:
```bash
curl "http://localhost:8000/api/v1/videos/550e8400-e29b-41d4-a716-446655440000"
```

Should return 404:
```json
{
  "detail": "Video not found"
}
```

## Step 10: Performance Testing

### Test multiple videos concurrently:
```bash
# Ingest 3 videos at once
curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_1"}' &

curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_2"}' &

curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_3"}' &
```

Watch worker process them:
```bash
docker-compose logs -f worker
```

## Common Issues & Solutions

### Issue: Port 8000 already in use
**Solution**: Change port in docker-compose.yml:
```yaml
ports:
  - "8001:8000"
```

### Issue: PostgreSQL connection refused
**Solution**: Wait for postgres to be ready:
```bash
docker-compose logs postgres
docker-compose restart app worker
```

### Issue: Celery tasks not running
**Solution**: Check worker is running:
```bash
docker-compose ps worker
docker-compose logs worker
docker-compose restart worker
```

### Issue: Whisper model download fails
**Solution**: Check disk space and internet connection:
```bash
df -h
docker-compose logs worker | grep -i whisper
```

Pre-download model manually:
```bash
docker-compose exec worker python -c "import whisper; whisper.load_model('base')"
```

### Issue: Out of memory
**Solution**: Reduce worker concurrency:
```yaml
# In docker-compose.yml
command: celery -A app.core.celery_app worker --loglevel=info --concurrency=1
```

### Issue: Qdrant connection error
**Solution**: Check Qdrant is running:
```bash
docker-compose ps qdrant
curl http://localhost:6333/healthz
docker-compose restart qdrant app worker
```

## Success Checklist

- [ ] All Docker services started
- [ ] Database migrations completed
- [ ] Health check passes
- [ ] Video ingestion succeeds
- [ ] Job status updates correctly
- [ ] Video processing completes
- [ ] Chunks created and indexed
- [ ] Conversation created successfully
- [ ] Database contains expected records
- [ ] Qdrant vector store populated

## Next Steps

After successful testing:

1. **Test with longer videos** (10-30 minutes)
2. **Test with different languages** (if Whisper model supports it)
3. **Implement Phase 2** (RAG chat functionality)
4. **Build frontend** (React/Next.js UI)
5. **Add monitoring** (Prometheus, Grafana)

## Performance Benchmarks

Expected processing times (on typical hardware):

- **Audio download**: 10-30 seconds per minute of video
- **Transcription** (Whisper base): ~1x realtime (3 min video → 3 min processing)
- **Chunking**: <5 seconds for any video
- **Enrichment**: 2-5 seconds per chunk (depends on LLM)
- **Embedding**: 1-2 seconds for 10 chunks (local)
- **Indexing**: <1 second

**Total for 3-minute video**: ~5-10 minutes with enrichment enabled

To speed up:
- Use smaller Whisper model (tiny)
- Disable contextual enrichment
- Use faster LLM (GPT-4 → GPT-3.5)
- Increase worker concurrency
