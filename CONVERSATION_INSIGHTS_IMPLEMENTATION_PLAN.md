# Implementation Plan: Conversation Insights Mind-Map Visualization

## Overview

Add interactive mind-map visualization to display topics/themes extracted from selected videos in a conversation using React Flow. Users can click topics to see related chunks with "jump to timestamp" functionality.

**Status**: Ready for implementation
**Model**: Sonnet 4.5
**Estimated Effort**: 40-55 hours across 7 phases

---

## Key Requirements

### Feature Specifications
- **Data Source**: Extract topics from selected video content (transcripts/chunks), NOT chat messages
- **Detail Level**: 5-10 high-level topics only
- **Extraction Method**: Pure LLM-based (MVP with zero technical debt for future upgrade)
- **Visualization**: React Flow (https://reactflow.dev/)
- **UI Integration**: Modal/Dialog overlay triggered from conversation page
- **Interactivity**:
  - Click topic node → Highlight connected nodes + show detail panel
  - Detail panel shows related chunks with timestamps
  - "Jump to timestamp" buttons (integration point for future video player)
- **Generation**: On-demand when user opens modal
- **Caching**: Store generated insights in database to avoid re-extraction

### Technical Constraints
- **Zero New Dependencies (Backend)**: Use existing LLM infrastructure
- **Frontend**: Add `reactflow@11.10.4` only
- **Testing**: Comprehensive regression testing required
- **Upgrade Path**: Database schema and API contracts support future hybrid clustering approach

---

## Architecture Summary

### Backend Flow
```
User opens modal → Check cache (conversation_insights table)
  → If cached & video_ids match: Return cached graph
  → Else: Extract topics via LLM → Build graph → Cache → Return
```

### Frontend Flow
```
Click "Insights" button → Open dialog modal
  → Fetch graph data (React Query)
  → Render React Flow with custom nodes
  → Click topic node → Fetch chunks → Show detail panel
```

---

## Database Schema

### New Table: `conversation_insights`

```sql
CREATE TABLE conversation_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Snapshot of context when generated
    video_ids UUID[] NOT NULL,

    -- LLM metadata
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    extraction_prompt_version INT DEFAULT 1,

    -- Graph data as JSONB
    graph_data JSONB NOT NULL,
    -- Structure: {"nodes": [...], "edges": [...]}

    -- Topic-to-chunk mappings as JSONB
    topic_chunks JSONB NOT NULL,
    -- Structure: {"topic-1": [{chunk_id, video_id, timestamps, text}, ...]}

    -- Metrics
    topics_count INT NOT NULL,
    total_chunks_analyzed INT NOT NULL,
    generation_time_seconds FLOAT,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,

    INDEX idx_insights_conversation (conversation_id),
    INDEX idx_insights_user (user_id),
    INDEX idx_insights_created (created_at)
);
```

**Migration File**: `backend/alembic/versions/006_add_conversation_insights.py`

---

## Implementation Phases

### Phase 1: Database & Backend Foundation ✅ (Checkpoint 1)

**Files to Create**:
1. `backend/alembic/versions/006_add_conversation_insights.py`

**Files to Modify**:
1. `backend/app/models/__init__.py` (if creating Python model, optional)

**Tasks**:
- [ ] Create Alembic migration with conversation_insights table schema
- [ ] Run migration: `docker-compose exec app alembic upgrade head`
- [ ] Verify table created in PostgreSQL
- [ ] Create stub `backend/app/services/insights.py` with data classes

**Data Classes**:
```python
@dataclass
class TopicNode:
    id: str
    label: str
    description: str
    chunk_count: int
    relevance_score: float

@dataclass
class TopicChunk:
    chunk_id: uuid.UUID
    video_id: uuid.UUID
    video_title: str
    start_timestamp: float
    end_timestamp: float
    text: str
    chunk_title: Optional[str]

@dataclass
class InsightGraph:
    nodes: List[Dict]
    edges: List[Dict]
    topic_chunks: Dict[str, List[TopicChunk]]
    metadata: Dict
```

**Test**:
```bash
docker-compose exec app alembic current
# Should show migration 006 applied
```

---

### Phase 2: LLM Topic Extraction Logic ⚙️ (Checkpoint 2)

**Files to Create/Modify**:
1. `backend/app/services/insights.py` - Main implementation (400+ lines)
2. `backend/tests/unit/test_insights_service.py` - Unit tests

**Core Functions**:

#### 2.1 Chunk Sampling
```python
def _sample_chunks_for_extraction(
    chunks: List[Chunk],
    max_chunks: int = 50
) -> List[Chunk]:
    """
    Intelligent sampling:
    - Prioritize chapter boundaries
    - Even distribution across videos
    - High keyword diversity
    """
```

**Strategy**: If videos have chapters, take 2-3 chunks per chapter. Otherwise, sample evenly with keyword diversity scoring.

#### 2.2 LLM Prompt Design

**System Message**:
```python
system_prompt = """You are an expert at analyzing educational video content and identifying main themes.

Your task: Given summaries from video transcripts, extract 5-10 HIGH-LEVEL topics that organize the content.

Guidelines:
1. Topics should be BROAD themes, not specific facts
2. Each topic should encompass multiple chunks (3-15 chunks per topic)
3. Topics should be mutually exclusive where possible
4. Use clear, descriptive labels (3-8 words)
5. Provide a 2-3 sentence description of what the topic covers

Return ONLY valid JSON with this structure:
{
  "topics": [
    {
      "id": "topic-1",
      "label": "Neural Network Fundamentals",
      "description": "Covers basic architecture, layers, and forward propagation concepts...",
      "keywords": ["neural network", "layers", "activation", "forward pass"]
    }
  ]
}

IMPORTANT:
- Return 5-10 topics (adjust based on content diversity)
- Keywords help map topics to chunks (3-7 per topic)
- No external knowledge - only extract from provided content
"""
```

**User Message**:
```python
user_prompt = f"""Video Context:
Videos: {', '.join(v.title for v in videos)}

Chunk Summaries (from {len(sampled_chunks)} segments across {len(videos)} videos):

{formatted_chunks}

Extract 5-10 main topics from this content. Return JSON only."""
```

#### 2.3 Topic-to-Chunk Mapping

```python
def _map_topics_to_chunks(
    topics: List[TopicNode],
    all_chunks: List[Chunk]
) -> Dict[str, List[TopicChunk]]:
    """
    Match topics to chunks using keyword overlap.
    Returns top 15 chunks per topic.
    """
    # For each topic, score chunks by keyword overlap
    # Take top 15 chunks per topic
```

#### 2.4 Graph Construction

```python
def _build_graph_structure(
    topics: List[TopicNode],
    videos: List[Video],
    topic_chunks: Dict[str, List[TopicChunk]]
) -> Dict:
    """
    Build React Flow graph:
    - Video nodes (outer ring)
    - Topic nodes (inner ring)
    - Edges: topic → videos containing that topic
    """
```

**Graph Format**:
```json
{
  "nodes": [
    {
      "id": "topic-1",
      "type": "topic",
      "data": {
        "label": "Neural Network Fundamentals",
        "description": "...",
        "chunkCount": 12
      }
    },
    {
      "id": "video-uuid",
      "type": "video",
      "data": {
        "label": "Video Title",
        "thumbnail": "https://...",
        "duration": 3600
      }
    }
  ],
  "edges": [
    {
      "id": "topic-1-video-uuid",
      "source": "topic-1",
      "target": "video-uuid",
      "type": "contains"
    }
  ]
}
```

#### 2.5 Main Extraction Function

```python
async def extract_topics_from_videos(
    db: Session,
    user_id: uuid.UUID,
    video_ids: List[uuid.UUID],
    target_topics: int = 7
) -> InsightGraph:
    """
    1. Fetch all chunks for videos
    2. Sample 30-50 chunks intelligently
    3. Call LLM with extraction prompt
    4. Parse JSON response (follow enrichment.py pattern)
    5. Map topics to chunks via keywords
    6. Build graph structure
    """
```

**JSON Parsing Pattern** (copy from `enrichment.py` lines 125-174):
- Remove markdown code blocks
- Parse JSON
- Fallback heuristics if parsing fails

**Test**:
```bash
pytest backend/tests/unit/test_insights_service.py -v
# Test sampling, keyword matching, graph building
```

---

### Phase 3: Caching & API Routes 🌐 (Checkpoint 3)

**Files to Create**:
1. `backend/app/api/routes/insights.py` (200+ lines)
2. `backend/tests/unit/test_insights_routes.py`

**Files to Modify**:
1. `backend/app/api/routes/__init__.py` - Add insights router

#### 3.1 Caching Service

```python
async def get_or_generate_insights(
    db: Session,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    force_regenerate: bool = False
) -> InsightGraph:
    """
    Check cache (conversation_insights table).
    If cached and video_ids match: return cached data.
    Else: generate new insights, save to cache, return.
    """
```

**Cache Key**: `conversation_id` + matching `video_ids` array

#### 3.2 API Endpoints

**Endpoint 1**: `GET /api/v1/conversations/{conversation_id}/insights`

**Query Params**: `regenerate: bool = False`

**Response**:
```json
{
  "conversation_id": "uuid",
  "graph": {
    "nodes": [...],
    "edges": [...]
  },
  "metadata": {
    "topicsCount": 7,
    "chunksAnalyzed": 45,
    "generationTime": 5.2,
    "cached": true,
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

**Endpoint 2**: `GET /api/v1/conversations/{conversation_id}/insights/topics/{topic_id}/chunks`

**Response**:
```json
{
  "topicId": "topic-1",
  "topicLabel": "Neural Network Fundamentals",
  "chunks": [
    {
      "chunkId": "uuid",
      "videoId": "uuid",
      "videoTitle": "Introduction to Deep Learning",
      "startTimestamp": 120.5,
      "endTimestamp": 145.2,
      "timestampDisplay": "02:00 - 02:25",
      "text": "Neural networks are composed of layers...",
      "chunkTitle": "Network Architecture Basics"
    }
  ]
}
```

#### 3.3 Router Registration

**File**: `backend/app/api/routes/__init__.py`

```python
from app.api.routes import insights

api_router.include_router(insights.router, prefix="/conversations", tags=["insights"])
```

**Test**:
```bash
# Run API endpoint tests
pytest backend/tests/unit/test_insights_routes.py -v

# Manual API test
curl http://localhost:8000/api/v1/conversations/{id}/insights
```

---

### Phase 4: Frontend Components 🎨 (Checkpoint 4)

**Files to Create**:
1. `frontend/src/components/insights/ConversationInsightMap.tsx`
2. `frontend/src/components/insights/TopicNode.tsx`
3. `frontend/src/components/insights/VideoNode.tsx`
4. `frontend/src/lib/api/insights.ts`

**Files to Modify**:
1. `frontend/package.json` - Add reactflow dependency

#### 4.1 Install React Flow

```bash
cd frontend
npm install reactflow@11.10.4
```

#### 4.2 API Client Module

**File**: `frontend/src/lib/api/insights.ts`

```typescript
export const insightsApi = {
  async getInsights(
    conversationId: string,
    regenerate = false
  ): Promise<InsightsResponse> {
    const response = await apiClient.get(
      `/conversations/${conversationId}/insights`,
      { params: { regenerate } }
    );
    return response.data;
  },

  async getTopicChunks(
    conversationId: string,
    topicId: string
  ): Promise<TopicChunksResponse> {
    const response = await apiClient.get(
      `/conversations/${conversationId}/insights/topics/${topicId}/chunks`
    );
    return response.data;
  },
};
```

#### 4.3 Main Map Component

**File**: `frontend/src/components/insights/ConversationInsightMap.tsx`

**Key Features**:
- React Flow with custom node types (topic, video)
- Node click handler to highlight connected nodes
- State management for selected topic
- Integration with TopicDetailPanel

**Structure**:
```typescript
"use client";

import ReactFlow, { useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";

export function ConversationInsightMap({
  conversationId,
  graphData,
}: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(graphData.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphData.edges);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);

  const handleNodeClick = (node: Node) => {
    // Highlight connected nodes
    // Set selectedTopicId
  };

  return (
    <div className="flex h-full w-full gap-4">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={{ topic: TopicNode, video: VideoNode }}
        onNodeClick={handleNodeClick}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
      {selectedTopicId && (
        <TopicDetailPanel
          conversationId={conversationId}
          topicId={selectedTopicId}
          onClose={() => setSelectedTopicId(null)}
        />
      )}
    </div>
  );
}
```

#### 4.4 Custom Node Components

**TopicNode.tsx**:
```typescript
export const TopicNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={cn("rounded-lg border-2 px-4 py-3", selected && "border-primary")}>
      <Handle type="target" position={Position.Left} />
      <p className="text-sm font-semibold">{data.label}</p>
      <Badge>{data.chunkCount} chunks</Badge>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
```

**VideoNode.tsx**:
```typescript
export const VideoNode = memo(({ data }: NodeProps) => {
  return (
    <div className="rounded-lg border bg-muted px-3 py-2">
      <Handle type="target" position={Position.Left} />
      <Video className="h-4 w-4" />
      <p className="text-xs">{data.label}</p>
    </div>
  );
});
```

**Test**: Render component with hardcoded graph data in Storybook or test page.

---

### Phase 5: Detail Panel & Interactions 🖱️ (Checkpoint 5)

**Files to Create**:
1. `frontend/src/components/insights/TopicDetailPanel.tsx`

#### 5.1 Topic Detail Panel

**File**: `frontend/src/components/insights/TopicDetailPanel.tsx`

**Features**:
- Fetch chunks for selected topic (React Query)
- Display list of chunks with timestamps
- "Jump to timestamp" button (stub for now)
- Scroll area for long lists

**Structure**:
```typescript
export function TopicDetailPanel({
  conversationId,
  topicId,
  onClose,
}: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["topic-chunks", conversationId, topicId],
    queryFn: () => insightsApi.getTopicChunks(conversationId, topicId),
  });

  return (
    <div className="w-80 border-l p-4">
      <h3>{data?.topicLabel}</h3>
      <ScrollArea>
        {data?.chunks.map(chunk => (
          <div key={chunk.chunkId}>
            <p>{chunk.videoTitle}</p>
            <p>{chunk.timestampDisplay}</p>
            <Button onClick={() => handleJumpToTimestamp(chunk)}>
              <Play /> Jump to timestamp
            </Button>
            <p>{chunk.text}</p>
          </div>
        ))}
      </ScrollArea>
    </div>
  );
}
```

**Jump to Timestamp Handler** (stub):
```typescript
const handleJumpToTimestamp = (videoId: string, timestamp: number) => {
  // Future: Integrate with video player
  console.log(`Jump to ${videoId} at ${timestamp}s`);
};
```

**Test**: Click topic node, verify detail panel shows chunks with correct data.

---

### Phase 6: Modal Integration & Polish 🎬 (Checkpoint 6)

**Files to Modify**:
1. `frontend/src/app/conversations/[id]/page.tsx` - Add insights button and dialog

#### 6.1 Add Insights Button

**Location**: Header section (~line 740)

**Changes**:
```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ConversationInsightMap } from "@/components/insights/ConversationInsightMap";
import { Network } from "lucide-react";

