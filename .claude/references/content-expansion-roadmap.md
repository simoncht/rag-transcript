# Content Expansion Roadmap

Reference document for the product-builder skill. Contains architecture foundations, phased roadmap, per-content-type reference cards, and design principles for expanding RAG Transcript beyond YouTube.

**Last updated:** 2026-02-06

---

## 1. Architecture Foundation

### Current Generic vs Video-Specific Map

**Already content-agnostic (reusable as-is):**
| Component | File | Evidence |
|-----------|------|----------|
| Chunking | `services/chunking.py` | Operates on `TranscriptSegment(text, start, end, speaker)` — no YouTube imports |
| Enrichment | `services/enrichment.py` | Operates on `Chunk` objects with generic `video_context` string |
| Embeddings | `services/embeddings.py` | Takes text strings, returns vectors |
| Vector Store | `services/vector_store.py` | Indexes chunks by collection, agnostic to source |
| Query Expansion | `services/query_expansion.py` | Generates query variants from user text |
| Reranking | `services/reranker.py` | Scores query-chunk pairs |
| LLM Providers | `services/llm_providers.py` | Generic LLM abstraction |
| Fact Extraction | `services/fact_extraction.py` | Extracts facts from conversation messages |

**YouTube-specific (needs generalization):**
| Component | File | What's Coupled |
|-----------|------|---------------|
| Data Model | `models/video.py` | `youtube_id`, `youtube_url`, `channel_name`, `channel_id`, `view_count`, `like_count`, `upload_date`, `chapters` columns |
| Processing Pipeline | `tasks/video_tasks.py` | `youtube_service.download_audio()`, `youtube_service.get_captions()`, hardcoded status flow |
| YouTube Service | `services/youtube.py` | yt-dlp download, caption extraction, URL parsing |
| Transcription | `services/transcription.py` | Audio file → text (reusable for podcasts, but not needed for text content) |

**Provider abstraction (partially built):**
| Component | File | Status |
|-----------|------|--------|
| Base interfaces | `providers/base.py` | Done — ContentProvider, DiscoveryProvider ABCs |
| Registry | `providers/registry.py` | Done — singleton registry with lazy init |
| YouTube provider | `providers/youtube.py` | Done — implements both interfaces |
| Pipeline integration | `tasks/video_tasks.py` | **Not done** — tasks call youtube_service directly, not through provider |

### Provider Interface Summary

```python
# ContentProvider (backend/app/providers/base.py)
class ContentProvider(ABC):
    source_type -> str              # "youtube", "reddit", "pdf"
    display_name -> str             # "YouTube", "Reddit", "PDF"
    is_configured() -> bool         # Check API keys, etc.
    search(query, max_results) -> List[SearchResult]
    get_metadata(source_id) -> ContentMetadata
    validate(source_id) -> ValidationResult

# DiscoveryProvider (backend/app/providers/base.py)
class DiscoveryProvider(ABC):
    check_for_new_content(source_type, source_id, since) -> List[DiscoveredContentData]
    get_source_info(source_type, source_id) -> SourceInfo
    get_supported_source_types() -> List[str]
```

### Generic Processing Pipeline (Target Architecture)

```
User Input (URL / file upload / API fetch)
    │
    ▼
ContentProvider.validate() + get_metadata()
    │
    ▼
Content Extraction (source-specific)
    ├── YouTube: download_audio → transcribe (Whisper)
    ├── PDF: extract text + structure (pdfplumber)
    ├── Reddit: fetch thread via API (PRAW)
    ├── Web Article: scrape + extract (trafilatura)
    ├── Podcast: download_audio → transcribe (Whisper)
    └── ... (new providers plug in here)
    │
    ▼
Normalized Text + Metadata
    │
    ▼
Chunking (services/chunking.py) ← content-agnostic
    │
    ▼
Enrichment (services/enrichment.py) ← content-agnostic
    │
    ▼
Embedding (services/embeddings.py) ← content-agnostic
    │
    ▼
Vector Indexing (services/vector_store.py) ← content-agnostic
    │
    ▼
Ready for RAG queries
```

