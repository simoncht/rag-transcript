# RAG Transcript System

A production-grade web-based RAG (Retrieval-Augmented Generation) system for YouTube videos, featuring semantic chunking, contextual enrichment, and intelligent chat capabilities.

## 🎯 Overview

This system allows users to:
- Ingest YouTube videos and extract audio transcripts
- Process transcripts using Whisper (open-source speech-to-text)
- Chunk and embed transcripts with contextual enrichment
- Chat with an AI agent about video content with citations
- Persist conversation history across sessions

## 🏗️ Architecture

### Tech Stack

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Vector Store**: Qdrant
- **Task Queue**: Celery + Redis
- **Speech-to-Text**: OpenAI Whisper
- **Embeddings**: sentence-transformers (local) or OpenAI API
- **LLMs**: Ollama (local), OpenAI, or Anthropic
- **Storage**: Local filesystem (dev) → Azure Blob Storage (production)
- **Frontend**: React/Next.js (to be implemented)

### Core Components

#### 1. **Semantic Chunking Engine** (`app/services/chunking.py`)
Production-grade chunking following RAG best practices:
- Token-aware boundaries (target: 512, min: 256, max: 800 tokens)
- Configurable overlap (80 tokens) for context continuity
- Sentence and speaker boundary detection
- YouTube chapter awareness
- Duration limits (max 90 seconds per chunk)
- Uses tiktoken (cl100k_base) for accurate token counting

#### 2. **Contextual Enrichment** (`app/services/enrichment.py`)
Anthropic-style contextual retrieval:
- Generates chunk summaries (1-3 sentences)
- Creates descriptive titles (3-7 words)
- Extracts keywords/entities
- Combines enrichment with original text for embedding
- Graceful degradation with fallback heuristics
- Batch processing with retry logic

#### 3. **Embedding Service** (`app/services/embeddings.py`)
Multi-backend embedding generation:
- Local: sentence-transformers (all-MiniLM-L6-v2, 384 dims)
- OpenAI: text-embedding-3-small (1536 dims)
- Azure OpenAI: Custom deployments
- Batch processing (32 chunks at a time)
- L2 normalization for cosine similarity
- LRU caching for repeated texts

#### 4. **LLM Provider Abstraction** (`app/services/llm_providers.py`)
Unified interface for multiple LLM backends:
- **Ollama**: Local LLMs (Llama2, Mistral, etc.)
- **OpenAI**: GPT models
- **Anthropic**: Claude models
- **Azure OpenAI**: Enterprise deployments
- Streaming support for real-time responses
- Automatic retry with exponential backoff
- Token usage tracking

#### 5. **Vector Store** (`app/services/vector_store.py`)
Qdrant integration for similarity search:
- Cosine similarity for relevance scoring
- Rich filtering (user_id, video_ids, chapter, timestamps)
- Metadata storage (title, summary, keywords, timestamps)
- Batch indexing
- Efficient deletion by video_id

#### 6. **Transcription Service** (`app/services/transcription.py`)
Whisper-based speech-to-text:
- Multi-model support (tiny, base, small, medium, large)
- CPU and CUDA device support
- Segment-level timestamps
- Language auto-detection
- Progress tracking callbacks

#### 7. **YouTube Downloader** (`app/services/youtube.py`)
yt-dlp integration:
- Audio extraction (best quality, MP3 conversion)
- Metadata extraction (title, description, channel, chapters)
- Validation (duration, file size limits)
- Progress tracking

#### 8. **Storage Service** (`app/services/storage.py`)
Abstraction for local and cloud storage:
- Local filesystem (development)
- Azure Blob Storage interface (production-ready)
- Per-user isolation
- Usage tracking (MB)

## 📊 Database Schema

### Core Models

#### `users`
- User accounts and subscription info
- Stripe customer ID for billing
- Subscription tier (free, pro, enterprise)

#### `videos`
- YouTube video metadata (title, description, channel, etc.)
- Processing status (pending → downloading → transcribing → chunking → enriching → indexing → completed)
- Progress tracking (percentage)
- Storage paths (audio, transcript)
- Chapter information (if available)

#### `transcripts`
- Full transcript text
- Whisper segments with timestamps
- Language detection
- Speaker count (if diarization available)

#### `chunks`
- Semantically meaningful transcript units
- Token count and timestamps
- Contextual enrichment (summary, title, keywords)
- Embedding text for vector search
- Speaker and chapter associations

#### `conversations`
- Chat sessions
- Selected video IDs (scope)
- Message count and token usage

#### `messages`
- User and assistant messages
- Token usage tracking
- LLM metadata (provider, model, response time)
- Citations to source chunks

#### `message_chunk_references`
- Many-to-many: messages ↔ chunks
- Relevance scores
- Citation tracking

#### `usage_events`
- Billable actions (video ingested, transcribed, chat messages)
- Cost estimation
- Quota tracking

#### `user_quotas`
- Monthly limits (videos, minutes, messages, storage)
- Usage tracking per quota period

#### `jobs`
- Background task tracking
- Progress and status
- Error handling and retry logic

## 🔄 Processing Pipeline

### Video Ingestion Flow

```
1. User submits YouTube URL
   ↓
2. Extract video metadata (yt-dlp)
   ↓
3. Download audio (MP3, 192kbps)
   ↓
4. Store in local storage / Azure Blob
   ↓
5. Transcribe with Whisper
   ↓
6. Chunk transcript (semantic boundaries)
   ↓
7. Enrich chunks (LLM: summary, title, keywords)
   ↓
8. Generate embeddings (batch)
   ↓
9. Index in Qdrant vector store
   ↓
10. Mark video as completed
```

