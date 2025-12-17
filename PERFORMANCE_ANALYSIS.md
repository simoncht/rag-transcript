# RAG Pipeline Performance Analysis

**Date**: 2025-12-10
**Issue**: Query response time of 64.7 seconds is too slow
**Query**: "what did bashar said about Self-worth & discernment?"

## Performance Breakdown

### Current Configuration
```env
OLLAMA_MODEL="qwen3-vl:235b-instruct-cloud"  # 235B parameters!
RETRIEVAL_TOP_K=20
ENABLE_RERANKING=True
RERANKING_TOP_K=7
RERANKING_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"
MIN_RELEVANCE_SCORE=0.50
```

### Estimated Time Breakdown (64.7s total)
1. **Query Embedding**: ~0.1s (local sentence-transformer)
2. **Vector Search**: ~0.2s (Qdrant with 20 results)
3. **Reranking**: ~2-5s (cross-encoder on 20 chunks)
4. **Context Building**: ~0.3s (format 5 chunks with metadata)
5. **LLM Generation**: ~60s (235B parameter model, 2544 tokens)
   - **Token generation rate**: ~40 tokens/second (VERY SLOW)

## Primary Bottleneck: LLM Model Size

### Issue
Using `qwen3-vl:235b-instruct-cloud` - a 235 BILLION parameter model:
- **Too large** for real-time responses
- **Cloud variant** may add network latency to Ollama cloud service
- Even on high-end GPUs, 235B models struggle with speed

### Impact
- 60+ seconds per response
- Blocks user interaction
- Poor user experience

## Secondary Bottleneck: Reranking Overhead

### Issue
- Reranking 20 chunks with cross-encoder
- Each (query, chunk) pair requires a forward pass
- Cross-encoders are 10-20x slower than bi-encoders

### Impact
- 2-5 seconds overhead
- Diminishing returns: retrieving 20 but only using top 5

## Recommendations

### 🚀 High-Impact Changes (80-90% speedup)

#### 1. **Switch to Smaller LLM** (CRITICAL)

**Option A: Fast Local Models (2-5s responses)**
```env
# Recommended: qwen2.5-coder 7B (excellent quality, 50x faster)
OLLAMA_MODEL="qwen2.5-coder:7b"

# Alternative: Llama 3 8B (well-tested, very fast)
OLLAMA_MODEL="llama3:8b"

# Alternative: Mistral 7B (good balance)
OLLAMA_MODEL="mistral:7b"
```

**Expected speedup**: 60s → 2-5s for LLM generation (12-30x faster)

**Option B: Cloud APIs (if budget allows, 1-3s responses)**
```env
# OpenAI GPT-4o-mini (fast, cheap, excellent quality)
LLM_PROVIDER="openai"
OPENAI_MODEL="gpt-4o-mini"
OPENAI_API_KEY="your-key"

# Anthropic Claude 3 Haiku (fastest Claude, good quality)
LLM_PROVIDER="anthropic"
ANTHROPIC_MODEL="claude-3-haiku-20240307"
ANTHROPIC_API_KEY="your-key"
```

**Expected speedup**: 60s → 1-3s for LLM generation (20-60x faster)

#### 2. **Optimize Retrieval Pipeline**

```env
# Reduce initial retrieval (still good coverage)
RETRIEVAL_TOP_K=10

# Keep reranking but with fewer candidates
RERANKING_TOP_K=5

# Lower relevance threshold (0.50 is too strict)
MIN_RELEVANCE_SCORE=0.15
```

**Expected speedup**: 2-5s → 0.5-1s for reranking

### 💡 Medium-Impact Changes (10-20% additional speedup)

#### 3. **Make Reranking Optional Per Request**
- Keep reranking for important queries
- Skip for quick exploratory questions
- Add `enable_reranking` flag to API request

#### 4. **Reduce Context Size**
- Currently using top 5 chunks with extensive formatting
- Consider top 3 for simpler queries
- Reduce metadata verbosity

#### 5. **Enable Response Streaming**
- Implement SSE (Server-Sent Events) for progressive display
- User sees tokens as they're generated
- Perceived latency reduced even if total time is same