---

## 2. Phased Content Roadmap

| Phase | Content Types | Why This Order | Prerequisites | Effort |
|-------|--------------|----------------|---------------|--------|
| **0** | **Foundation** — Generic Content model, content-agnostic task pipeline, provider-routed processing | Everything depends on this. Without it, each content type requires forking video_tasks.py | None | L (1-2 weeks) |
| **1** | **PDF, Plain Text, Markdown** | Easiest — text already exists, no API or transcription needed, high user demand for document analysis | Phase 0 + file upload infrastructure | M per type |
| **2** | **Web Articles, Reddit** | URL-based input mirrors YouTube UX pattern, broad appeal, good APIs available | Phase 0 | M per type |
| **3** | **Podcasts, Audio Files** | Reuses existing Whisper transcription pipeline almost entirely | Phase 0 | S-M per type |
| **4** | **Twitter/X, RSS Feeds** | API-heavy, rate limits, real-time monitoring aspect | Phase 0 + notification system for new content alerts | M-L per type |
| **5** | **Slack/Discord Exports, Email Archives** | File upload + specialized thread/conversation parsing | Phase 0 + Phase 1 (file upload infrastructure) | M per type |
| **6** | **GitHub Repos, Issues, PRs** | Specialized code-aware chunking, cross-reference resolution | Phase 0 + code-aware chunking strategy | L per type |

### Phase 0: Foundation Layer (Detailed)

**What it includes:**
1. **Generic Content model** — Rename/extend `Video` to `Content` with `content_type` enum, move YouTube-specific columns to JSONB `source_metadata`
2. **Generic processing task** — `content_tasks.py` that dispatches to the right provider based on `content_type`
3. **Provider pipeline integration** — Processing tasks call `provider_registry.get_content_provider()` instead of importing `youtube_service` directly
4. **File upload infrastructure** — Endpoint + storage for document types (used by Phase 1+)
5. **Citation system extension** — Make citation data polymorphic (timestamp for video, page number for PDF, permalink for Reddit)

**Backward compatibility:** Existing YouTube videos continue working. The generic Content model includes all current Video columns, and `content_type='youtube'` is the default.

---

## 3. Per-Content-Type Reference Cards

### PDF Documents

- **Input format:** File upload (.pdf)
- **Extraction library:** `pdfplumber` (recommended — best table/layout extraction), alternatives: `PyPDF2` (simpler, text-only), `pymupdf`/`fitz` (fast, good for images)
- **Text structure:** Pages with potential headers, footers, tables, multi-column layouts. OCR may be needed for scanned docs (use `pytesseract` or `pdf2image` + vision model).
- **Metadata available:** Title (from PDF metadata), author, creation date, page count, file size
- **Chunking considerations:** Page-aware chunking — include page number in chunk metadata. Respect section boundaries if detected. Tables should be kept as single chunks.
- **Citation model:** Page number + optional section heading. Link format: `page X` (no URL for uploaded files, show in-app viewer)
- **API constraints:** None (local processing). File size limit recommended: 100MB.
- **Estimated effort:** M (2-4 days backend, 1-2 days frontend for upload UI + PDF viewer)

### Plain Text / Markdown

- **Input format:** File upload (.txt, .md) or paste into text field
- **Extraction library:** None needed for plain text. For Markdown: `markdown-it-py` or `mistune` to parse structure.
- **Text structure:** Unstructured (plain text) or structured with headings (Markdown). Markdown headings make excellent chunk boundaries.
- **Metadata available:** Filename, file size, heading structure (Markdown)
- **Chunking considerations:** For Markdown, chunk at heading boundaries. For plain text, use standard semantic chunking.
- **Citation model:** Line number range or heading path (e.g., "Section 2.1 > Subsection A")
- **API constraints:** None
- **Estimated effort:** S (1-2 days — simplest content type, good first provider after foundation)

### Web Articles