### Chat RAG Flow (to be implemented)

```
1. User sends message with selected videos
   ↓
2. Embed user query
   ↓
3. Search Qdrant (filter by user_id + video_ids)
   ↓
4. Retrieve top-k chunks (default: 10)
   ↓
5. Optional: Re-rank chunks (cross-encoder or LLM)
   ↓
6. Build prompt with:
   - System message (grounded response instructions)
   - Retrieved chunks (with video title, timestamps)
   - Conversation history (token budget managed)
   ↓
7. Generate LLM response (stream if enabled)
   ↓
8. Parse citations
   ↓
9. Save message + chunk references
   ↓
10. Track usage (tokens, chunks retrieved)
```

## 🎛️ Configuration

Key settings in `.env`:

### Chunking
```env
CHUNK_TARGET_TOKENS=512
CHUNK_MIN_TOKENS=256
CHUNK_MAX_TOKENS=800
CHUNK_OVERLAP_TOKENS=80
CHUNK_MAX_DURATION_SECONDS=90
```

### Contextual Enrichment
```env
ENABLE_CONTEXTUAL_ENRICHMENT=True
ENRICHMENT_BATCH_SIZE=10
ENRICHMENT_MAX_RETRIES=3
```

### Embeddings
```env
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
EMBEDDING_BATCH_SIZE=32
EMBEDDING_PROVIDER=local  # local, openai, azure
```

### LLM
```env
LLM_PROVIDER=ollama  # ollama, openai, anthropic
LLM_MODEL=llama2
LLM_MAX_TOKENS=1500
LLM_TEMPERATURE=0.7
```

### RAG
```env
RETRIEVAL_TOP_K=10
RERANKING_TOP_K=5
ENABLE_RERANKING=False
CONVERSATION_HISTORY_TOKEN_LIMIT=2000
```

## 🚀 Next Steps

### Phase 1 Remaining (Backend Core)
- [ ] Set up Celery worker and task definitions
- [ ] Create API endpoints (videos, jobs, health)
- [ ] Implement FastAPI main app
- [ ] Create Alembic migrations

### Phase 2 (RAG Chat)
- [ ] Implement RAG chat endpoint with streaming
- [ ] Conversation management endpoints
- [ ] Citation parsing and tracking
- [ ] Token budget management

### Phase 3 (Usage Tracking)
- [ ] UsageTracker service implementation
- [ ] Quota enforcement before operations
- [ ] Usage event logging
- [ ] Quota reset scheduled task

### Phase 4 (Infrastructure)
- [ ] Docker Compose setup (postgres, redis, qdrant)
- [ ] FastAPI app containerization
- [ ] Celery worker container
- [ ] Development environment setup script

### Phase 5 (Frontend)
- [ ] Next.js project setup
- [ ] Video management UI
- [ ] ChatGPT-style chat interface
- [ ] Real-time processing updates (WebSocket/SSE)
- [ ] Citation display with YouTube links

### Phase 6 (SaaS Features - Future)
- [ ] Authentication (JWT + OAuth)
- [ ] Multi-user data isolation
- [ ] Admin dashboard
- [ ] Stripe billing integration
- [ ] Subscription management

## 📚 API Design (Preview)

### Videos
- `POST /api/v1/videos/ingest` - Ingest YouTube video
- `GET /api/v1/videos` - List user's videos
- `GET /api/v1/videos/{id}` - Get video details
- `DELETE /api/v1/videos/{id}` - Delete video

### Jobs
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/stream/jobs/{job_id}` - SSE stream for real-time updates

### Chat
- `POST /api/v1/conversations` - Create new conversation
- `GET /api/v1/conversations` - List conversations
- `GET /api/v1/conversations/{id}` - Get conversation details
- `POST /api/v1/conversations/{id}/messages` - Send message (with streaming)
- `PATCH /api/v1/conversations/{id}` - Update conversation (add/remove videos)

### Transcripts
- `GET /api/v1/videos/{id}/transcript` - Get full transcript
- `GET /api/v1/videos/{id}/chunks` - Get all chunks

## 🧪 Testing Strategy

### Unit Tests
- Chunking edge cases (very short/long transcripts, no punctuation)
- Enrichment fallback logic
- Token counting accuracy
- Embedding normalization

### Integration Tests
- End-to-end video processing pipeline
- RAG retrieval with multiple videos
- Quota enforcement
- Storage service operations

### Performance Tests
- Large video processing (4 hours)
- Concurrent video ingestion
- High-volume chat queries
- Vector search latency

## 📖 Development Status

### ✅ Completed
- Project structure and configuration
- Database models (all tables)
- Storage service abstraction (local + Azure interface)
- YouTube downloader with metadata extraction
- Semantic chunking engine (production-grade)
- Contextual enrichment service (Anthropic-style)
- Embedding service (multi-backend)
- LLM provider abstraction (Ollama, OpenAI, Anthropic)
- Qdrant vector store integration
- Whisper transcription service

### 🚧 In Progress
- Celery task definitions
- API endpoints
- FastAPI main application

### 📋 Planned
- Docker Compose setup
- Frontend implementation
- Usage tracking and billing
- Testing suite
- Documentation

## 🛠️ Installation (Preview)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Set up environment variables
cp backend/.env.example backend/.env
# Edit .env with your configuration

# Run database migrations
cd backend
alembic upgrade head

# Start services (Docker Compose - to be implemented)
docker-compose up -d

# Run FastAPI dev server
uvicorn app.main:app --reload

# Start Celery worker (separate terminal)
celery -A app.celery_app worker --loglevel=info
```

## 📝 License

TBD

## 🤝 Contributing

TBD
