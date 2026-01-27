# Model Research: DeepSeek API for RAG Transcript

This document summarizes the LLM configuration for the RAG Transcript app, using DeepSeek API for all subscription tiers.

## Model Configuration Summary

| Tier | Model | Context | Max Output | Pricing |
|------|-------|---------|------------|---------|
| Free | `deepseek-chat` | 128K | 8K | $0.28/M in, $0.42/M out |
| Pro | `deepseek-reasoner` | 128K | 64K | $0.28/M in, $0.42/M out |
| Enterprise | `deepseek-reasoner` | 128K | 64K | Same as Pro with SLA |

**Cache pricing**: $0.028/M (10x cheaper for automatic prefix cache hits)

---

## DeepSeek API Overview

### Why DeepSeek?

1. **Cost-effective**: ~10x cheaper than GPT-4 with comparable quality
2. **OpenAI-compatible**: Easy integration with existing code
3. **Automatic caching**: Reduces costs for multi-turn conversations by up to 90%
4. **Reasoning mode**: Chain-of-thought for complex queries (Pro/Enterprise)

### Models

#### `deepseek-chat` (Free Tier)

**Official Documentation**: [api-docs.deepseek.com](https://api-docs.deepseek.com/)

| Spec | Value |
|------|-------|
| Base Model | DeepSeek-V3.2 |
| Mode | Non-thinking (fast) |
| Context Length | 128K tokens |
| Max Output | 8K tokens |
| Pricing (Input) | $0.28/M tokens |
| Pricing (Output) | $0.42/M tokens |
| Cache Hit Pricing | $0.028/M tokens |

**For This App:**
- Fast responses for simple factual queries
- Good for basic transcript Q&A
- Optimized for latency

**Known Limitations:**
- No chain-of-thought reasoning
- May miss nuances in complex multi-source queries

#### `deepseek-reasoner` (Pro/Enterprise)

**Official Documentation**: [DeepSeek Reasoner Guide](https://api-docs.deepseek.com/guides/reasoning_model)

| Spec | Value |
|------|-------|
| Base Model | DeepSeek-V3.2 |
| Mode | Thinking (chain-of-thought) |
| Context Length | 128K tokens |
| Max Output | 64K tokens |
| Pricing (Input) | $0.28/M tokens |
| Pricing (Output) | $0.42/M tokens |
| Cache Hit Pricing | $0.028/M tokens |

**For This App:**
- Advanced reasoning for complex transcript analysis
- Better at synthesizing information from multiple sources
- 64K output enables detailed summaries
- Chain-of-thought provides transparency

**Known Limitations:**
- Slightly slower due to reasoning step
- `reasoning_content` must NOT be included in message history (returns 400 error)

---

## Context Caching

DeepSeek uses **automatic disk-based prefix caching** - no code changes required.

### How It Works

```
Request 1: [System Prompt] + [User Question 1]
                ↓ cached (if ≥64 tokens)

Request 2: [System Prompt] + [Prev Q&A] + [User Question 2]
           └── cache hit ──┘

Request 3: [System Prompt] + [Prev Q&A] + [More Q&A] + [User Question 3]
           └────────── cache hit ───────┘
```

### RAG Transcript Cache Behavior

| Component | Cacheability | Reason |
|-----------|--------------|--------|
| System prompt | **High** | ~200 tokens, identical every request |
| Conversation facts | **High** | Only grows, never changes |
| Conversation history | **High** | Grows incrementally, prefix preserved |
| Retrieved chunks | **Low** | Changes with each query |
| Current query | **None** | Always unique |

### Cost Savings

| Conversation Turn | Cache Hit | Cache Miss | Est. Savings |
|-------------------|-----------|------------|--------------|
| Turn 1 | 0 | 2,500 | 0% |
| Turn 5 | 2,000 | 2,500 | 17% |
| Turn 10 | 4,500 | 2,500 | 29% |
| Turn 15+ | 6,000+ | 2,500 | 38%+ |

**Longer conversations = more savings** because the cached prefix grows while new content stays constant.

---

## API Integration Notes

### OpenAI Compatibility

DeepSeek uses an OpenAI-compatible API:

```python
import openai

client = openai.OpenAI(
    api_key="your-api-key",
    base_url="https://api.deepseek.com/v1"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[...],
)
```

### Reasoner Response Handling

**Critical**: The `deepseek-reasoner` model returns `reasoning_content` which must NOT be passed back in subsequent messages:

```python
# Response from deepseek-reasoner
response.choices[0].message = {
    "role": "assistant",
    "content": "Final answer here",           # ✅ Include in history
    "reasoning_content": "Chain of thought"   # ❌ NEVER include in history
}
```

The RAG Transcript codebase handles this in `llm_providers.py`:
- `reasoning_content` is extracted for logging
- Only `content` is stored in message history

### Usage Metrics

The API response includes cache performance:

```python
response.usage = {
    "prompt_tokens": 3000,
    "completion_tokens": 500,
    "prompt_cache_hit_tokens": 500,   # Cached (cheap)
    "prompt_cache_miss_tokens": 2500, # Not cached (normal price)
}
```

---

## Previous Model Research (Archive)

### Previous Ollama-based Configuration

Before migrating to DeepSeek API, the app used local Ollama models:

| Tier | Model | Notes |
|------|-------|-------|
| Free | GPT-OSS 120B | 5.1B active MoE params |
| Pro | Qwen3-VL 235B | 256K context, RAG optimized |
| Enterprise | Qwen3-VL 235B | Same as Pro |

**Reasons for migration:**
1. **Operational simplicity**: No local GPU/Ollama required
2. **Cost predictability**: Pay-per-use vs. infrastructure costs
3. **Reliability**: API uptime vs. self-managed infrastructure
4. **Scalability**: No need to scale local hardware

### Model Selection Rationale

| Criterion | DeepSeek Chat | DeepSeek Reasoner |
|-----------|---------------|-------------------|
| Context Length | 128K | 128K |
| RAG Suitability | High | **High** |
| Speed | **Fast** | Medium |
| Transcript Understanding | Good | **Excellent** |
| Complex Reasoning | Good | **Excellent** |
| Cost | **Low** | **Low** |

---

## Configuration

### Environment Variables

```bash
# Provider (must be "deepseek")
LLM_PROVIDER="deepseek"

# API Configuration
DEEPSEEK_API_KEY="sk-your-api-key"
DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
DEEPSEEK_MODEL="deepseek-chat"

# Tier-specific models
LLM_MODEL_FREE="deepseek-chat"
LLM_MODEL_PRO="deepseek-reasoner"
LLM_MODEL_ENTERPRISE="deepseek-reasoner"
```

### Code Reference

- `backend/app/services/llm_providers.py` - DeepSeekProvider class
- `backend/app/core/config.py` - Environment variable mappings
- `backend/app/core/pricing.py` - MODEL_TIERS dictionary
- `backend/app/api/routes/conversations.py` - Cache monitoring logging

---

## Verification Steps

1. **Test API connectivity**:
   ```bash
   curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"
   ```

2. **Test chat completion**: Send test message, verify response

3. **Test reasoner mode**: Send complex query to Pro tier user, verify reasoning

4. **Test caching**: Check `prompt_cache_hit_tokens` in logs after multi-turn conversation

5. **Monitor costs**: Check DeepSeek dashboard for usage

---

## Sources

- [DeepSeek API Documentation](https://api-docs.deepseek.com/)
- [DeepSeek Multi-Round Chat Guide](https://api-docs.deepseek.com/guides/multi_round_chat)
- [DeepSeek Reasoner Guide](https://api-docs.deepseek.com/guides/reasoning_model)
- [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache)
- [DeepSeek Pricing](https://api-docs.deepseek.com/quick_start/pricing)