- **Input format:** URL
- **Extraction library:** `trafilatura` (recommended — best article extraction, handles boilerplate removal), alternatives: `newspaper3k` (older but stable), `readability-lxml`
- **Text structure:** Article body with title, author, date. May include images, code blocks, embedded media.
- **Metadata available:** Title, author, publish date, site name, canonical URL, language, description
- **Chunking considerations:** Preserve paragraph boundaries. Code blocks should stay intact. Headings serve as section markers.
- **Citation model:** Section heading + paragraph offset. Link: original URL with optional anchor.
- **API constraints:** Respect robots.txt. Rate limit scraping to 1 req/sec per domain. Some sites block automated access.
- **Estimated effort:** M (2-3 days — extraction is straightforward, edge cases in HTML parsing)

### Reddit

- **Input format:** URL (thread, comment, subreddit) or search query
- **Extraction library:** `asyncpraw` (async Reddit API wrapper). Reddit API requires OAuth app registration.
- **Text structure:** Hierarchical threads — post + nested comment trees. Each comment has author, score, timestamp, parent reference.
- **Metadata available:** Subreddit, author, score, upvote ratio, comment count, flair, awards, creation time
- **Chunking considerations:** Thread-aware chunking — keep a comment and its direct replies together. Top-level post is its own chunk. High-score comments may deserve individual chunks.
- **Citation model:** Permalink to specific comment. Format: `r/subreddit - u/author (score)`.
- **API constraints:** Reddit API: 60 requests/minute (OAuth), 10 requests/minute (unauthenticated). Free tier is sufficient for most usage. Requires app registration at reddit.com/prefs/apps.
- **Estimated effort:** M (3-4 days — API integration + thread-aware chunking is the main complexity)

### Podcasts / Audio Files

- **Input format:** URL (RSS feed episode, direct audio URL) or file upload (.mp3, .wav, .m4a)
- **Extraction library:** `feedparser` for RSS parsing, `requests`/`httpx` for audio download. Reuse existing `transcription.py` (Whisper) for STT.
- **Text structure:** Identical to YouTube transcripts after Whisper processing — timestamped segments with optional speaker diarization.
- **Metadata available:** Episode title, show name, publish date, duration, description, episode number (from RSS). For uploaded files: filename, duration, format.
- **Chunking considerations:** Same as YouTube — timestamp-aligned semantic chunks. Podcast episodes tend to be longer (30-120 min), so chunk count will be higher.
- **Citation model:** Timestamp (same as YouTube). Link: audio player seek to timestamp.
- **API constraints:** RSS feeds are public. Audio download respects server bandwidth. No API keys needed.
- **Estimated effort:** S-M (2-3 days — mostly reuses existing transcription pipeline, new RSS parsing)

### Twitter/X

- **Input format:** URL (tweet, thread) or search query
- **Extraction library:** Twitter API v2 (official) or `snscrape` (scraping, may break). API requires developer account ($100/month for Basic tier).
- **Text structure:** Short posts (280 chars), threads (multiple linked posts), quote tweets, replies. Media attachments (images, video) may contain text.
- **Metadata available:** Author, timestamp, like count, retweet count, reply count, hashtags, mentions, media attachments
- **Chunking considerations:** Individual tweets are too short for standard chunking. Group entire threads as single chunks. For search results, group by topic/conversation.
- **Citation model:** Tweet permalink. Format: `@username - date`.
- **API constraints:** Twitter API v2 Basic: $100/month, 10K tweets/month read. Free tier: write-only (useless for reading). Rate limits: 300 requests/15min (app-level).
- **Estimated effort:** M-L (3-5 days — API cost barrier, thread reconstruction, short-text chunking strategy)

### Slack/Discord Exports

