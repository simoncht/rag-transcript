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

**Note:** Ollama must be running for the default LLM model (`qwen3-coder:480b-cloud`). It's configured to auto-start via launchd on macOS. If not running, start with `ollama serve`. Backend auth is strict: `CLERK_ISSUER` must match the live Clerk tenant (e.g., `https://wise-coral-92.clerk.accounts.dev`) or every API call will 401.

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
- **`core/`**: Config, auth, Celery app setup, shared rate limiter (`core/rate_limit.py`)

### Frontend Structure (`frontend/src/`)
- Next.js 14 App Router with Shadcn UI components
- **`app/`**: Page routes (videos, collections, conversations, admin)
- **`components/`**: Reusable UI components
- State management: Zustand + React Query
- Auth: Clerk
  - Dev middleware treats `/videos`, `/collections`, `/conversations`, `/admin` as public in local mode; pages show sign-in CTAs when unauthenticated.

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
| `query_expansion.py` | Multi-query retrieval - generates 2-3 query variants for 20-30% better recall |
| `reranker.py` | Cross-encoder reranking for improved precision |
| `fact_extraction.py` | Conversation memory - extracts facts after 15+ message turns |
| `insights.py` | Generates conversation summaries and key points |
| `rate_limit.py` | Shared SlowAPI limiter to avoid circular imports across routers |
| `job_cancellation.py` | Cancel video processing - revoke Celery tasks, cleanup partial data |

### Processing Pipeline
```
YouTube URL → download_audio → transcribe (Whisper) → chunk (semantic)
→ enrich (LLM) → embed (vectors) → index (Qdrant) → ready for RAG
```

Video status flow: `pending → downloading → transcribing → chunking → enriching → indexing → completed`
- Can transition to `canceled` from any in-progress state (user-initiated)
- Can transition to `failed` on error at any stage

### Video Cancellation & Cleanup
- **Cancel endpoint:** `POST /api/v1/videos/{video_id}/cancel` with `cleanup_option`: `keep_video` (default) or `full_delete`
- **Bulk cancel:** `POST /api/v1/videos/cancel-bulk` for multiple videos
- **Reprocess endpoint:** `POST /api/v1/videos/{video_id}/reprocess` for pending/failed/canceled videos
- **Cleanup service:** `backend/app/services/job_cancellation.py` - revokes Celery tasks, deletes partial audio/transcript files, removes chunks and vectors
- **Cancellation checkpoints:** Tasks check for canceled status between pipeline stages to stop gracefully

### Scheduled Cleanup Tasks (Celery Beat)
| Task | Schedule | Purpose |
|------|----------|---------|
| `cleanup_stale_videos` | Hourly (:00) | Cancels videos stuck in pending/downloading >24h |
| `cleanup_orphaned_files` | Every 6h (:30) | Removes orphan audio/transcript files without DB records |

Configured in `backend/app/core/celery_app.py` beat_schedule.

### RAG Pipeline Architecture

**Query Processing (in conversations.py send_message endpoint):**
```
1. Query Expansion: Generate 2-3 semantic variants (0.8s)
2. Multi-Query Search: Embed each variant → search Qdrant → merge by max score
3. Reranking: Cross-encoder reranks top candidates (if enabled)
4. Relevance Filtering: Apply score thresholds (0.50 primary, 0.15 fallback)
5. Deduplication: Remove nearby chunks from same video (30s buckets)
6. Context Building: Assemble top chunks with metadata
7. Conversation Memory: Load facts for conversations with 15+ messages
8. LLM Generation: Stream response with citations
```

**Performance:** ~4s total (1s query expansion, 0.5s retrieval, 2.5s LLM)

**Configuration:**
- `ENABLE_QUERY_EXPANSION=True` - Multi-query retrieval for better recall
- `ENABLE_RERANKING=True` - Cross-encoder for precision
- `RETRIEVAL_TOP_K=10` - Candidates per query variant
- `RERANKING_TOP_K=5` - Final chunks after reranking

