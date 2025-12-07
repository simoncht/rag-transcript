# RAG Retrieval Accuracy Improvements - December 7, 2025

**Status**: 📋 PLANNED | 🎯 HIGH IMPACT
**Last Updated**: 2025-12-07
**Focus**: Improving answer accuracy through better retrieval and ranking

---

## Executive Summary

Current implementation correctly filters transcripts by selected videos but has room for improvement in:
1. **Retrieval quality** - ranking and filtering retrieved chunks
2. **Context construction** - providing more grounding information to LLM
3. **Embedding quality** - using better models for semantic search
4. **Hybrid approaches** - combining multiple retrieval strategies

**Verified**: Vector filtering by selected videos ✅ | Source isolation ✅

---

## Current State Assessment

### What's Working Well ✅
- **Video filtering**: Only selected videos' transcripts are searched (vector filter at Qdrant level)
- **Source isolation**: No leakage of content from unselected videos
- **Conversation history**: Last 5 messages included for context
- **Citation tracking**: Source chunks with timestamps properly linked

### Current Architecture
```
User Query → Embed (all-MiniLM-L6-v2) → Vector Search (top 10) → Use top 5 → Build Context → LLM
```

---

## High Impact Improvements

### 1. **Enable Re-ranking** (RECOMMENDED - Quick Win)
**Priority**: 🔴 HIGH | **Effort**: 🟢 LOW | **Impact**: 📈 HIGH

Re-ranking improves precision by re-scoring retrieved chunks using a cross-encoder model.

**Current State**: Disabled in `.env`
```bash
ENABLE_RERANKING=False
RERANKING_TOP_K=5
```

**Changes Needed**:
1. Install cross-encoder: `pip install sentence-transformers`
2. Update `backend/app/services/llm_providers.py` to include re-ranking logic
3. Set `ENABLE_RERANKING=True` in `.env`
4. Choose model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (lightweight, good quality)

**How it works**:
```
Retrieve top 10 chunks (fast, broad)
    ↓
Re-rank with cross-encoder (slow but accurate)
    ↓
Use top 5 re-ranked chunks for context
```

**Expected Impact**: +15-30% improvement in answer accuracy

---

### 2. **Upgrade Embedding Model** (RECOMMENDED - Medium Effort)
**Priority**: 🔴 HIGH | **Effort**: 🟡 MEDIUM | **Impact**: 📈 HIGH

Current embedding model `all-MiniLM-L6-v2` is fast but limited in semantic understanding.

**Comparison**:
| Model | Dimensions | Quality | Speed | File Size |
|-------|-----------|---------|-------|-----------|
| `all-MiniLM-L6-v2` (Current) | 384 | ⭐⭐⭐ | ✅ Fast | 22 MB |
| `all-mpnet-base-v2` | 768 | ⭐⭐⭐⭐ | Medium | 420 MB |
| `e5-large-v2` | 1024 | ⭐⭐⭐⭐⭐ | Slower | 669 MB |
| `bge-large-en-v1.5` | 1024 | ⭐⭐⭐⭐⭐ | Slower | 349 MB |

**Recommendation**: Start with `all-mpnet-base-v2` (good balance)

**Changes Needed**:
1. Update `.env`:
```bash
EMBEDDING_MODEL="all-mpnet-base-v2"
EMBEDDING_DIMENSIONS=768
```
2. Download model on first run
3. Re-embed all existing chunks (one-time, automatic)

**Expected Impact**: +20-40% improvement in retrieval quality

---

### 3. **Implement Relevance Threshold** (RECOMMENDED - Quick Win)
**Priority**: 🔴 HIGH | **Effort**: 🟢 LOW | **Impact**: 📈 MEDIUM

Filter out low-confidence matches before building context.

**Code Location**: `backend/app/api/routes/conversations.py:643-660`

**Implementation**:
```python
# After vector search, add threshold filtering
MIN_RELEVANCE_SCORE = 0.50  # Configurable in .env
scored_chunks = [c for c in scored_chunks if c.score >= MIN_RELEVANCE_SCORE]

if not scored_chunks:
    # Inform LLM that no relevant context was found
    context = "WARNING: No relevant content found in the selected transcripts."
else:
    # Use filtered chunks
    context_parts = [...]
```

**Benefits**:
- Prevents low-quality matches from polluting context
- More honest when query doesn't match any transcript
- LLM can respond accordingly ("not mentioned in transcripts")

**Expected Impact**: +10-20% improvement in answer accuracy

---

### 4. **Improve Context Construction** (RECOMMENDED - Quick Win)
**Priority**: 🟡 MEDIUM | **Effort**: 🟢 LOW | **Impact**: 📈 MEDIUM