- **Input format:** File upload (Slack JSON export, Discord JSON export)
- **Extraction library:** Custom JSON parser. Slack export format: `channels/channel-name/YYYY-MM-DD.json`. Discord: varies by export tool (DiscordChatExporter recommended).
- **Text structure:** Chronological messages in channels/threads. Messages have author, timestamp, reactions, attachments, thread replies.
- **Metadata available:** Channel name, author, timestamp, reactions, thread structure, mentioned users
- **Chunking considerations:** Conversation-aware chunking — keep related messages together based on time proximity and thread structure. A gap of 30+ minutes typically indicates a new conversation.
- **Citation model:** Channel + timestamp. Format: `#channel - @author - date`. No external link (data is uploaded).
- **API constraints:** None (file upload). Slack exports require workspace admin access. File size can be large (GBs for active workspaces).
- **Estimated effort:** M (3-4 days — parsing is straightforward, conversation boundary detection is the challenge)

### Email Archives

- **Input format:** File upload (.mbox, .eml, .pst)
- **Extraction library:** `mailbox` (stdlib for mbox), `email` (stdlib for parsing), `extract-msg` for .msg, `pypff` for .pst (Outlook)
- **Text structure:** Email body (plain text or HTML), subject, from/to/cc, attachments. Threading via In-Reply-To/References headers.
- **Metadata available:** Subject, sender, recipients, date, thread ID, attachment names, labels/folders
- **Chunking considerations:** Thread-aware — group emails in same thread. Long email chains should separate recent from quoted content. Strip signatures and disclaimers.
- **Citation model:** Email subject + sender + date. No external link (data is uploaded).
- **API constraints:** None (file upload). Privacy considerations: email content is sensitive, ensure proper access controls.
- **Estimated effort:** M-L (3-5 days — format variety is the challenge, thread reconstruction from headers)

### GitHub Repos / Issues / PRs

- **Input format:** URL (repo, issue, PR) or GitHub API integration
- **Extraction library:** `PyGithub` or GitHub REST/GraphQL API directly via `httpx`. For repo content: `gitpython` for cloning.
- **Text structure:**
  - **Issues/PRs:** Title + body + comment thread (similar to Reddit structure)
  - **Repo files:** Code files with directory structure. README/docs are most relevant for RAG.
  - **Commits/diffs:** Change descriptions with context
- **Metadata available:** Repo name, author, stars, language, labels, milestones, assignees, creation/update dates
- **Chunking considerations:** Code-aware chunking — respect function/class boundaries. Use tree-sitter or AST parsing for intelligent code splitting. Issues/PRs chunk like Reddit threads.
- **Citation model:** File path + line numbers (code), issue/PR number + comment ID (discussions). Link: GitHub permalink.
- **API constraints:** GitHub API: 5000 requests/hour (authenticated), 60/hour (unauthenticated). Free for public repos. GitHub App or PAT for auth.
- **Estimated effort:** L (5-8 days — code-aware chunking is complex, multiple sub-types within GitHub)

---

## 4. Architecture Principles

### Principle 1: Content-Agnostic Pipeline
The core pipeline (extraction output → chunks → enrich → embed → index) must never import from or reference specific providers. All source-specific logic lives in provider classes.

**Test:** Can you add a new content type without modifying any file in `services/`?

### Principle 2: Provider Pattern for Source-Specific Logic
Every content source implements `ContentProvider`. The provider handles:
- Validation (does this URL/file exist? is it processable?)
- Metadata extraction (title, author, date, etc.)
- Text extraction (getting the raw text out of the source)
- Content-specific search (searching within the source platform)

The provider does NOT handle: chunking, enrichment, embedding, or indexing.

### Principle 3: JSONB Metadata for Source-Specific Fields
The generic Content model has a `source_metadata` JSONB column. Source-specific data goes there:
```python
# YouTube
source_metadata = {"youtube_id": "abc123", "channel_name": "...", "chapters": [...]}

# Reddit
source_metadata = {"subreddit": "MachineLearning", "score": 1542, "comment_count": 89}

# PDF
source_metadata = {"page_count": 42, "author": "...", "file_hash": "sha256:..."}
```

**Rule:** If only one content type needs a field, it goes in `source_metadata`. If 3+ content types need it, it becomes a real column.

### Principle 4: Extensible Citation System
Citations must support different source types without conditionals in the frontend:

