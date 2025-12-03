# Setup Guide

This guide will help you set up and run the RAG Transcript System locally.

## Prerequisites

- **Docker** and **Docker Compose** (recommended for easy setup)
- OR **Python 3.11+** (for manual setup)
- **ffmpeg** (for audio processing)
- **Git**

## Quick Start with Docker (Recommended)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd rag-transcript
```

### 2. Create Environment File

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your configuration:
- For local development, the defaults should work
- If using OpenAI or Anthropic, add your API keys

### 3. Start All Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant (port 6333)
- FastAPI app (port 8000)
- Celery worker
- Celery beat

### 4. Run Database Migrations

```bash
docker-compose exec app alembic upgrade head
```

### 5. Verify Setup

Check health:
```bash
curl http://localhost:8000/health
```

View API docs:
```
http://localhost:8000/docs
```

## Manual Setup (Without Docker)

### 1. Install System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip ffmpeg postgresql redis-server
```

#### macOS
```bash
brew install python@3.11 ffmpeg postgresql redis
```

#### Windows
- Install Python 3.11 from python.org
- Install ffmpeg from ffmpeg.org
- Install PostgreSQL from postgresql.org
- Install Redis (via WSL or Windows port)

### 2. Install Qdrant

```bash
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

Or download binary from: https://qdrant.tech/documentation/quick-start/

### 3. Set Up Python Environment

```bash
cd backend
python -m venv venv

# Activate venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your database and service URLs:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_transcript
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 5. Set Up Database

```bash
# Create database
createdb rag_transcript

# Run migrations
alembic upgrade head
```

### 6. Start Services

Terminal 1 - FastAPI:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 - Celery Worker:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

Terminal 3 - Celery Beat (optional):
```bash
celery -A app.core.celery_app beat --loglevel=info
```

## Usage

### 1. Ingest a YouTube Video

```bash
curl -X POST "http://localhost:8000/api/v1/videos/ingest" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

Response:
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Video ingestion started"
}
```

### 2. Check Processing Status

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

Response:
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

### 3. List Videos

```bash
curl "http://localhost:8000/api/v1/videos?skip=0&limit=10"
```

### 4. Get Video Details

```bash
curl "http://localhost:8000/api/v1/videos/{video_id}"
```

### 5. Create Conversation

```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Discussion about React",
    "selected_video_ids": ["550e8400-e29b-41d4-a716-446655440000"]
  }'
```

### 6. Send Chat Message (Phase 2 - Not Yet Implemented)

```bash
curl -X POST "http://localhost:8000/api/v1/conversations/{conversation_id}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the main topics discussed in this video?",
    "stream": false
  }'
```

## Configuration

### LLM Provider

Edit `.env` to configure your LLM provider:

#### Ollama (Local, Default)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

Make sure Ollama is running:
```bash
ollama serve
ollama pull llama2
```

#### OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

#### Anthropic
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

### Embedding Provider

#### Local (Default, Free)
```env
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

#### OpenAI
```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Chunking Configuration

Adjust chunking parameters in `.env`:
```env
CHUNK_TARGET_TOKENS=512
CHUNK_MIN_TOKENS=256
CHUNK_MAX_TOKENS=800
CHUNK_OVERLAP_TOKENS=80
CHUNK_MAX_DURATION_SECONDS=90
```

### Contextual Enrichment

Enable/disable contextual enrichment:
```env
ENABLE_CONTEXTUAL_ENRICHMENT=true  # or false
ENRICHMENT_BATCH_SIZE=10
ENRICHMENT_MAX_RETRIES=3
```

## Monitoring

### View Logs

Docker:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f worker
```

Manual:
- Check FastAPI console output
- Check Celery worker console output

### Access Qdrant Dashboard

Open in browser:
```
http://localhost:6333/dashboard
```

### PostgreSQL Admin

Use your preferred PostgreSQL client:
- Host: localhost
- Port: 5432
- Database: rag_transcript
- User: postgres
- Password: postgres

## Troubleshooting

### Port Already in Use

Change ports in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Change 8001 to any available port
```

### Database Connection Error

Ensure PostgreSQL is running:
```bash
docker-compose ps postgres
```

Reset database:
```bash
docker-compose down -v
docker-compose up -d postgres
docker-compose exec app alembic upgrade head
```

### Celery Worker Not Processing

Check worker logs:
```bash
docker-compose logs -f worker
```

Restart worker:
```bash
docker-compose restart worker
```

### Out of Memory

Reduce Celery concurrency in `docker-compose.yml`:
```yaml
command: celery -A app.core.celery_app worker --loglevel=info --concurrency=1
```

### Whisper Model Download Issues

Whisper models are downloaded on first use. Ensure internet connection and sufficient disk space (~1GB for base model).

Pre-download models:
```python
import whisper
whisper.load_model("base")
```

## Development

### Run Tests

```bash
cd backend
pytest
```

### Format Code

```bash
black app/
ruff check app/ --fix
```

### Create Migration

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt
```

## Production Deployment

For production:
1. Use proper environment variables (secrets management)
2. Enable HTTPS (reverse proxy with nginx)
3. Use managed PostgreSQL (AWS RDS, Azure Database)
4. Use managed Redis (AWS ElastiCache, Azure Cache)
5. Deploy Qdrant on dedicated server or Qdrant Cloud
6. Use Azure Blob Storage instead of local storage
7. Set up monitoring (Prometheus, Grafana, Sentry)
8. Configure rate limiting
9. Enable authentication (JWT)

## Next Steps

After setup:
1. Ingest a few test videos
2. Wait for processing to complete
3. Explore the API docs at http://localhost:8000/docs
4. Phase 2: Implement RAG chat functionality
5. Phase 3: Build the frontend UI
