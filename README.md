# RAG Transcript System

Production-grade RAG system for YouTube videos with semantic chunking, contextual enrichment, and intelligent chat.

---

## 🚀 Getting Started

**New to this project?** Follow the step-by-step setup guide:

👉 **[SETUP.md](./SETUP.md)** - Complete beginner-friendly installation guide

---

## ✅ Current Status (2025-12-02)

**Phase 1 COMPLETE** - All 6 containers operational

✅ Health endpoint | Whisper loaded | Embeddings (384-dim) | DB migrations | SSL resolved

**Next**: Phase 2 functional testing

👉 **Quick Start**: [RESUME.md](./RESUME.md) | **Details**: [PROGRESS.md](./PROGRESS.md)

---

## Overview

**Features:**
- Per-conversation source control (include/exclude videos) with clickable citations that jump to the exact transcript segment.
- Ingest YouTube videos → extract audio transcripts (Whisper)
- Semantic chunking with contextual enrichment
- Chat with AI about video content with citations
- Persistent conversation history

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy, Celery
- Database: PostgreSQL (pgvector), Redis, Qdrant
- ML: Whisper (transcription), sentence-transformers (embeddings)
- LLMs: Ollama/OpenAI/Anthropic
- Storage: Local (dev) → Azure Blob (prod)

---

## Architecture

### Core Services (`backend/app/services/`)

| Service | Purpose | Key Features |
|---------|---------|--------------|
| `chunking.py` | Semantic text chunking | Token-aware (512t target), sentence boundaries, 80t overlap |
| `enrichment.py` | Contextual metadata | LLM-generated summaries, titles, keywords |
| `embeddings.py` | Vector embeddings | Multi-backend (local/OpenAI/Azure), batch processing, caching |
| `llm_providers.py` | LLM abstraction | Ollama/OpenAI/Anthropic, streaming, retry logic |
| `vector_store.py` | Qdrant integration | Cosine similarity, metadata filtering, batch indexing |
| `transcription.py` | Whisper STT | Multi-model support, timestamps, language detection |
| `youtube.py` | Video download | yt-dlp, audio extraction, metadata, chapters |
| `storage.py` | File storage | Local filesystem + Azure Blob interface |

### Database Schema (`backend/app/models/`)

**Core Tables:**
  - `users` - Accounts, subscription tiers, Stripe IDs
  - `videos` - Metadata, processing status, storage paths
  - `transcripts` - Full text, Whisper segments, timestamps
  - `chunks` - Semantic units, enrichment, embeddings
  - `conversations` - Chat sessions, selected videos, optional backing collection
  - `messages` - User/assistant messages, LLM metadata, citations
  - `message_chunk_references` - Citation tracking
  - `conversation_sources` - Per-conversation video list with `is_selected` flag used to filter retrieval
  - `usage_events` - Billable actions, quota tracking
  - `user_quotas` - Monthly limits
  - `jobs` - Background task tracking

---

## Processing Pipeline

```
YouTube URL → download_audio → transcribe (Whisper) → chunk (semantic)
→ enrich (LLM) → embed (vectors) → index (Qdrant) → ready for RAG
```

**Status Flow:**
`pending → downloading → transcribing → chunking → enriching → indexing → completed`

---

## API Endpoints

### Videos
- `POST /api/v1/videos/ingest` - Submit YouTube URL
- `GET /api/v1/videos` - List videos (paginated)
- `GET /api/v1/videos/{id}` - Video details
- `DELETE /api/v1/videos/{id}` - Soft delete

### Jobs
- `GET /api/v1/jobs/{job_id}` - Job status/progress

### Conversations
- `POST /api/v1/conversations` - Create chat
- `GET /api/v1/conversations` - List chats
- `GET /api/v1/conversations/{id}` - Chat details
- `PATCH /api/v1/conversations/{id}` - Update (add/remove videos)
- `DELETE /api/v1/conversations/{id}` - Delete
- `POST /api/v1/conversations/{id}/messages` - Send message (Phase 2)

---

## Configuration

Key settings in `.env`:

```env
# Chunking
CHUNK_TARGET_TOKENS=512
CHUNK_OVERLAP_TOKENS=80

# Embeddings
EMBEDDING_PROVIDER=local  # local, openai, azure
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# LLM
LLM_PROVIDER=ollama  # ollama, openai, anthropic
LLM_MODEL=llama2

# RAG
RETRIEVAL_TOP_K=10
ENABLE_RERANKING=False
```

---

## Development

### Setup
```bash
# Start services
docker-compose up -d

# Run migrations
docker-compose exec app alembic upgrade head

# Check health
curl http://localhost:8000/health
```

### Common Tasks
```bash
# View logs
docker-compose logs -f app worker

# Create migration
docker-compose exec app alembic revision -m "description" --autogenerate

# Run tests
docker-compose exec app pytest

# Code formatting
docker-compose exec app black . && ruff .
```

See [AGENTS.md](./AGENTS.md) for coding guidelines.

---

## Phase Roadmap

### ✅ Phase 1 (Complete)
- Docker infrastructure (6 containers)
- Video ingestion pipeline
- Transcription, chunking, enrichment
- Vector indexing
- API endpoints (videos, jobs, conversations)
- Database migrations

### 🚧 Phase 2 (Next)
- RAG chat implementation
- Streaming LLM responses
- Citation parsing
- Token budget management
- Usage tracking

### 📋 Phase 3+ (Future)
- Frontend (Next.js)
- Authentication (JWT + OAuth)
- Stripe billing
- Admin dashboard
- Production deployment

---

## Documentation

- **[SETUP.md](./SETUP.md)** - **Complete setup guide for new machines** (start here!)
- **[RESUME.md](./RESUME.md)** - Quick resume guide, commands, status
- **[PROGRESS.md](./PROGRESS.md)** - Recent changes, technical details
- **[AGENTS.md](./AGENTS.md)** - Development guidelines, conventions
- **API Docs**: http://localhost:8000/docs (Swagger UI)

---

## License

TBD