```python
# Citation data stored per chunk
citation = {
    "type": "youtube_timestamp",  # or "pdf_page", "reddit_comment", "web_section"
    "label": "12:34",             # Human-readable (timestamp, page number, etc.)
    "url": "https://...",         # Direct link (YouTube URL with t=, Reddit permalink, etc.)
    "context": {                  # Type-specific context
        "channel_name": "...",    # YouTube
        "page_number": 7,         # PDF
        "subreddit": "...",       # Reddit
    }
}
```

### Principle 5: Foundation First
Do not build content-type providers on top of the current Video-specific model. Complete Phase 0 (generic Content model + content-agnostic task pipeline) before adding any new content type. Building on the Video model creates tech debt that compounds with each new type.

### Principle 6: Independently Deployable Providers
Each provider is a self-contained module. Adding Reddit support should not require changes to the YouTube provider, PDF provider, or core pipeline. The registry pattern enables this:

```python
# providers/registry.py auto-discovers and registers providers
# Adding a new provider = creating a new file in providers/
```

### Principle 7: Graceful Degradation Per Source
Each content type has different failure modes. Providers must handle their own errors gracefully:
- Reddit API down → queue for retry, don't block other content
- PDF parsing fails on one page → extract what you can, note the gap
- Audio too long for Whisper → warn user, offer to process first N minutes

---

## 5. Foundation Migration Sketch

### Generic Content Model

```sql
-- Extend videos table or create new content table
ALTER TABLE videos ADD COLUMN content_type VARCHAR(50) DEFAULT 'youtube';
ALTER TABLE videos ADD COLUMN source_metadata JSONB DEFAULT '{}';
ALTER TABLE videos ADD COLUMN source_url TEXT;  -- generic URL (replaces youtube_url)
ALTER TABLE videos ADD COLUMN source_id TEXT;    -- generic ID (replaces youtube_id)

-- Create index for content_type filtering
CREATE INDEX idx_videos_content_type ON videos(content_type);

-- Migrate existing data
UPDATE videos SET
    content_type = 'youtube',
    source_url = youtube_url,
    source_id = youtube_id,
    source_metadata = jsonb_build_object(
        'youtube_id', youtube_id,
        'youtube_url', youtube_url,
        'channel_name', channel_name,
        'channel_id', channel_id,
        'view_count', view_count,
        'like_count', like_count,
        'upload_date', upload_date,
        'chapters', chapters
    );
```

### Content Type Enum

```python
class ContentType(str, Enum):
    YOUTUBE = "youtube"
    PDF = "pdf"
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    WEB_ARTICLE = "web_article"
    REDDIT = "reddit"
    PODCAST = "podcast"
    AUDIO = "audio"
    TWITTER = "twitter"
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    GITHUB_ISSUE = "github_issue"
    GITHUB_REPO = "github_repo"
```

### Backward Compatibility Strategy

1. **Keep the `videos` table name** initially — renaming is a large migration with FK cascades. Add `content_type` column instead.
2. **Keep YouTube-specific columns** as nullable — they continue to work for YouTube content. New content types use `source_metadata` JSONB.
3. **Alias in code** — Create a `Content = Video` type alias so new code uses the generic name while the table migration is in progress.
4. **API versioning** — New endpoints use `/content/` prefix, old `/videos/` endpoints continue working for YouTube.
5. **Frontend routing** — `/content` page shows all types with filters, `/videos` redirects to `/content?type=youtube`.

### Generic Processing Task

```python
# tasks/content_tasks.py (new)
@celery_app.task
def process_content(content_id: str):
    """Generic content processing dispatcher."""
    content = get_content(content_id)
    provider = provider_registry.get_content_provider(content.content_type)

    # Phase 1: Extract text
    text_segments = provider.extract_text(content)  # New method on ContentProvider

    # Phase 2: Chunk (reuse existing)
    chunks = chunker.chunk_transcript(text_segments)

    # Phase 3: Enrich (reuse existing)
    enriched = [enricher.enrich_chunk(c) for c in chunks]

    # Phase 4: Embed + Index (reuse existing)
    embed_and_index(content_id, enriched)
```
