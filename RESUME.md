# Quick Resume

**Last Updated**: 2025-12-03 18:30 PST
**Status**: 🚧 Phase 3.1 IN PROGRESS | Collections backend complete, frontend partial

## System Check

```bash
docker-compose ps              # All 6 running (postgres, redis, qdrant, app, worker [solo], beat)
curl http://localhost:8000/health  # {"status":"healthy"}
```

## ✅ Phase 3 Complete - Frontend Fully Functional

Full Next.js frontend with:
- ✅ Video management UI (YouTube ingestion, status tracking)
- ✅ Conversation creation with video selection
- ✅ Real-time chat interface with message history
- ✅ Citation display with timestamps and relevance scores
- ✅ Mock authentication (placeholder for Phase 4)
- ✅ Responsive design with Tailwind CSS
- ✅ Type-safe API integration with TypeScript

## ✅ Phase 2 Complete - RAG Chat Backend

Backend RAG chat implementation:
- ✅ LLM integration (Ollama with Qwen3-Coder)
- ✅ Query embedding and vector search
- ✅ Context retrieval from video transcripts
- ✅ Conversation history management
- ✅ Citation tracking with timestamps
- ✅ Multi-provider support (Ollama/OpenAI/Anthropic)

```bash
# Test RAG search (vector store)
docker-compose exec app python test_rag.py

# Ingest video
curl -X POST http://localhost:8000/api/v1/videos/ingest \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "YOUTUBE_URL"}'

# Create conversation
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "My Chat", "selected_video_ids": ["VIDEO_ID"]}'

# Send chat message (RAG chat)
curl -X POST http://localhost:8000/api/v1/conversations/CONVERSATION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this about?", "stream": false}'
```

## Common Commands

```bash
docker-compose ps                  # Check status
docker-compose logs -f app worker  # View logs
docker-compose restart {service}   # Restart service
docker-compose up -d               # Start all
docker-compose down                # Stop all
```

## Technical Notes

- **SSL Bypass**: `backend/app/core/ssl_patch.py` (corporate environment)
- **Models**:
  - Whisper (base) for transcription
  - sentence-transformers (all-MiniLM-L6-v2, 384-dim) for embeddings
  - Qwen3-Coder (480B cloud) via Ollama for chat
- **Model Cache**: `/hf_cache` volume (shared across app/worker/beat)
- **Offline Mode**: `HF_HUB_OFFLINE=1` prevents network calls to HuggingFace
- **Ollama**: `host.docker.internal:11434` for Docker to Windows host access
- **Worker**: running `--pool=solo --concurrency=1` for Whisper stability
- **Chunking**: lowered thresholds for short clips (min_tokens=16, target=256) with single-chunk fallback

## Frontend Development (Phase 3)

```bash
# Start frontend development server
cd frontend
npm install
npm run dev
# Visit http://localhost:3000
```

**Features:**
- Video management page at `/videos`
- Conversations list at `/conversations`
- Chat interface at `/conversations/[id]`
- Mock login at `/login` (accepts any email)

**Tech Stack:**
- Next.js 14 with App Router
- TypeScript
- Tailwind CSS
- TanStack Query for data fetching
- Zustand for state management
- React Markdown for chat rendering

## 🚧 Phase 3.1: Video Collections (In Progress)

**See `PHASE_3_ENHANCEMENTS.md` for full specification**

### ✅ Completed:
**Backend (100%)**
- ✅ Database migration (collections, collection_videos, collection_members tables)
- ✅ SQLAlchemy models (Collection, CollectionVideo, CollectionMember)
- ✅ API endpoints (7 endpoints: CRUD collections, add/remove videos)
- ✅ Tags support for videos
- ✅ Conversation creation from collections
- ✅ Auto-created "Uncategorized" default collection

**Frontend API Layer (100%)**
- ✅ TypeScript types for collections
- ✅ Collections API client functions
- ✅ Videos API updateTags function

**Frontend UI (60%)**
- ✅ Collections list page (`/collections`)
- ✅ Create/Edit collection modal with metadata
- ✅ Navigation updated with Collections link
- ⏳ Videos page integration (add to collection, show collections)
- ⏳ Conversation creation from collections

### 🎯 Remaining Work:
1. Update Videos page to show which collections each video belongs to
2. Add "Add to Collection" functionality on Videos page
3. Update Conversation creation to support selecting from collections
4. End-to-end testing

### Key Features:
- **Collections/Playlists** - Organize videos by course, instructor, subject
- **Metadata & Tags** - Instructor, subject, semester, custom tags
- **Many-to-Many** - Videos can belong to multiple collections
- **Default Collection** - Auto-created "Uncategorized" for new videos
- **Flexible Chat** - Create conversations from entire collection or individual videos

## Phase 4: Next Steps (Production Ready)

1. **Collection Sharing**
   - Owner/Editor/Viewer roles
   - Invite links and permissions
2. **Real Authentication**
   - JWT token authentication (backend + frontend)
   - OAuth integration (Google, GitHub)
   - Secure session management
3. **Stripe billing integration**
   - Storage quota tracking
   - Subscription tiers
4. **Production deployment**
5. **Monitoring & observability**
6. **Horizontal scaling**
7. **Streaming chat responses** (optional enhancement)

## Key Files

**Documentation:**
- `PROGRESS.md` - Detailed history
- `RESUME.md` - Quick reference (this file)
- `PHASE_3_ENHANCEMENTS.md` - Video collections feature spec
- `README.md` - Architecture overview

**Backend:**
- `docker-compose.yml` - Container config
- `backend/alembic/versions/003_add_collections.py` - Collections migration
- `backend/app/models/collection.py` - Collection models
- `backend/app/api/routes/collections.py` - Collections API endpoints
- `backend/app/api/routes/conversations.py` - RAG chat endpoint (with collection support)
- `backend/app/services/llm_providers.py` - Multi-provider LLM abstraction

**Frontend:**
- `frontend/README.md` - Frontend documentation
- `frontend/src/app/` - Next.js pages (videos, collections, conversations, login)
- `frontend/src/lib/api/` - API client functions (videos, collections, conversations)
- `frontend/src/lib/types/` - TypeScript type definitions
- `frontend/src/components/layout/` - Layout components
- `frontend/src/components/collections/` - Collection components (modal)