// Add state
const [insightsDialogOpen, setInsightsDialogOpen] = useState(false);

// Add query (only loads when dialog opens)
const { data: insightsData, isLoading: insightsLoading } = useQuery({
  queryKey: ["conversation-insights", conversationId],
  queryFn: () => insightsApi.getInsights(conversationId as string),
  enabled: insightsDialogOpen && !!conversationId,
  staleTime: 300000, // 5 minutes
});

// Add button in header
<Dialog open={insightsDialogOpen} onOpenChange={setInsightsDialogOpen}>
  <DialogTrigger asChild>
    <Button variant="outline" size="sm" className="gap-2">
      <Network className="h-4 w-4" />
      Insights
    </Button>
  </DialogTrigger>
  <DialogContent className="max-w-6xl h-[85vh] p-0">
    <DialogHeader className="p-6 pb-4">
      <DialogTitle>Conversation Insights: Topic Map</DialogTitle>
    </DialogHeader>
    <div className="flex-1 min-h-0 px-6 pb-6">
      {insightsLoading ? (
        <Loader2 className="animate-spin" />
      ) : insightsData ? (
        <ConversationInsightMap
          conversationId={conversationId}
          graphData={insightsData.graph}
        />
      ) : (
        <p>No insights available</p>
      )}
    </div>
  </DialogContent>
