# Plan: Add Content Overview + Chat Activity Metric Cards to /videos Page

## Context

The `/videos` page shows two metric cards: **Storage** (usage + breakdown) and **Processing** (completion, minutes, messages, chunks). These answer "how much space am I using?" but leave two gaps:
- **"What's in my library?"** — no summary of content topics, duration, or languages
- **"Am I getting value from it?"** — no visibility into how the content is being used in conversations

We'll add two new cards to fill these gaps. All data already exists in the database — no new tables or migrations needed.

## New Cards

### Card: Content Overview

| Metric | Display example | DB source |
|--------|----------------|-----------|
| Total duration | "47h 23m of content" | `SUM(duration_seconds)` on completed videos |
| Summary coverage | "18 of 24 have summaries" | `COUNT WHERE summary IS NOT NULL` |
| Top topics | Badges: `ML`, `Python`, `Web Dev` (top 5) | Aggregate `key_topics` arrays, rank by frequency |
| Languages | "en, es, ja" | `DISTINCT transcription_language` |

### Card: Chat Activity

| Metric | Display example | DB source |
|--------|----------------|-----------|
| Total conversations | "23 conversations" | `COUNT` on user's conversations |
| Total messages | "187 messages" | `SUM(message_count)` |
| Most chatted video | "ML Course Ep.1 (8 conversations)" | Video with most `conversation_sources` entries |
| Last conversation | "2 hours ago" | `MAX(last_message_at)` |

## Implementation

### 1. Backend: `GET /api/v1/videos/stats`

**File:** `backend/app/api/routes/videos.py`

New endpoint with 3-4 lightweight aggregation queries (all indexed columns):

```python
@router.get("/stats")
async def get_video_stats(db, current_user) -> VideoStatsResponse:
    # Q1: Video aggregations (completed count, total duration, summary count, languages)
    # Q2: Top topics (flatten key_topics arrays, Counter.most_common(5))
    # Q3: Conversation aggregations (count, message sum, last_message_at)
    # Q4: Most chatted video (GROUP BY video_id on conversation_sources, LIMIT 1)
```

**Response schema** (inline or in `backend/app/schemas/`):

```python
class VideoStatsResponse(BaseModel):
    total_duration_seconds: int
    completed_count: int
    videos_with_summaries: int
    top_topics: list[str]
    languages: list[str]
    total_conversations: int
    total_messages: int
    most_chatted_video: MostChattedVideo | None
    last_conversation_at: datetime | None

class MostChattedVideo(BaseModel):
    id: str
    title: str
    conversation_count: int
```

### 2. Frontend: API client + types

**File:** `frontend/src/lib/api/videos.ts` — add `getStats()` method
**File:** `frontend/src/lib/types/index.ts` — add `VideoStats` type

### 3. Frontend: Render cards

**File:** `frontend/src/app/videos/page.tsx`

- Add `useQuery(["video-stats"], ...)` with `staleTime: 60_000`, enabled only when authenticated
- Render two new `<Card>` components below the existing Storage + Processing cards in the same grid
- Loading: `<Skeleton>` placeholders
- Empty states: "No content yet" / "No conversations yet" with contextual CTAs

### Pre-edit consultation (per CLAUDE.md)

- Read `.claude/prompts/rag-architect.md` before editing `videos.py` (it's adjacent to RAG pipeline routes)
- Read `.claude/prompts/test-generate.md` after implementation to write tests for the stats endpoint

## Files to modify

| File | Change |
|------|--------|
| `backend/app/api/routes/videos.py` | Add `GET /videos/stats` endpoint |
| `backend/app/schemas/` (or inline) | Add `VideoStatsResponse` schema |
| `frontend/src/lib/api/videos.ts` | Add `getStats()` API call |
| `frontend/src/lib/types/index.ts` | Add `VideoStats` type |
| `frontend/src/app/videos/page.tsx` | Add 2 new metric cards |

## Verification

1. `curl localhost:8000/api/v1/videos/stats` returns correct aggregated data
2. Cards render with loading skeletons while fetching
3. Empty state works for new user with 0 videos / 0 conversations
4. Numbers match actual DB state
5. `npx tsc --noEmit` passes
6. `npx next build` succeeds
7. Unit tests for the stats endpoint
