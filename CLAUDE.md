# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG Transcript is a production-grade RAG system for YouTube videos. It downloads YouTube videos, transcribes them with Whisper, creates semantic chunks with contextual enrichment, and enables AI-powered chat with citations.

## Quick Start

```bash
# Start all services (7 containers: postgres, redis, qdrant, app, worker, beat, frontend)
docker compose up -d

# Verify Ollama is running (required for default LLM - auto-starts on boot)
curl http://localhost:11434/api/tags

# Access the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**Note:** Ollama must be running for the default LLM model (`qwen3-vl:235b-instruct-cloud`). It's configured to auto-start via launchd on macOS. If not running, start with `ollama serve`.

## Development Commands

### Docker-based (recommended)
```bash
# Start all services
docker compose up -d

# Run migrations
docker-compose exec app alembic upgrade head

# View logs
docker-compose logs -f app worker

# Run tests
docker-compose exec app pytest

# Create migration
docker-compose exec app alembic revision -m "description" --autogenerate

# Format code
docker-compose exec app black . && ruff .
```

### Local development
```bash
# Backend
cd backend && uvicorn app.main:app --reload

# Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Celery beat
celery -A app.core.celery_app beat --loglevel=info

# Tests (single file or unit only)
PYTHONPATH=backend pytest backend/tests/unit
pytest backend/tests/unit/test_chunking.py -v

# Frontend
cd frontend && npm run dev
npm run build
npm run lint
npm run type-check
```

## Architecture

### Backend Structure (`backend/app/`)
- **`main.py`**: FastAPI entrypoint
- **`api/routes/`**: HTTP endpoints (thin handlers delegating to services)
- **`services/`**: Domain logic (chunking, embeddings, enrichment, LLM, vector store, transcription, youtube, storage)
- **`models/`**: SQLAlchemy ORM models
- **`schemas/`**: Pydantic request/response schemas
- **`tasks/`**: Celery background tasks (call same service functions as API)
- **`core/`**: Config, auth, Celery app setup

### Frontend Structure (`frontend/src/`)
- Next.js 14 App Router with Shadcn UI components
- **`app/`**: Page routes (videos, collections, conversations, admin)
- **`components/`**: Reusable UI components
- State management: Zustand + React Query
- Auth: Clerk

### Key Services
| Service | Purpose |
|---------|---------|
| `chunking.py` | Semantic text chunking (512 token target, 80 overlap) |
| `enrichment.py` | LLM-generated summaries, titles, keywords per chunk |
| `embeddings.py` | Vector embeddings (local sentence-transformers, OpenAI, or Azure) |
| `llm_providers.py` | LLM abstraction (Ollama/OpenAI/Anthropic) with streaming |
| `vector_store.py` | Qdrant integration for similarity search |
| `transcription.py` | Whisper STT with timestamps |
| `youtube.py` | yt-dlp video download and metadata extraction |

### Processing Pipeline
```
YouTube URL → download_audio → transcribe (Whisper) → chunk (semantic)
→ enrich (LLM) → embed (vectors) → index (Qdrant) → ready for RAG
```

Video status flow: `pending → downloading → transcribing → chunking → enriching → indexing → completed`

### Database (PostgreSQL + pgvector)
Core tables: `users`, `videos`, `transcripts`, `chunks`, `conversations`, `messages`, `conversation_sources`, `collections`, `jobs`, `usage_events`

Migrations in `backend/alembic/versions/` - keep filenames ordered (e.g., `003_describe_change.py`).

### Infrastructure (Docker Compose)
- `postgres`: pgvector/pgvector:pg15 (port 5432)
- `redis`: Redis 7 for Celery broker (port 6379)
- `qdrant`: Vector database (ports 6333 HTTP, 6334 gRPC)
- `app`: FastAPI server (port 8000)
- `worker`: Celery worker for background tasks
- `beat`: Celery beat for scheduled tasks
- `frontend`: Next.js dev server (port 3000)

### External Dependencies
- **Ollama**: Required for default LLM. Runs on host machine (port 11434), accessed via `host.docker.internal` from Docker. Auto-starts via launchd (`~/Library/LaunchAgents/com.ollama.server.plist`).

## Code Style

- Python 3.11, 4-space indent, type hints preferred
- Run `black .` and `ruff .` before commits
- snake_case for functions/variables, PascalCase for classes
- Keep API responses typed via Pydantic schemas
- Frontend: Use existing Shadcn primitives, follow App Router conventions