</Dialog>
```

#### 6.2 Optional: Regenerate Button

Add button in dialog header to force regeneration:
```typescript
<Button
  variant="outline"
  size="sm"
  onClick={() => {
    queryClient.invalidateQueries(["conversation-insights", conversationId]);
    insightsApi.getInsights(conversationId, true); // regenerate=true
  }}
>
  Regenerate
</Button>
```

**Test**:
- Click "Insights" button in conversation page
- Verify modal opens with loading state
- Verify map displays with topics and videos
- Click topic nodes and verify interactions work

---

### Phase 7: Testing & Regression ✅ (Final)

**Tasks**:

#### 7.1 Backend Unit Tests

**Run tests**:
```bash
pytest backend/tests/unit/test_insights_service.py -v
pytest backend/tests/unit/test_insights_routes.py -v
pytest backend/tests/test_insights_integration.py -v
```

**Coverage Check**:
```bash
pytest backend/tests --cov=app.services.insights --cov=app.api.routes.insights
```

#### 7.2 Regression Testing Checklist

**Verify these existing features still work**:

**Conversations**:
- [ ] Create conversation from collection
- [ ] Create conversation from individual videos
- [ ] Conversation list loads correctly
- [ ] Send message and receive response
- [ ] Chunk references displayed correctly
- [ ] Source citations work (click to scroll)

**Source Management**:
- [ ] Select/deselect sources in conversation
- [ ] Add new videos to conversation
- [ ] Sources persist across page refresh

**Videos**:
- [ ] Upload new video (ingest YouTube URL)
- [ ] Delete video
- [ ] Video processing status updates

**Collections**:
- [ ] Create collection
- [ ] Add videos to collection
- [ ] Conversation syncs with collection videos

**Authentication**:
- [ ] Login/logout works
- [ ] Protected routes redirect to login
- [ ] User data persists correctly

#### 7.3 Manual Testing Script

**Test Case 1: Basic Insights Generation**
1. Create conversation with 2-3 completed videos
2. Click "Insights" button
3. Wait for generation (5-10 seconds)
4. Verify mind-map displays with topics and videos
5. Click topic node → Verify connected videos highlight
6. Verify detail panel shows chunks
7. Close modal → Reopen → Verify cached data loads instantly

**Test Case 2: Video Selection Changes**
1. Generate insights for conversation with videos A, B
2. Close modal
3. Change conversation sources to videos A, C
4. Reopen insights modal
5. Verify new insights generated (should detect video change)

**Test Case 3: Large Conversation**
1. Create conversation with 10 videos
2. Generate insights
3. Verify graph displays correctly (no performance issues)
4. Verify sampling works (max 50 chunks analyzed)

**Test Case 4: No Videos Selected**
1. Create empty conversation (no videos)
2. Click "Insights" button
3. Verify helpful error message shown

#### 7.4 Performance Testing

**Metrics to Track**:
- Insight generation time (target: <15 seconds for 5 videos)
- Frontend render time (target: <500ms for 20 nodes)
- API response time for cached insights (target: <200ms)

#### 7.5 Bug Fixes

Document and fix any issues found during testing.

---

## Files Summary

### Files to CREATE (11 new files)

**Backend (6 files)**:
1. `backend/alembic/versions/006_add_conversation_insights.py` - Migration
2. `backend/app/services/insights.py` - Topic extraction service (~400 lines)
3. `backend/app/api/routes/insights.py` - API endpoints (~200 lines)
4. `backend/tests/unit/test_insights_service.py` - Service tests
5. `backend/tests/unit/test_insights_routes.py` - Route tests
6. `backend/tests/test_insights_integration.py` - Integration tests

**Frontend (5 files)**:
7. `frontend/src/components/insights/ConversationInsightMap.tsx` - Main map
8. `frontend/src/components/insights/TopicNode.tsx` - Custom node
9. `frontend/src/components/insights/VideoNode.tsx` - Custom node
10. `frontend/src/components/insights/TopicDetailPanel.tsx` - Detail panel
11. `frontend/src/lib/api/insights.ts` - API client

### Files to MODIFY (3 files)

**Backend (1 file)**:
1. `backend/app/api/routes/__init__.py` - Add insights router

**Frontend (2 files)**:
2. `frontend/package.json` - Add reactflow dependency
3. `frontend/src/app/conversations/[id]/page.tsx` - Add insights button + modal

---

## Critical Implementation Details

### LLM Prompt Pattern

**Follow `enrichment.py` pattern** (lines 87-174):
- System message with clear instructions
- User message with formatted input
- JSON parsing with fallback heuristics
- Manual markdown code block removal

### Graph Data Format

**React Flow expects**:
```typescript
{
  nodes: [
    { id: string, type: string, data: any, position?: {x, y} }
  ],
  edges: [
    { id: string, source: string, target: string, type?: string }
  ]
}
```

**Auto-layout**: Use `fitView` prop to automatically position nodes. For advanced layouts, consider `dagre` or `elkjs` libraries.

### Caching Strategy

**Cache Hit**: `conversation_id` exists AND `video_ids` array matches exactly
**Cache Miss**: Generate new insights, overwrite old cache entry

### Error Handling

**LLM Parsing Failure**:
- Log error with full LLM response
- Retry once with modified prompt
- Fall back to simple keyword extraction if both fail

**No Enriched Chunks**:
- Use raw chunk text
- Extract first sentence as title
- Show warning in UI: "Limited insights - chunks not enriched"

---

## Edge Cases & Gotchas

### React Flow SSR Issues
- Always use `"use client"` directive
- React Flow requires browser APIs (window, document)
- If issues persist, use dynamic import: `const ReactFlow = dynamic(() => import('reactflow'), { ssr: false })`

### Large Context (10+ Videos)
- Enforce sampling: max 50 chunks analyzed
- Use chunk summaries instead of full text
- Show warning in UI if >10 videos selected

### Stale Cache Detection
- Check `video_ids` array match on every fetch
- Show "Regenerate" button if mismatch detected
- Optional: Auto-regenerate on video change (can be added later)

### Topic-Chunk Mapping Accuracy
- Use multiple signals: keywords + title + summary overlap
- Start with 70% accuracy goal (MVP)
- Future: Add embedding similarity for better matching

---

## Future Upgrade Path (Post-MVP)

This implementation maintains **zero technical debt** for:

1. **Hybrid Clustering** (Option 3 from original proposal):
   - Replace pure LLM with embedding-based clustering + LLM labeling
   - Database schema unchanged (just modify `insights.py`)
   - API contracts unchanged
   - Frontend unchanged

2. **Video Relationship Graph** (Secondary Feature):
   - New endpoint `/insights/video-relationships`
   - Reuse same React Flow components
   - New analysis: compare topics across videos

3. **Interactive Editing**:
   - Allow users to merge/split topics
   - Store edits in `graph_data` JSONB
   - Add `user_modified: bool` flag

---

## Success Criteria

**MVP Complete When**:
- [ ] User can click "Insights" button in conversation page
- [ ] Modal displays mind-map with 5-10 topics
- [ ] Topics connected to source videos via edges
- [ ] Clicking topic highlights connected nodes
- [ ] Detail panel shows related chunks with timestamps
- [ ] "Jump to timestamp" button present (stub OK)
- [ ] Insights cached for repeat views
- [ ] All regression tests pass
- [ ] No breaking changes to existing features

**Performance Targets**:
- Insight generation: <15 seconds for 5 videos
- Frontend render: <500ms for 20 nodes
- Cached response: <200ms

---

## Next Steps to Begin Implementation

1. **Confirm plan approval** with user
2. **Start Phase 1**: Create database migration
3. **Follow phases sequentially** with checkpoints
4. **Test at each phase** before moving forward
5. **Document any deviations** from plan

---

## Questions for User (Before Implementation)

1. ✅ Confirmed: Use Option 1 (pure LLM) for MVP
2. ✅ Confirmed: React Flow for visualization
3. ✅ Confirmed: Modal/Dialog UI integration
4. ✅ Confirmed: On-demand generation with caching
5. ✅ Confirmed: Comprehensive regression testing required

**Ready to proceed with implementation!**