Current context is minimal. Add speaker info, timestamps, and topic headers.

**Current Context Format** (`conversations.py:651-660`):
```
[Source 1] (Relevance: 0.85)
Timestamp: 123.5s - 145.2s
This is the chunk text content...
```

**Improved Context Format**:
```
[Source 1] from "Video Title Here"
Speaker: Dr. John Smith
Timestamp: 02:03 - 02:25
Topic: Machine Learning Fundamentals
Relevance: 85% match
---
This is the chunk text content...
```

**Code Changes**:
```python
# In send_message, update context building
context_parts = []
for i, chunk in enumerate(scored_chunks[:5], 1):
    video = db.query(Video).filter(Video.id == chunk.video_id).first()

    context_parts.append(
        f"[Source {i}] from \"{video.title}\"\n"
        f"Speaker: {chunk.speakers[0] if chunk.speakers else 'Unknown'}\n"
        f"Timestamp: {_format_timestamp_display(chunk.start_timestamp, chunk.end_timestamp)}\n"
        f"Topic: {chunk.chapter_title or chunk.title or 'N/A'}\n"
        f"Relevance: {(chunk.score * 100):.0f}% match\n"
        f"---\n{chunk.text}\n"
    )
```

**Expected Impact**: +5-15% improvement (better LLM grounding)

---

### 5. **Hybrid Search: Semantic + Keyword** (Medium Effort)
**Priority**: 🟡 MEDIUM | **Effort**: 🟡 MEDIUM | **Impact**: 📈 MEDIUM

Combine vector similarity search with keyword/BM25 search to catch exact terms.

**Current**: Only semantic search (embeddings)
```
Query: "What is the default chunk size?"
Result: May miss exact phrase if worded differently
```

**Hybrid Approach**:
```
Query: "What is the default chunk size?"

1. Semantic Search: Find chunks about chunking strategies (score: 0.78)
2. Keyword Search: Find chunks with exact terms "default" AND "chunk" (score: 0.95)
3. Fuse Scores: α * semantic + (1-α) * keyword (α = 0.6)
4. Use fused ranking
```

**Implementation**:
- Add simple BM25 using Python `rank_bm25` package
- Create hybrid search function
- Rank fusion with configurable weights

**Expected Impact**: +10-25% on queries with exact keywords

---

## Medium Impact Improvements

### 6. **Query Expansion/Reformulation**
**Priority**: 🟡 MEDIUM | **Effort**: 🟡 MEDIUM | **Impact**: 📈 MEDIUM

Use LLM to expand user query before embedding and searching.

**Example**:
```
User Query: "How do we chunk videos?"

Expanded Queries (auto-generated):
1. "Video chunking strategy and configuration"
2. "Breaking transcripts into smaller segments"
3. "Chunk size settings and parameters"

Then embed all 3 and merge results (take union of top-k)
```

**Benefits**:
- Catches synonyms and paraphrases
- Better coverage of related concepts
- Especially useful for vague queries

---

### 7. **Contextual Chunk Headers**
**Priority**: 🟡 MEDIUM | **Effort**: 🔴 HIGH | **Impact**: 📈 HIGH

When chunking transcripts, prepend context to improve embedding quality.

**Current Chunking**:
```
chunk.text = "The model uses attention mechanisms to..."
```

**Contextual Chunking**:
```
chunk.text = "This is from a video titled 'Advanced ML Techniques' discussing transformers.
The model uses attention mechanisms to..."
```

**Benefits**:
- Embeddings capture context better
- Reduces ambiguity (what model? what context?)
- Requires re-chunking existing videos

**Implementation**: Modify `backend/app/services/chunking.py`

---

### 8. **Increase Retrieval Depth with Filtering**
**Priority**: 🟡 MEDIUM | **Effort**: 🟢 LOW | **Impact**: 📈 MEDIUM

Retrieve more candidates, then aggressively filter.

**Current**:
```python
RETRIEVAL_TOP_K=10  # Retrieve 10
Use top 5 for context (50% usage)
```

**Improved**:
```python
RETRIEVAL_TOP_K=20  # Retrieve 20
Apply re-ranking → select top 5-7
Apply relevance threshold → final list
```

**Changes**: Update in `.env`:
```bash
RETRIEVAL_TOP_K=20
RERANKING_TOP_K=7
MIN_RELEVANCE_SCORE=0.50
```

---

### 9. **Add Response Confidence Indicator**
**Priority**: 🟢 LOW | **Effort**: 🟢 LOW | **Impact**: 🟢 LOW (UX)

Show user how confident the response is based on chunk scores.

**Implementation**:
```python
avg_relevance = np.mean([c.score for c in scored_chunks[:5]])
confidence_level = (
    "High" if avg_relevance > 0.75 else
    "Medium" if avg_relevance > 0.55 else
    "Low"
)

# Return in response
response.confidence = confidence_level
```

