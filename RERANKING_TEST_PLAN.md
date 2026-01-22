# Reranking Validation Test Plan

## Objective
Validate that enabling reranking (`enable_reranking: True`) improves RAG accuracy, as predicted by Anthropic research showing 67% improvement with contextual retrieval + reranking.

## Change Details
- **File**: `backend/app/core/config.py:147`
- **Change**: `enable_reranking: bool = False` → `enable_reranking: bool = True`
- **Config**: Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` to rerank top 20 retrieved chunks down to top 7

## Test Plan Structure

### Phase 1: Technical Validation (Verify It Works)
Confirm reranking is actually executing in the pipeline.

### Phase 2: Accuracy Validation (Verify It Helps)
Measure retrieval and response quality improvements.

---

## Phase 1: Technical Validation

### Test 1.1: Configuration Check
**Objective**: Verify reranking is enabled in runtime

**Steps**:
```bash
# Check config via pipeline-status skill
.claude/skills/pipeline-status.sh | grep "Reranking enabled"
```

**Expected**: `Reranking enabled: True`

**Success Criteria**: ✅ Configuration shows reranking enabled

---

### Test 1.2: Reranker Service Initialization
**Objective**: Verify reranker service loads successfully

**Steps**:
```bash
# Run smoke test to check service initialization
.claude/skills/rag-smoke-test.sh
```

**Expected**:
- ✅ No import errors for `RerankerService`
- ✅ Cross-encoder model loads successfully
- ✅ All pipeline components pass

**Success Criteria**: ✅ RAG smoke test passes without errors

---

### Test 1.3: Retrieval Flow Inspection
**Objective**: Verify reranking executes in the retrieval path

**Steps**:
```bash
# Test via Python script
docker compose exec -T app python -c "
from app.core.config import settings
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.video import Video

# Get a test video
engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
db = Session()
video = db.query(Video).filter(Video.status == 'completed').first()

if video:
    embedding_service = EmbeddingService()
    vector_service = VectorStoreService()

    # Test retrieval with reranking
    query = 'What is the main topic discussed?'
    query_embedding = embedding_service.embed_text(query, use_cache=False)

    results = vector_service.search_chunks(
        query_embedding=query_embedding,
        video_ids=[video.id],
        user_id=video.user_id,
        top_k=20  # Should retrieve 20, rerank to 7
    )

    print(f'Retrieved {len(results)} chunks')
    print(f'Expected: 7 (after reranking from 20)')
    print(f'Top chunk score: {results[0].score:.3f}')
else:
    print('No completed videos to test')