### Database (PostgreSQL + pgvector)

**Core tables:** `users`, `videos`, `transcripts`, `chunks`, `conversations`, `messages`, `conversation_sources`, `collections`, `jobs`, `usage_events`, `conversation_facts`

**Key relationships:**
- `conversation_sources` links conversations to videos with `is_selected` flag for filtering
- `message_chunk_references` tracks citations with relevance scores
- `conversation_facts` stores extracted facts for memory (Phase 2 feature)

**Migrations:** Keep filenames ordered in `backend/alembic/versions/` (e.g., `006_add_conversation_insights.py`).

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

## Important Implementation Details

### Citation System (Phase 1 Complete)
- Citations include metadata: channel name, chapter title, speakers (when available)
- Citation badges are inline with expandable details
- Jump URLs navigate to exact YouTube timestamp
- Located in `frontend/src/components/shared/CitationBadge.tsx`

### Conversation Memory (Phase 2 Complete)
- After 15+ messages, system extracts facts using LLM
- Facts stored in `conversation_facts` table with confidence scores
- Facts injected into system prompt for context continuity
- Service: `backend/app/services/fact_extraction.py`

### Admin Console & Auth Elevation
- Admin API: `backend/app/api/routes/admin.py` (dashboard stats, user list/search/filter, user detail, subscription/status updates, quota overrides). Protected by `get_admin_user` requiring `is_superuser=True`.
- Frontend: Next.js pages under `/admin` (dashboard, users, user detail) with Clerk gate plus backend `/auth/me` check; unauth pages show CTAs in dev.
- Elevation rules: backend auto-promotes on login if email is in `ADMIN_EMAILS`; otherwise `is_superuser` must already be true in `users`. Clerk metadata alone is not trusted unless synced via webhook.
- Webhooks: `/api/v1/webhooks/clerk` can upsert users and set `is_superuser` when `public_metadata.is_superuser` is true or email is in `ADMIN_EMAILS` (requires `CLERK_WEBHOOK_SECRET` and Clerk webhook configuration).
- Admin monitoring additions: `/api/v1/admin/qa-feed` surfaces questions/answers with sources/latency/tokens/cost; `/admin/conversations` list/detail for timeline review; `/admin/content/overview` shows ingestion/collection health. Frontend tabs under `/admin` consume these read-only endpoints.

### Query Expansion (Recently Added)
- Improves retrieval recall by 20-30%
- Generates 2-3 query variants using LLM (low temp 0.3)
- Max-score fusion merges results from multiple queries
- Adds ~1s latency but significantly improves answer quality
- Gracefully falls back to single query if LLM unavailable

### Monitoring & Observability
- Comprehensive logging throughout RAG pipeline
- Log categories: `[Query Expansion]`, `[Vector Search]`, `[Reranking]`, `[Context Building]`, `[RAG Pipeline Complete]`
- View logs: `docker compose logs -f app | grep "\[RAG Pipeline\]"`
- Final summary includes timing breakdown and chunk flow stats
- Rate limiting uses SlowAPI with a shared limiter (`core/rate_limit.py`); each rate-limited route must accept a `request` param.

## Code Style

- Python 3.11, 4-space indent, type hints preferred
- Run `black .` and `ruff .` before commits
- snake_case for functions/variables, PascalCase for classes
- Keep API responses typed via Pydantic schemas
- Frontend: Use existing Shadcn primitives, follow App Router conventions

## Key Configuration Files

- `.env` - Environment variables (LLM provider, RAG settings, API keys)
- `backend/.env.example` - Includes `ADMIN_EMAILS` allowlist and optional `CLERK_WEBHOOK_SECRET` for Clerk user sync
- `docker-compose.yml` - Service orchestration
- `backend/alembic.ini` - Database migration config
- `backend/requirements.txt` - Python dependencies
- `frontend/package.json` - Node.js dependencies