**Frontend**: Display confidence badge next to response

---

### 10. **Better "No Context" Handling**
**Priority**: 🟢 LOW | **Effort**: 🟢 LOW | **Impact**: 🟢 LOW

Be explicit when retrieval returns poor results.

**Implementation**:
```python
if not scored_chunks or scored_chunks[0].score < 0.40:
    context = (
        "⚠️ WARNING: No relevant content found in selected transcripts. "
        "The response below may be speculative or based on general knowledge."
    )
    user_message_with_context = f"{context}\n\nUser question: {request.message}"
```

**Benefit**: Honest feedback to user when transcripts don't match query

---

## Implementation Roadmap

### Phase 1: Quick Wins (This Week)
1. ✅ Enable re-ranking
2. ✅ Add relevance threshold
3. ✅ Improve context construction

**Effort**: 2-3 hours | **Expected Accuracy Gain**: +25-35%

### Phase 2: Model Upgrade (Next Week)
1. Upgrade embedding model to `all-mpnet-base-v2`
2. Re-embed existing chunks (automated)
3. Test accuracy improvement

**Effort**: 4-6 hours | **Expected Accuracy Gain**: +20-40%

### Phase 3: Advanced (Future)
1. Implement hybrid search
2. Add query expansion
3. Contextual chunk headers (requires re-chunking)

**Effort**: 8-12 hours | **Expected Accuracy Gain**: +15-30%

---

## Configuration Reference

### Current `.env` Settings
```bash
# RAG Configuration
RETRIEVAL_TOP_K=10
RERANKING_TOP_K=5
ENABLE_RERANKING=False
CONVERSATION_HISTORY_TOKEN_LIMIT=2000

# Embedding Configuration
EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS=384
```

### Recommended `.env` Settings (After Improvements)
```bash
# RAG Configuration
RETRIEVAL_TOP_K=20
RERANKING_TOP_K=7
ENABLE_RERANKING=True
MIN_RELEVANCE_SCORE=0.50
CONVERSATION_HISTORY_TOKEN_LIMIT=2000

# Embedding Configuration
EMBEDDING_MODEL="sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIMENSIONS=768
```

---

## Metrics to Track

Before implementing improvements, establish baselines:

| Metric | Current | Goal |
|--------|---------|------|
| Avg chunk relevance score | TBD | 0.70+ |
| Avg retrieval precision | TBD | 0.80+ |
| User satisfaction (if possible) | TBD | 4.0+/5.0 |
| Response time (ms) | <500ms | <1000ms |
| Re-rank filtering rate | N/A | 20-30% removed |

---

## Testing Checklist

### For Each Improvement
- [ ] Baseline metric recorded
- [ ] Implementation complete
- [ ] Tests pass (if applicable)
- [ ] Improvement metric recorded
- [ ] Compared to baseline

### Regression Testing
- [ ] No new chunks lost during re-embedding
- [ ] All videos still searchable
- [ ] Conversation history still works
- [ ] Response times acceptable

---

## Related Files

### Core Files
- `backend/app/api/routes/conversations.py` - Message handling & RAG pipeline
- `backend/app/services/vector_store.py` - Vector search implementation
- `backend/app/services/embeddings.py` - Embedding generation
- `backend/app/core/config.py` - Configuration settings

### Config Files
- `backend/.env` - Environment variables
- `docker-compose.yml` - Docker configuration

### Documentation
- `RESUME.md` - Development overview
- `API_PERFORMANCE_OPTIMIZATION.md` - Previous optimization work

---

## Next Steps

1. **Immediate (Today)**
   - [ ] Implement re-ranking
   - [ ] Add relevance threshold
   - [ ] Improve context construction

2. **Short Term (This Week)**
   - [ ] Test improvements with sample queries
   - [ ] Measure accuracy gain
   - [ ] Document results

3. **Medium Term (Next Week)**
   - [ ] Upgrade embedding model
   - [ ] Re-embed all chunks
   - [ ] Benchmark new retrieval quality

4. **Long Term**
   - [ ] Consider hybrid search
   - [ ] Add query expansion
   - [ ] Implement user feedback loop

---

## Summary

Your RAG application correctly isolates transcript content by selected videos. The next phase is improving **retrieval accuracy** through:

1. Better ranking (re-ranking) ← **START HERE**
2. Better embeddings (larger model)
3. Better filtering (relevance threshold)
4. Better context (more grounding info)

**Recommended Priority**: #1 → #3 → #2 → #5 → others

**Expected Combined Impact**: 50-100% improvement in answer accuracy

Would you like me to implement Phase 1 improvements?
