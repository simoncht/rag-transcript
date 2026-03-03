# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG Transcript is a production-grade RAG system for YouTube videos. It downloads YouTube videos, transcribes them with Whisper, creates semantic chunks with contextual enrichment, and enables AI-powered chat with citations.

## Quick Start

```bash
# Start all services (7 containers: postgres, redis, qdrant, app, worker, beat, frontend)
docker compose up -d

# Verify DeepSeek API connectivity
curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"

# Access the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**Note:** DeepSeek API is required for LLM functionality. Set `DEEPSEEK_API_KEY` in your `.env` file.

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
- State management: React Query + React Context
- Auth: NextAuth.js
  - Dev middleware treats `/videos`, `/collections`, `/conversations`, `/admin` as public in local mode; pages show sign-in CTAs when unauthenticated.

### Key Services
| Service | Purpose |
|---------|---------|
| `chunking.py` | Semantic text chunking (256 token target, 80 overlap) |
| `enrichment.py` | LLM-generated summaries, titles, keywords per chunk |
| `embeddings.py` | Vector embeddings (local sentence-transformers, OpenAI, or Azure) |
| `llm_providers.py` | LLM abstraction (DeepSeek/OpenAI/Anthropic) with streaming |
| `vector_store.py` | Qdrant integration for similarity search + MMR diversity |
| `two_level_retriever.py` | Intent-based retrieval: routes to summaries (COVERAGE) or chunks (SPECIFIC) |
| `intent_classifier.py` | Classifies queries as COVERAGE, SPECIFIC, or HYBRID via regex |
| `query_expansion.py` | Multi-query retrieval - generates 2-3 query variants for better recall |
| `query_rewriter.py` | Rewrites follow-up questions using conversation history |
| `reranker.py` | Cross-encoder reranking (`bge-reranker-base`, 110M params) |
| `relevance_grader.py` | Self-RAG: LLM grades chunk relevance, triggers REFORMULATE/EXPAND actions |
| `hyde.py` | Hypothetical Document Embeddings for abstract/coverage queries |
| `bm25_search.py` | BM25 sparse search for hybrid retrieval |
| `video_summarizer.py` | Generates video-level summaries for two-level retrieval |
| `transcription.py` | Whisper STT with timestamps |
| `youtube.py` | yt-dlp video download and metadata extraction |
| `fact_extraction.py` | Conversation memory - extracts facts after 15+ message turns |
| `memory_consolidation.py` | Deduplicates and consolidates conversation facts |
| `followup_questions.py` | Generates follow-up question suggestions after responses |
| `insights.py` | Generates conversation summaries and key points |
| `theme_service.py` | Extracts and clusters themes from video collections |
| `discovery_service.py` | Content discovery and recommendation engine |
| `rate_limit.py` | Shared SlowAPI limiter to avoid circular imports across routers |
| `job_cancellation.py` | Cancel video processing - revoke Celery tasks, cleanup partial data |
| `storage_calculator.py` | Comprehensive storage calculation (disk + database + vectors) for billing |

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

### Scheduled Tasks (Celery Beat)
| Task | Schedule | Purpose |
|------|----------|---------|
| `cleanup_stale_videos` | Hourly (:00) | Cancels videos stuck in pending/downloading >24h |
| `cleanup_orphaned_files` | Every 6h (:30) | Removes orphan audio/transcript files without DB records |
| `reconcile_storage_quotas` | Daily (3:15 AM) | Fixes quota drift by recalculating actual storage |
| `consolidate_conversation_memory` | Daily (4:45 AM) | Deduplicates and consolidates conversation facts |
| `check_heavy_users` | Every 6h (:45) | Monitors high-usage users for quota enforcement |
| `backfill_video_summaries` | Daily (4:00 AM) | Generates missing video summaries for two-level retrieval |
| `check_discovery_sources` | Hourly (:15) | Checks discovery sources for new content |
| `cleanup_expired_discoveries` | Daily (5:00 AM) | Removes expired discovery items |
| `generate_recommendations` | Mondays (8:00 AM) | Generates weekly content recommendations |
| `send_notification_digests` (daily) | Daily (9:00 AM) | Sends daily email digests |
| `send_notification_digests` (weekly) | Mondays (9:30 AM) | Sends weekly email digests |

Configured in `backend/app/core/celery_app.py` beat_schedule.

### Storage Billing Architecture

**Comprehensive storage calculation** (used for quota enforcement and billing):
- **Disk files**: Audio + transcript files (via `storage_service.get_storage_usage()`)
- **Database text**: Chunks, messages, facts, insights (via `StorageCalculator.calculate_database_storage_mb()`)
- **Vectors**: Estimated from indexed chunk count × 5KB (via `StorageCalculator.calculate_vector_storage_mb()`)

**Single source of truth for tier limits**: `PRICING_TIERS` in `backend/app/core/pricing.py`
- Free: 1 GB storage
- Pro: 50 GB storage
- Enterprise: Unlimited (-1)

**Quota tracking**: `usage_tracker.track_storage_usage()` credits/debits storage deltas.
Cleanup operations automatically credit freed storage back to user quota.

### RAG Pipeline Architecture

**Query Processing (in conversations.py send_message endpoint):**
```
1. Query Expansion: Generate 2-3 semantic variants (0.8s)
2. Diversity-Aware Search: MMR-based retrieval balances relevance + video diversity
3. Multi-Query Merge: Combine results from variants, keep highest scores
4. Reranking: Cross-encoder reranks top candidates (if enabled)
5. Relevance Filtering: Apply score thresholds (0.50 primary, 0.15 fallback)
6. Deduplication: Remove nearby chunks from same video (30s buckets)
7. Context Building: Assemble top chunks with metadata (adaptive limit)
8. Conversation Memory: Load facts for conversations with 15+ messages
9. LLM Generation: Stream response with citations
```

**Performance:** ~4s total (1s query expansion, 0.5s retrieval, 2.5s LLM)

**Diversity-Aware Retrieval (MMR):**
- Ensures multi-video queries return chunks from multiple videos, not just the most similar
- Adaptive diversity factor: 0.3-0.5 for single video, 0.5-0.7 for multi-video collections
- Adaptive chunk limit: 4-12 based on video count and mode (summarize gets more)
- Implementation: `vector_store.py:search_with_diversity()` uses client-side MMR
- Helper functions: `_get_diversity_factor()`, `_get_chunk_limit()` in conversations.py

**Configuration:**
- `ENABLE_QUERY_EXPANSION=True` - Multi-query retrieval for better recall
- `ENABLE_RERANKING=True` - Cross-encoder for precision
- `ENABLE_RELEVANCE_GRADING=True` - Self-RAG: LLM grades chunk relevance
- `ENABLE_HYDE=True` - HyDE: hypothetical document embeddings for coverage queries
- `ENABLE_QUERY_REWRITING=True` - Rewrites follow-up questions using conversation history
- `ENABLE_BM25_SEARCH=True` - BM25 hybrid search
- `RETRIEVAL_TOP_K=20` - Candidates per query variant
- `RERANKING_TOP_K=7` - Final chunks after reranking

### Database (PostgreSQL + pgvector)

**Core tables:** `users`, `videos`, `transcripts`, `chunks`, `conversations`, `messages`, `conversation_sources`, `collections`, `jobs`, `usage_events`, `conversation_facts`

**Key relationships:**
- `conversation_sources` links conversations to videos with `is_selected` flag for filtering
- `message_chunk_references` tracks citations with relevance scores
- `conversation_facts` stores extracted facts for conversation memory

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
- **DeepSeek API**: Required for LLM functionality. Set `DEEPSEEK_API_KEY` in `.env`. Pricing: $0.28/M input, $0.42/M output, with automatic context caching at $0.028/M for cache hits.

## Important Implementation Details

### Citation System
- Citations include metadata: channel name, chapter title, speakers (when available)
- Citation badges are inline with expandable details
- Jump URLs navigate to exact YouTube timestamp
- Located in `frontend/src/components/shared/CitationBadge.tsx`

### Conversation Memory
- After 15+ messages, system extracts facts using LLM
- Facts stored in `conversation_facts` table with confidence scores
- Facts injected into system prompt for context continuity
- Consolidation task deduplicates facts daily
- Service: `backend/app/services/fact_extraction.py`

### Two-Level Hierarchical Retrieval
For large collections, chunk-level retrieval alone has coverage limitations. The system uses intent-based routing:
- **COVERAGE queries** ("summarize", "what topics"): Routes to video summaries first, falls back to chunks
- **SPECIFIC queries** ("what did X say about Y"): Routes directly to chunk retrieval
- **HYBRID queries**: Retrieves both summaries and chunks
- Video summaries stored in `videos.summary` and `videos.key_topics` columns
- Backfill task generates missing summaries daily (4:00 AM)
- Service: `backend/app/services/two_level_retriever.py`

### Admin Console & Auth Elevation
- Admin API: `backend/app/api/routes/admin.py` (dashboard stats, user list/search/filter, user detail, subscription/status updates, quota overrides). Protected by `get_admin_user` requiring `is_superuser=True`.
- Frontend: Next.js pages under `/admin` (dashboard, users, user detail) with backend `/auth/me` check; unauth pages show CTAs in dev.
- Elevation rules: backend auto-promotes on login if email is in `ADMIN_EMAILS`; otherwise `is_superuser` must already be true in `users`.
- Admin monitoring additions: `/api/v1/admin/qa-feed` surfaces questions/answers with sources/latency/tokens/cost; `/admin/conversations` list/detail for timeline review; `/admin/content/overview` shows ingestion/collection health. Frontend tabs under `/admin` consume these read-only endpoints.

### Query Expansion (Recently Added)
- Improves retrieval recall by 20-30%
- Generates 2-3 query variants using LLM (low temp 0.3)
- Max-score fusion merges results from multiple queries
- Adds ~1s latency but significantly improves answer quality
- Gracefully falls back to single query if LLM unavailable

### Tier-Based Model Selection (DeepSeek API)
Different subscription tiers use different DeepSeek models:

| Tier | Model | Context | Max Output | Best For |
|------|-------|---------|------------|----------|
| Free | `deepseek-chat` | 128K | 8K | Fast responses, simple queries |
| Pro | `deepseek-reasoner` | 128K | 64K | Complex reasoning, detailed analysis |
| Enterprise | `deepseek-reasoner` | 128K | 64K | Same as Pro with SLA |

**Pricing**: $0.28/M input, $0.42/M output. **Cache hits**: $0.028/M (10x cheaper for repeated prefixes).

**Key feature:** `deepseek-reasoner` provides chain-of-thought reasoning for complex queries. The `reasoning_content` is extracted for logging but NOT included in message history (would cause 400 errors).

**Configuration:**
- Tier models defined in `backend/app/core/pricing.py` (`MODEL_TIERS`)
- Environment overrides: `LLM_MODEL_FREE`, `LLM_MODEL_PRO`, `LLM_MODEL_ENTERPRISE`
- Model resolution: `backend/app/core/pricing.py:resolve_model()`
- Admins can override model selection (via `is_superuser` flag)
- See `docs/MODEL_RESEARCH.md` for full analysis

### Monitoring & Observability
- Comprehensive logging throughout RAG pipeline
- Log categories: `[Query Expansion]`, `[Vector Search]`, `[Reranking]`, `[Context Building]`, `[RAG Pipeline Complete]`, `[DeepSeek Cache]`, `[DeepSeek Reasoner]`
- View logs: `docker compose logs -f app | grep "\[RAG Pipeline\]"`
- DeepSeek cache metrics logged: `[DeepSeek Cache] Hit: X tokens (Y%), Miss: Z tokens`
- Final summary includes timing breakdown and chunk flow stats
- Rate limiting uses SlowAPI with a shared limiter (`core/rate_limit.py`); each rate-limited route must accept a `request` param.

## Code Style

- Python 3.11, 4-space indent, type hints preferred
- Run `black .` and `ruff .` before commits
- snake_case for functions/variables, PascalCase for classes
- Keep API responses typed via Pydantic schemas
- Frontend: Use existing Shadcn primitives, follow App Router conventions

## Behavioral Contracts

Before editing memory, citations, or fact extraction behavior, read `.claude/references/behavioral-contracts.md` to check which promises exist and their current status (PASS/BROKEN/FIXED).

## Key Configuration Files

- `.env` - Environment variables (LLM provider, RAG settings, API keys)
- `backend/.env.example` - Includes `ADMIN_EMAILS` allowlist
- `docker-compose.yml` - Service orchestration
- `backend/alembic.ini` - Database migration config
- `backend/requirements.txt` - Python dependencies
- `frontend/package.json` - Node.js dependencies
- `docs/MODEL_RESEARCH.md` - LLM model research and tier selection rationale

## Future Enhancements (Planned)

### RAPTOR (When Multi-Content Support Added)
RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval) builds full hierarchical trees.
**When to consider:** When expanding to support PDFs, Word docs, and mixed content collections.
- More valuable for documents with complex nested structure
- Enables cross-document theme discovery
- Higher indexing cost (~$0.008/video vs ~$0.001 for two-level)

**Multi-content architecture vision:**
```
Collection
├── Videos (transcripts)
├── PDFs (extracted text + structure)
└── Word docs (extracted text)
    ↓
Unified chunks → Hierarchical summaries → Cross-content retrieval
```

### Current Limitations
- Single content type (videos) supported; PDF/document support planned
- Embedding model (`all-MiniLM-L6-v2`, 384 dims) is outdated; BGE upgrade code-ready but not deployed