### 🔍 Low-Impact Optimizations (1-5% speedup)

#### 6. **Embedding Cache Optimization**
- Already using LRU cache (max 1000 items)
- Consider increasing to 5000 for frequent queries

#### 7. **Batch Processing**
- If multiple users query simultaneously
- Batch LLM requests where possible

## Recommended Configuration

### For Development (Fast Iteration)
```env
OLLAMA_MODEL="qwen2.5-coder:7b"
RETRIEVAL_TOP_K=10
ENABLE_RERANKING=False
RERANKING_TOP_K=5
MIN_RELEVANCE_SCORE=0.15
LLM_MAX_TOKENS=1000  # Reduce for faster responses
```

**Expected response time**: 3-7 seconds

### For Production (Quality + Speed Balance)
```env
# Option 1: Local inference
OLLAMA_MODEL="qwen2.5-coder:14b"  # or llama3:13b
RETRIEVAL_TOP_K=15
ENABLE_RERANKING=True
RERANKING_TOP_K=5
MIN_RELEVANCE_SCORE=0.20
LLM_MAX_TOKENS=1500

# Option 2: Cloud inference (recommended)
LLM_PROVIDER="openai"
OPENAI_MODEL="gpt-4o-mini"
RETRIEVAL_TOP_K=15
ENABLE_RERANKING=True
RERANKING_TOP_K=7
MIN_RELEVANCE_SCORE=0.20
```

**Expected response time**:
- Local: 5-10 seconds (still good UX)
- Cloud: 2-4 seconds (excellent UX)

## Testing Plan

### 1. Create Performance Test Script
```python
# backend/tests/test_performance.py
import time
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store_service
from app.services.llm_providers import llm_service

def test_query_performance():
    query = "What did bashar say about self-worth?"

    # Test embedding
    start = time.time()
    embedding = embedding_service.embed_text(query)
    embed_time = time.time() - start

    # Test vector search
    start = time.time()
    chunks = vector_store_service.search_chunks(embedding, top_k=10)
    search_time = time.time() - start

    # Test LLM
    start = time.time()
    response = llm_service.complete([{"role": "user", "content": "Test"}])
    llm_time = time.time() - start

    print(f"Embedding: {embed_time:.2f}s")
    print(f"Search: {search_time:.2f}s")
    print(f"LLM: {llm_time:.2f}s")
    print(f"Total: {embed_time + search_time + llm_time:.2f}s")
```

### 2. Benchmark Different Models
Test with same query on:
- qwen2.5-coder:7b
- llama3:8b
- mistral:7b
- gpt-4o-mini (if API key available)

### 3. A/B Test Reranking
- Compare accuracy with/without reranking
- Measure time saved
- Decide if 2-5s overhead worth the accuracy gain

## Model Availability Check

To see which models are available locally:
```bash
ollama list
```

To pull recommended models:
```bash
ollama pull qwen2.5-coder:7b
ollama pull llama3:8b
ollama pull mistral:7b
```

## Expected Outcomes

### After Switching to 7B Model
- Response time: **64.7s → 5-8s** (8-13x faster)
- Quality: Comparable for most queries
- User experience: Acceptable

### After Full Optimization
- Response time: **64.7s → 2-5s** (13-32x faster)
- Quality: Better (lower threshold catches more relevant chunks)
- User experience: Excellent

### With Streaming (Future Enhancement)
- Perceived latency: **<1s** (first tokens appear immediately)
- Actual time: Same as above
- User experience: Best-in-class

## Next Steps

1. **Immediate**: Change `.env` to use 7B model
2. **Test**: Run same query, measure new time
3. **Iterate**: Adjust other parameters based on results
4. **Monitor**: Add timing logs to track each stage
5. **Implement**: Response streaming for progressive display

## Related Files

- Configuration: `backend/.env`, `backend/app/core/config.py`
- RAG Pipeline: `backend/app/api/routes/conversations.py` (lines 579-949)
- LLM Service: `backend/app/services/llm_providers.py`
- Reranker: `backend/app/services/reranker.py`
- Embeddings: `backend/app/services/embeddings.py`
- Vector Store: `backend/app/services/vector_store.py`