"
```

**Expected**:
- Retrieves exactly 7 chunks (reranked from 20)
- Top chunk score > 0.5 (higher than without reranking)

**Success Criteria**: ✅ Reranking reduces 20 initial results to 7 reranked results

---

## Phase 2: Accuracy Validation

### Test 2.1: Retrieval Quality Comparison
**Objective**: Compare chunk relevance before and after reranking

**Methodology**: Use 5 test queries and measure:
- **Precision@7**: % of top 7 chunks that are relevant
- **Top chunk score**: Relevance score of best chunk
- **Score distribution**: How scores change with reranking

**Test Queries** (customize based on your video content):
1. "What is the main topic of this video?"
2. "What are the key conclusions or takeaways?"
3. "Are there any technical terms or concepts explained?"
4. "What examples or case studies are mentioned?"
5. "What recommendations or action items are provided?"

**Steps**:
```bash
# Create test script
docker compose exec -T app python tests/manual/test_reranking_accuracy.py
```

**Baseline Metrics** (to be collected with `enable_reranking: False`):
- Record for each query:
  - Top 7 chunk IDs retrieved
  - Relevance scores
  - Human judgment: relevant/not relevant for each chunk

**Post-Change Metrics** (with `enable_reranking: True`):
- Same queries, record same metrics
- Compare chunk ordering and scores

**Success Criteria**:
- ✅ Average precision@7 increases by ≥10%
- ✅ Top chunk scores increase for ≥4/5 queries
- ✅ Fewer irrelevant chunks in top 7

---

### Test 2.2: Response Quality (End-to-End)
**Objective**: Measure if generated responses improve with better chunks

**Methodology**: Use same 5 test queries, evaluate full RAG responses

**Metrics**:
- **Faithfulness**: Response accurately reflects chunk content (manual review)
- **Relevance**: Response addresses the question (1-5 scale)
- **Completeness**: Response covers key points (1-5 scale)
- **Citation quality**: Cited chunks are relevant (% relevant citations)

**Steps**:
1. Create conversation via API with each test query
2. Record response and cited chunks
3. Manually evaluate each response on 1-5 scale
4. Calculate average scores

**Baseline** (with `enable_reranking: False`):
```bash
# Test each query and record responses
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"video_ids": ["VIDEO_ID"], "message": "QUERY"}'
```

**Post-Change** (with `enable_reranking: True`):
- Same queries, record new responses
- Compare quality scores

**Success Criteria**:
- ✅ Average relevance score increases ≥0.5 points
- ✅ Citation quality improves (≥10% more relevant citations)
- ✅ At least 4/5 queries show improvement

---

### Test 2.3: Performance Impact
**Objective**: Measure latency overhead from reranking

**Metrics**:
- Query response time (p50, p95, p99)
- First chunk time (time to first streamed response)

**Steps**:
```bash
# Measure query latency
time curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"video_ids": ["VIDEO_ID"], "message": "Test query"}'
```

**Baseline** (without reranking):
- Run 10 queries, record response times

**Post-Change** (with reranking):
- Run 10 queries, record response times
- Calculate increase

**Success Criteria**:
- ✅ Median latency increases <200ms
- ✅ P95 latency increases <500ms
- ✅ Latency increase is acceptable trade-off for accuracy gain

---

## Quick Validation Tests (Minimal)

If time is limited, run these essential tests:

### Quick Test 1: Smoke Test
```bash
.claude/skills/rag-smoke-test.sh
```
✅ Pass: Pipeline works with reranking enabled

### Quick Test 2: Result Count Check
```bash
docker compose exec -T app python -c "
from app.core.config import settings
print(f'Reranking enabled: {settings.enable_reranking}')
print(f'Retrieval top_k: {settings.retrieval_top_k}')
print(f'Reranking top_k: {settings.reranking_top_k}')
print('')
print('Expected flow: Retrieve 20 chunks → Rerank → Return top 7')
"
```
✅ Pass: Shows correct configuration

### Quick Test 3: Manual Query Comparison
1. Ask same question twice via the UI
2. Check cited chunks - should be more relevant
3. Check response quality - should be better

✅ Pass: Subjective improvement in response quality

---

## Test Execution Checklist

- [ ] **Pre-Change**: Collect baseline metrics
  - [ ] Run pipeline-status (confirm reranking disabled)
  - [ ] Record retrieval results for 5 test queries
  - [ ] Record response quality scores
  - [ ] Record latency baseline

- [ ] **Change Applied**: Enable reranking ✅ (DONE)

- [ ] **Post-Change**: Collect new metrics
  - [ ] Restart services: `docker compose restart app worker`
  - [ ] Run pipeline-status (confirm reranking enabled)
  - [ ] Run RAG smoke test (confirm no errors)
  - [ ] Record new retrieval results for same 5 queries
  - [ ] Record new response quality scores
  - [ ] Record new latency metrics

- [ ] **Analysis**: Compare before/after
  - [ ] Calculate precision@7 improvement
  - [ ] Calculate response quality improvement
  - [ ] Calculate latency overhead
  - [ ] Document findings

- [ ] **Decision**: Keep or rollback
  - [ ] If accuracy improves ≥10% and latency <500ms: ✅ Keep
  - [ ] If accuracy improves <10% or latency >500ms: ❌ Investigate/rollback

---

## Expected Results (Based on Research)

Based on Anthropic's contextual retrieval research:
- **35% improvement** with contextual embeddings alone
- **49% improvement** with contextual embeddings + hybrid search
- **67% improvement** with contextual embeddings + hybrid search + reranking

Since we're only enabling reranking (not contextual embeddings or hybrid search):
- **Conservative estimate**: 15-25% improvement in retrieval accuracy
- **Best case**: 30-40% improvement

## Next Steps After Testing

### If Testing Shows Improvement:
1. ✅ Keep reranking enabled
2. Document baseline vs. improved metrics
3. Consider Phase 3: Enable contextual enrichment for further gains
4. Consider Phase 4: Implement hybrid search (BM25 + semantic)

### If Testing Shows Issues:
1. Check reranker model is loading correctly
2. Verify chunk quality (are chunks semantic and well-structured?)
3. Test different reranking model (e.g., `cross-encoder/ms-marco-MiniLM-L-12-v2`)
4. Adjust `reranking_top_k` (try 5 or 10 instead of 7)

---

## Automated Test Script (Optional)

Create `backend/tests/manual/test_reranking_accuracy.py`:

```python
"""Manual test script to compare retrieval quality with/without reranking."""
import time
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.video import Video
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService

# Test queries
TEST_QUERIES = [
    "What is the main topic of this video?",
    "What are the key conclusions or takeaways?",
    "Are there any technical terms or concepts explained?",
    "What examples or case studies are mentioned?",
    "What recommendations or action items are provided?",
]

def run_retrieval_test():
    """Test retrieval quality with current configuration."""
    print(f"Testing with reranking: {settings.enable_reranking}")
    print(f"Retrieval top_k: {settings.retrieval_top_k}")
    print(f"Reranking top_k: {settings.reranking_top_k}")
    print("=" * 60)

    # Get test video
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    video = db.query(Video).filter(Video.status == 'completed').first()

    if not video:
        print("❌ No completed videos found")
        return

    print(f"Testing with video: {video.title}")
    print("=" * 60)

    embedding_service = EmbeddingService()
    vector_service = VectorStoreService()

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\nQuery {i}: {query}")
        print("-" * 60)

        # Measure retrieval time
        start = time.time()
        query_embedding = embedding_service.embed_text(query, use_cache=False)
        results = vector_service.search_chunks(
            query_embedding=query_embedding,
            video_ids=[video.id],
            user_id=video.user_id,
            top_k=settings.reranking_top_k if settings.enable_reranking else 7
        )
        elapsed = (time.time() - start) * 1000

        print(f"Retrieved: {len(results)} chunks in {elapsed:.0f}ms")

        if results:
            print(f"Top scores: {[f'{r.score:.3f}' for r in results[:3]]}")
            print(f"Score range: {results[0].score:.3f} - {results[-1].score:.3f}")
            print(f"Preview: {results[0].text[:100]}...")
        else:
            print("No results returned")

    db.close()

if __name__ == "__main__":
    run_retrieval_test()
```

Run with:
```bash
docker compose exec -T app python tests/manual/test_reranking_accuracy.py
```
