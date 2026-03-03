# RAG Architecture: Full-Spectrum Analysis vs. Industry & Academic State-of-the-Art

**Date:** 2026-03-01
**System:** RAG Transcript (YouTube video knowledge base)
**Methodology:** Component-by-component comparison against 40+ academic papers, industry whitepapers from Anthropic, OpenAI, Google, Microsoft, Meta, and production frameworks from LlamaIndex, LangChain, Cohere, NVIDIA, Pinecone, Qdrant, Weaviate.

---

## Rating Scale

| Rating | Meaning |
|--------|---------|
| **A** | At or above SOTA. Aligned with best practices, well-optimized |
| **B** | Solid implementation. Minor gaps vs. SOTA, easily upgradeable |
| **C** | Functional but significant gap vs. SOTA. Clear upgrade path |
| **D** | Below baseline. Missing key capabilities that research considers essential |

---

## Executive Summary

| Component | Our Rating | SOTA Alignment |
|-----------|-----------|----------------|
| Chunking | **B+** | Semantic boundaries, good size — missing adaptive sizing |
| Embedding Model | **C** | all-MiniLM-L6-v2 is dated; 10+ pts below SOTA on MTEB |
| Contextual Enrichment | **A-** | Directly implements Anthropic's pattern with cost optimization |
| Hybrid Search (BM25 + Vector) | **B** | Enabled and functional — RRF weights could be tuned |
| Query Expansion | **A-** | Clean RAG-Fusion implementation, well-calibrated |
| Reranking | **B-** | BGE-reranker-base is entry-level; SOTA is 5x larger |
| Self-RAG | **B** | Implemented with 4 corrective actions — disabled by default |
| HyDE | **B** | Implemented with intent routing — disabled by default |
| MMR Diversity | **A-** | Adaptive lambda per video count; above typical implementations |
| Conversation Memory | **B-** | Functional extraction/scoring — junk facts, no updates, no consolidation |
| Citation System | **B** | Inline citations with timestamps — `was_used` tracking broken |
| Retrieval Depth | **C** | top_k=10 is far below industry 50-150 candidate pool |
| Context Ordering | **D** | No explicit ordering strategy; "Lost in the Middle" unaddressed |
| Evaluation Framework | **B** | Retrieval metrics solid — missing generation quality metrics |
| Hierarchical Retrieval | **D** | Not implemented; planned but critical for 50+ video collections |
| LLM Cost Optimization | **A** | DeepSeek cache exploitation + tier routing is excellent |
| Infrastructure | **A-** | Full Docker stack, Celery pipeline, proper separation of concerns |

**Overall System Grade: B**
Strong architecture with most SOTA components implemented. Three critical gaps: embedding model age, retrieval depth, and context ordering. The system is ahead of most production RAG deployments in having Self-RAG, HyDE, and query expansion built (even if some are disabled).

---

## 1. CHUNKING

### Our Implementation
- **Algorithm:** Token-aware semantic chunking with sentence boundary detection
- **Target:** 512 tokens (env override from default 256)
- **Min/Max:** 16 / 800 tokens
- **Overlap:** 80 tokens (~15.6% of target)
- **Boundaries:** Sentence splits, speaker changes, YouTube chapter awareness
- **Tokenizer:** OpenAI `cl100k_base` (tiktoken)

### What Research Says
- **"Searching for Best Practices in RAG"** (arXiv 2407.01219, July 2024): Optimal chunk size = 512 tokens. Sliding window at 97.41% faithfulness.
- **NVIDIA Chunking Benchmark** (2024): Factoid queries optimal at 256-512 tokens; analytical queries need 1024+. Page-level chunking had lowest variance (0.107 SD).
- **Chroma Research** (July 2024): LLM-based semantic chunking achieved 91.9% recall (highest). Chunking strategy impacts retrieval by up to 9%.
- **Pinecone**: 256-512 for factoid, 1024+ for analytical. 10-20% overlap recommended.
- **Dense-X / Proposition Chunking** (Chen et al., EMNLP 2024): Atomic, self-contained propositions outperform fixed-size passages.

### Rating: **B+**
| Aspect | Assessment |
|--------|-----------|
| Chunk size (512) | Matches academic optimal for factoid queries |
| Overlap (15.6%) | Within 10-20% recommendation |
| Semantic boundaries | Sentence + speaker + chapter awareness — above average |
| Adaptive sizing | Missing — analytical queries may benefit from larger chunks |
| Proposition chunking | Not implemented — SOTA trend but high complexity |

### Gap
No adaptive chunk sizing based on content type. Research shows analytical queries need 1024+ tokens. For long philosophical speeches (Alan Watts lectures), larger chunks may preserve context better. Consider a two-tier approach: 512 for factual content, 1024 for philosophical/narrative content.

---

## 2. EMBEDDING MODEL

### Our Implementation
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions:** 384
- **Parameters:** 22M
- **MTEB Score:** ~56 (estimated)
- **Query prefix:** None (symmetric model)

### What Research Says

**MTEB Leaderboard (2025):**

| Model | MTEB Avg | Retrieval | Dims | Params |
|-------|---------|-----------|------|--------|
| NV-Embed-v2 | 72.3 | 62.7 | 4096 | 7.8B |
| Cohere embed-v4 | 65.2 | — | 1024 | — |
| OpenAI text-3-large | 64.6 | 55.4 | 3072 | — |
| BGE-M3 | 63.0 | — | 1024 | 568M |
| BGE-base-en-v1.5 | 63.5 | 53.3 | 768 | 110M |
| **all-MiniLM-L6-v2** | **~56** | **~47** | **384** | **22M** |

- **OpenAI** (Jan 2024): text-embedding-3-small at 62.3% MTEB, 5x cheaper than ada-002. Matryoshka dimension reduction: 256-dim truncation of 3-large outperforms full 1536-dim ada-002.
- **BGE-base-en-v1.5**: 768 dims, 110M params, asymmetric query prefix. ~7 MTEB points above MiniLM.
- **NV-Embed-v2** (Lee et al., ICLR 2025): #1 MTEB (72.31), #1 retrieval (62.65). LLM-based architecture.

### Rating: **C**
| Aspect | Assessment |
|--------|-----------|
| Model age | MiniLM-L6-v2 is from 2021 — 5 years old in a fast-moving field |
| MTEB gap | ~7-16 points below current competitive models |
| Retrieval gap | ~6-16 points below SOTA on retrieval benchmarks |
| Asymmetric search | Not supported (symmetric model); BGE models use query prefixes for better retrieval |
| Cost efficiency | Excellent — runs locally, no API costs |
| Dimensions | 384 is on the small side; 768-1024 is the current sweet spot |

### Recommended Upgrade Path
1. **Quick win:** Switch to BGE-base-en-v1.5 (768d, 110M params). Already in codebase as alternative. +7 MTEB points, still runs locally. Requires re-embedding.
2. **Best value:** BGE-M3 (1024d, 568M params). Multilingual, strong retrieval. +7 MTEB points over BGE-base.
3. **If API OK:** OpenAI text-embedding-3-small (1536d). 62.3% MTEB, $0.00002/1K tokens.

**This is the single highest-impact upgrade available.** Embedding quality is the foundation — every downstream component (search, reranking, MMR) operates on these vectors.

---

## 3. CONTEXTUAL ENRICHMENT

### Our Implementation
- Full document text passed to LLM with each chunk for enrichment
- Generates: title (3-7 words), summary (1-3 sentences), keywords (3-7 terms)
- Embedding text: `"{title}. {summary}\n\n{chunk.text}"`
- DeepSeek cache optimization: system+transcript static per video (10x cost reduction for cache hits)
- Max context: 48K chars (~12K tokens)
- Batch size: 10, max workers: 20

### What Research Says
- **Anthropic "Contextual Retrieval"** (Sept 2024): Prepending chunk-specific context reduced retrieval failure by 35% (embeddings alone) to 67% (with BM25 + reranking). Uses 800-token chunks, 8K-token documents. Cost: $1.02/M document tokens with prompt caching.
- **Late Chunking** (Jina AI, Sept 2024): Embed full document, then chunk after transformer. 12% improvement over fixed-size. No LLM cost, but requires long-context embedding model.
- **Merola & Singh** (April 2025): Contextual retrieval > late chunking for semantic coherence; late chunking > contextual for efficiency.

### Rating: **A-**
| Aspect | Assessment |
|--------|-----------|
| Pattern | Directly implements Anthropic's contextual retrieval |
| Cost optimization | DeepSeek cache is smart — mirrors Anthropic's prompt caching recommendation |
| Enrichment quality | Title + summary + keywords per chunk — comprehensive |
| Embedding text construction | Prepends enrichment to chunk text — correct pattern |
| 48K char limit | Silent truncation for very long videos — PAR-002 broken contract |
| BM25 indexing | BM25 may not index enriched text (only raw) — Anthropic applies context to both |

### Gap
Verify that BM25 indexes the enriched text (title + summary + chunk), not just raw chunk text. Anthropic's results show Contextual BM25 provides additional gains beyond Contextual Embeddings alone (49% vs 35% failure reduction).

---

## 4. HYBRID SEARCH (BM25 + VECTOR)

### Our Implementation
- **BM25:** Enabled (`enable_bm25_search=True`)
- **Fusion:** Reciprocal Rank Fusion (RRF)
- **RRF constant:** k=60
- **Weights:** Vector=1.0, BM25=0.3
- **BM25 constraints:** min_normalized_score=0.25, min_term_overlap=2, max_unique_chunks=3

### What Research Says
- **Anthropic**: Hybrid (Contextual Embeddings + Contextual BM25) reduced failure by 49% vs 35% for embeddings alone.
- **Microsoft Azure AI Search** (2024): Hybrid + Semantic Ranker achieved NDCG@3=60.1 vs 43.8 for vector-only (+37%).
- **Bruch et al.** (ACM TOIS, 2024): Convex Combination (CC) **outperforms RRF** in both in-domain and out-of-domain. CC is sample-efficient and agnostic to score normalization.
- **Weaviate**: Hybrid search boosts RAG accuracy 20-30%.
- **Industry consensus:** Hybrid search is universally recommended. No major vendor recommends pure vector search for production RAG.

### Rating: **B**
| Aspect | Assessment |
|--------|-----------|
| BM25 enabled | Aligned with universal recommendation |
| RRF fusion | Standard approach — but CC outperforms per Bruch 2024 |
| BM25 weight (0.3) | Conservative; typical range 0.3-0.5 |
| max_unique_chunks=3 | Very restrictive — may discard good BM25-only matches |
| Term overlap filter | Good for precision, may hurt recall on paraphrased content |

### Gaps
1. Consider Convex Combination fusion (Bruch 2024 shows superiority over RRF)
2. `max_unique_chunks=3` from BM25 is very conservative — consider raising to 5-7
3. Verify BM25 indexes enriched text, not just raw chunks

---

## 5. QUERY EXPANSION

### Our Implementation
- **Enabled:** Yes (default)
- **Variants:** 2 query reformulations + original
- **LLM temperature:** 0.3
- **Min words to expand:** 6 (skip short queries)
- **Fusion:** Max-score across variants
- **Latency overhead:** ~1s

### What Research Says
- **RAG-Fusion** (Rackauckas, arXiv 2402.03367, Feb 2024): Core pattern — LLM generates multiple query variations, RRF merges results. "Provided accurate and comprehensive answers by contextualizing queries from various perspectives."
- **LangChain Multi-Query Retriever**: 2-3 reformulations standard. Top-6 most used retrieval strategy in their State of AI survey.
- **UniRAG** (ACL 2025): Unified query expansion approaches for RAG.
- **RQ-RAG** (2024): Decomposes multi-hop queries into sub-questions.

### Rating: **A-**
| Aspect | Assessment |
|--------|-----------|
| Pattern | Clean RAG-Fusion implementation |
| Variant count (2) | Matches recommended 2-3 |
| Temperature (0.3) | Good — low enough for consistency, high enough for variety |
| Short-query skip | Smart optimization — 6-word minimum prevents wasted LLM calls |
| Max-score fusion | Effective; literature also supports RRF fusion |
| Latency (~1s) | Acceptable; literature confirms 20-30% recall improvement justifies this |

### Minor Enhancement
Consider sub-question decomposition for complex multi-hop queries (RQ-RAG pattern). E.g., "How does Speaker A's view on X compare to Speaker B's view?" → decompose into two sub-queries.

---

## 6. RERANKING

### Our Implementation
- **Model:** `BAAI/bge-reranker-base` (110M params, cross-encoder)
- **Config default:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (code default)
- **Top-K after reranking:** 5 (env) / 7 (code default)
- **Score normalization:** Min-max to 0-1 range

### What Research Says

| Reranker | Params | Architecture | Quality |
|----------|--------|-------------|---------|
| **bge-reranker-base** | 110M | Cross-encoder | Entry-level |
| bge-reranker-large | 560M | Cross-encoder | Moderate |
| **bge-reranker-v2-m3** | 0.6B | Cross-encoder + LoRA | Strong (MIRACL 69.32) |
| Cohere Rerank 3.5 | — | Cross-encoder | SOTA on BEIR (+23.4% over hybrid) |
| Jina-ColBERT-v2 | — | Late interaction | +6.5% over ColBERT-v2, fast |
| monoT5 | 220M-3B | Sequence-to-sequence | Best quality per "Best Practices" paper |

- **"Searching for Best Practices in RAG"** (arXiv 2407.01219): monoT5 achieves best quality; TILDEv2 best speed. Reranking is one of the highest-impact components.
- **Cohere**: Reranking adds +20% accuracy. Rerank 3.5 handles 4K context for long documents.
- **Meta AI production pattern**: Retrieve 100 → rerank top 30-50 → return top 5-10.

### Rating: **B-**
| Aspect | Assessment |
|--------|-----------|
| Architecture | Cross-encoder — correct approach |
| Model quality | bge-reranker-base is the weakest BGE reranker (110M) |
| Candidate pool | Reranks only ~10 candidates (see Retrieval Depth) |
| Top-K output (5) | Reasonable final context size |
| Normalization | Min-max is simple but functional |
| Graceful degradation | Falls back to original order if model fails — good |

### Recommended Upgrade
Switch to `bge-reranker-v2-m3` (0.6B params). MIRACL 69.32, multilingual, LoRA fine-tuned. ~5x compute cost of base but significant quality improvement. Still runs locally.

---

## 7. SELF-RAG (RELEVANCE GRADING)

### Our Implementation
- **Enabled:** Configurable (`enable_relevance_grading`), enabled in config
- **Grading:** RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT per chunk
- **Sufficiency threshold:** ≥50% chunks RELEVANT
- **Corrective actions:** REFORMULATE, EXPAND_SCOPE, SUMMARY_FALLBACK, INSUFFICIENT
- **Efficiency:** Single batched LLM call for all chunks

### What Research Says
- **Self-RAG** (Asai et al., NeurIPS 2023 / ICLR 2024): Self-RAG outperformed ChatGPT on open-domain QA. 81% fact-checking accuracy vs 71% baseline. Adaptive retrieval: model decides when to retrieve.
- **"Agentic RAG" Survey** (arXiv 2501.09136, Jan 2025): Autonomous agents with reflection, planning, and tool use in RAG.
- **PFE-SELF-RAG** (2024): MMR + Self-RAG for diversity-aware relevance grading.

### Rating: **B**
| Aspect | Assessment |
|--------|-----------|
| Implementation | 4 corrective actions — more than typical binary relevant/irrelevant |
| Batched grading | Smart — single LLM call instead of N calls |
| Sufficiency threshold (50%) | Reasonable |
| Corrective actions | REFORMULATE and EXPAND_SCOPE go beyond standard Self-RAG |
| Default state | Disabled by default — should be enabled for factual tasks |
| Adaptive retrieval | Not implemented — SOTA decides when to retrieve at all |

### Gap
Self-RAG's biggest insight is **adaptive retrieval** — deciding whether retrieval is needed at all. For off-topic questions (Turn 24 in our test: "first video on YouTube?"), the system could skip retrieval entirely and respond from parametric knowledge. This would save latency and avoid "not mentioned in transcripts" responses.

---

## 8. HyDE (HYPOTHETICAL DOCUMENT EMBEDDINGS)

### Our Implementation
- **Enabled:** Configurable (`enable_hyde`), enabled in config
- **Trigger:** Coverage and hybrid intent queries
- **Generation:** 3-5 sentence hypothetical passage
- **Temperature:** 0.7
- **Fusion:** Additional retrieval vector via max-score

### What Research Says
- **HyDE** (Gao et al., ACL 2023): Significantly outperforms unsupervised dense retrievers. Comparable to fine-tuned retrievers in zero-shot settings.
- **When HyDE helps:** Zero-shot retrieval, large query-document gap, coverage/summary queries.
- **When HyDE hurts:** Factual domains (hallucination risk), small LLMs (25-60% latency increase), high query-document similarity already.
- **Best practice:** Use hybrid policy — HyDE only when similarity confidence is low.

### Rating: **B**
| Aspect | Assessment |
|--------|-----------|
| Implementation | Clean — intent-routed, not always-on |
| Intent routing | Correct — coverage queries get HyDE, factual queries skip |
| Temperature (0.7) | Standard for creative generation |
| Default state | Disabled — should enable for coverage/summary queries |
| Hallucination guard | No explicit post-validation of hypothetical passage |

### Gap
Add a confidence gate: only use HyDE vector when standard retrieval confidence is low (e.g., top-1 cosine similarity < 0.4). This avoids HyDE overhead when standard search already has high-confidence matches.

---

## 9. MMR DIVERSITY

### Our Implementation
- **Formula:** `λ × relevance - (1-λ) × max_similarity_to_selected`
- **Adaptive lambda:** 0.3-0.5 (single video), 0.5-0.7 (multi-video)
- **Prefetch:** 100 candidates for MMR
- **Proximity penalty:** Same-source base similarity 0.7 + 0.3 × proximity; cross-source 0.1
- **Video guarantee search:** Two-phase: best chunk per video, then MMR fill

### What Research Says
- **Carbonell & Goldstein** (ACM SIGIR 1998): Original MMR. Lambda balances relevance vs diversity.
- **SMMR** (ACM SIGIR 2025): Probabilistic sampling > deterministic greedy MMR. Better relevance-diversity tradeoff.
- **VRSD** (arXiv 2024): Alternative to MMR with superior vector information utilization.

### Rating: **A-**
| Aspect | Assessment |
|--------|-----------|
| Adaptive lambda | Above typical implementations — context-aware is correct |
| Video guarantee | Novel feature for multi-source RAG — ensures cross-video coverage |
| Prefetch pool (100) | Good candidate pool for MMR selection |
| Proximity penalty | Smart — penalizes nearby chunks from same video (30s buckets) |
| Cross-source base (0.1) | Effectively treats cross-video chunks as highly diverse |

### Minor Enhancement
Consider SMMR's probabilistic approach (SIGIR 2025) if deterministic greedy MMR produces too-similar results in large collections.

---

## 10. CONVERSATION MEMORY

### Our Implementation
- **Extraction:** LLM-based fact extraction after every turn (async)
- **Categories:** identity, preference, topic, session, ephemeral
- **Injection threshold:** Facts injected when message_count >= 10
- **Scoring:** Multi-factor (importance 0.30, query relevance 0.25, recency 0.15, category 0.15, source turn 0.15)
- **Selection limit:** 15 facts per message (non-streaming: 25)
- **Consolidation:** Offline only (Celery beat), never inline
- **Update behavior:** New keys created, never updates existing values (MEM-004)

### What Research Says
- **MemGPT** (Packer et al., UC Berkeley, Oct 2023): OS-inspired hierarchical memory — core (in-context), archival (external), recall (conversation search). Uses interrupts for control flow. Open-sourced as Letta.
- **Mem0** (arXiv 2504.19413, April 2025): Production-oriented. Dynamic extraction + consolidation + retrieval. **Update phase evaluates extracted memories against existing ones via Tool Call mechanism.** 26% improvement over OpenAI, 91% lower p95 latency, 90%+ token cost savings.
- **A-MEM** (Xu et al., NeurIPS 2025): Zettelkasten-inspired. Dynamic memory structuring, linking based on similarities. **Memory evolution: new memories trigger updates to existing memories.**
- **Reflexion** (Shinn et al., NeurIPS 2023): Verbal self-reflection stored in episodic memory. Induces better decisions in subsequent trials.

### Rating: **B-**
| Aspect | Assessment |
|--------|-----------|
| Extraction | Functional — but extracts junk (~30% low-value facts) |
| Multi-factor scoring | Above average — query relevance embedding is a strong feature |
| Category prioritization | Good — identity > topic > preference > session |
| MEM-004 (no updates) | **Critical gap** — both Mem0 and A-MEM implement memory evolution |
| MEM-003 (no inline consolidation) | **Significant gap** — 95 facts by Turn 25 with only 25 selected |
| Junk extraction | System metadata, generic wisdom clog fact slots |
| Dead zone | history_limit=10, threshold=15 creates a gap |
| Fact embedding cache | Smart — immutable facts cached for fast relevance scoring |

### Key Gaps vs. SOTA
1. **Memory evolution (MEM-004):** Mem0 and A-MEM both update existing memories when new information contradicts old. Our system creates duplicate facts instead.
2. **Inline consolidation (MEM-003):** Mem0 consolidates during extraction, not just offline. At 95 facts, 74% are never seen per turn.
3. **Extraction quality:** Need negative examples in prompt to prevent extracting system metadata, suggested follow-ups, and generic wisdom as facts.
4. **Hierarchical memory:** MemGPT's three-tier model (core/archival/recall) is more sophisticated than our flat fact store.

---

## 11. CITATION SYSTEM

### Our Implementation
- **Format:** `[1]`, `[2]`, `[3]` inline markers
- **Max references per response:** 4
- **Metadata:** Channel name, chapter title, speakers, timestamp
- **Jump URLs:** Navigate to exact YouTube timestamp
- **Deduplication:** 30-second buckets
- **Tracking:** `message_chunk_references` table with relevance scores
- **Known bug:** `was_used_in_response` always True, never updated (CIT-001)

### What Research Says
- **GaRAGe Benchmark** (Amazon Science, ACL 2025): SOTA LLMs achieve at most 60% Relevance-Aware Factuality, 58.9% F1 on attribution. Models tend to over-summarize rather than strictly ground.
- **FACTUM** (arXiv, Jan 2026): Mechanistic citation hallucination detection. Outperforms baselines by 37.5% AUC.
- **Stanford Legal RAG Study** (2025): Two-dimensional evaluation: correctness + groundedness.
- **"Semantic Illusion"** (arXiv, Dec 2025): Embedding similarity alone is insufficient for hallucination detection.

### Rating: **B**
| Aspect | Assessment |
|--------|-----------|
| Inline citations | Standard and expected |
| Jump-to-timestamp | Excellent UX — rare in competitors |
| Max 4 references | Conservative; could be higher for multi-source queries |
| Deduplication (30s) | Smart — prevents adjacent chunk flooding |
| was_used tracking | Broken (CIT-001) — all sources marked as used |
| Hallucination detection | Not implemented — GaRAGe shows even SOTA struggles here |
| Citation validation | Validates reference bounds but not factual accuracy |

### Gap
Implement actual `was_used_in_response` tracking by checking if generated text contains claims from each cited chunk. Even simple string overlap would be better than always-True.

---

## 12. RETRIEVAL DEPTH (CRITICAL GAP)

### Our Implementation
- **retrieval_top_k:** 20
- **Per query variant:** 20 candidates
- **With 3 variants:** ~60 total candidates (before dedup)
- **After reranking:** Top 7
- **Adaptive chunk limit:** 4-12 based on video count

### What Research Says
- **Anthropic:** Retrieves top-150, reranks to top-20. *"Retrieve broad, rerank narrow."*
- **"Searching for Best Practices in RAG"**: Initial retrieval top-50.
- **Meta AI production pattern:** Retrieve 100 → rerank 30-50 → return 5-10.
- **Microsoft Azure:** 512-token chunks with broad retrieval achieved 62% better recall than narrow.
- **Industry consensus:** 50-150 candidate pool for reranking. Rerankers are most effective when they have a large, noisy pool to filter.

### Rating: **C**
| Aspect | Assessment |
|--------|-----------|
| top_k=10 per variant | Far below industry 50-150 recommendation |
| Total pool (~30) | Below minimum recommended (50) |
| Reranker starved | BGE-reranker-base works best with larger candidate pools |
| With multi-query | Partially compensates — 3 × 10 = 30, but with significant overlap |

### Recommended Fix
Increase `RETRIEVAL_TOP_K` to 30-50 per variant. With 3 query variants, this gives 90-150 candidates (before dedup), aligned with Anthropic's recommendation. The reranker then narrows to top 5-7 with much better selection quality.

**This is the second highest-impact change after embedding model upgrade.**

---

## 13. CONTEXT ORDERING (CRITICAL GAP)

### Our Implementation
- No explicit ordering strategy for chunks in the LLM prompt
- Chunks appear to be ordered by relevance score (descending)

### What Research Says
- **"Lost in the Middle"** (Liu et al., TACL 2024): LLMs exhibit U-shaped attention — performance degrades 30%+ when relevant information is in the middle of context. Rotary position embeddings (RoPE) cause this.
- **"Searching for Best Practices in RAG"** (arXiv 2407.01219): **Reverse ordering** (most relevant closest to the query, at the end) outperformed all other strategies.
- **Microsoft:** Query rewriting + context ordering contributed +22 NDCG@3 points.

### Rating: **D**
| Aspect | Assessment |
|--------|-----------|
| Ordering strategy | None explicit |
| "Lost in the Middle" mitigation | Not addressed |
| Research recommendation | Reverse order (ascending relevance, most relevant last / closest to query) |

### Recommended Fix
Reverse the chunk order in the context prompt so the most relevant chunk appears last (closest to the query/instruction). This is a zero-cost change with potential 10-30% quality improvement.

---

## 14. EVALUATION FRAMEWORK

### Our Implementation
- **Retrieval:** Recall@K, NDCG@K, MRR
- **Answer quality:** LLM-as-judge (faithfulness, relevance, completeness)
- **Golden dataset structure:** Queries with expected chunks, videos, answer keywords
- **Skill:** `/rag-eval` with baseline/compare modes

### What Research Says
- **RAGAS** (Es et al., EACL 2024): Reference-free evaluation. Faithfulness, Answer Relevance, Context Relevance. Most widely adopted framework.
- **ARES** (Saad-Falcon et al., NAACL 2024): Trained LM judges + Prediction-Powered Inference. 59.3% improvement over RAGAS in context relevance.
- **RAG Evaluation Survey** (arXiv 2504.14891, April 2025): Comprehensive survey covering system performance, factual accuracy, safety, computational efficiency.

### Rating: **B**
| Aspect | Assessment |
|--------|-----------|
| Retrieval metrics | Recall@K, NDCG, MRR — standard and complete |
| LLM-as-judge | Implemented (faithfulness, relevance, completeness) |
| Golden dataset | Structured with expected chunks/videos — good |
| Context Relevance | Not measured — RAGAS considers this critical |
| Hallucination rate | Not tracked as a metric |
| Attribution F1 | Not measured — GaRAGe benchmark considers this essential |
| Automated pipeline | Manual invocation only — no CI/CD integration |

### Gap
Add Context Precision/Relevance metric (measures noise in retrieved context). Consider ARES-style trained judges for more reliable evaluation than prompt-based RAGAS.

---

## 15. HIERARCHICAL RETRIEVAL

### Our Implementation
- Not implemented
- Planned in CLAUDE.md (two-level: video summaries + chunks)
- RAPTOR noted as future consideration

### What Research Says
- **RAPTOR** (Sarthi et al., Stanford, ICLR 2024): Recursive clustering + summarization tree. +20% absolute accuracy on QuALITY benchmark. Effective for cross-document understanding.
- **LlamaIndex**: Two-level hierarchy (document summaries + chunks) as pragmatic production alternative to full RAPTOR.
- **GraphRAG** (Microsoft, April 2024): Entity knowledge graphs with hierarchical community summaries. Standard RAG fails on global/sensemaking queries.

### Rating: **D**
| Aspect | Assessment |
|--------|-----------|
| Implementation | Not built |
| Impact | Critical for 50+ video collections (~12% video coverage per query currently) |
| Video summaries | Not generated during processing pipeline |
| Query routing | No distinction between collection-level and specific queries |

### Recommendation
Priority implementation for collection-level queries. Two-level approach (CLAUDE.md plan) is the right path. Add `summary` and `key_topics` columns to `videos` table, generate at end of processing pipeline, route "summarize" and "what themes" queries to video-level summaries.

---

## 16. LLM COST OPTIMIZATION

### Our Implementation
- **DeepSeek API:** $0.28/M input, $0.42/M output
- **Cache exploitation:** System+transcript static per video → $0.028/M for cache hits (10x savings)
- **Tier routing:** Free=deepseek-chat, Pro=deepseek-reasoner
- **Enrichment optimization:** Full transcript in system message (cached), chunk in user message (varies)
- **Reasoning content handling:** Extracted for logging, excluded from message history (prevents 400 errors)

### What Research Says
- **Anthropic:** Prompt caching recommended for contextual retrieval. $1.02/M document tokens.
- **OpenAI:** Batching, caching, and model tiering for cost management.
- **Industry trend:** Smaller, specialized models for specific tasks (embedding, reranking) with large models for generation only.

### Rating: **A**
| Aspect | Assessment |
|--------|-----------|
| DeepSeek pricing | 5-10x cheaper than OpenAI/Anthropic for generation |
| Cache strategy | Excellent — static transcript in system message maximizes cache hits |
| Tier routing | Smart — cheaper model for simple queries, reasoner for complex |
| Enrichment batching | Parallel workers with retry logic |
| Reasoning handling | Correct — prevents 400 errors from including thinking tokens |

---

## 17. INFRASTRUCTURE & PIPELINE

### Our Implementation
- **7 Docker containers:** postgres, redis, qdrant, app, worker, beat, frontend
- **Task pipeline:** Celery with Redis broker, proper visibility timeout (5h)
- **Processing stages:** download → transcribe → chunk → enrich → embed → index
- **Status tracking:** pending → downloading → transcribing → chunking → enriching → indexing → completed
- **Cancellation:** Graceful with cleanup checkpoints between stages
- **Scheduled tasks:** Stale cleanup (hourly), orphan files (6h), quota reconciliation (daily)
- **Rate limiting:** SlowAPI with shared limiter

### What Research Says
- **NVIDIA RAG Blueprint:** Docker deployment, Kubernetes support, guardrailing.
- **Production RAG patterns:** Async processing, job queuing, graceful degradation.
- **Meta AI:** Target latency budget: embed 20ms, ANN search 80ms, rerank 50ms, prompt build 50ms, first-token 250ms.

### Rating: **A-**
| Aspect | Assessment |
|--------|-----------|
| Container architecture | Clean separation of concerns |
| Task pipeline | Celery with proper long-task handling (5h visibility timeout) |
| Cancellation/cleanup | Graceful with checkpoints — above average |
| Scheduled maintenance | Stale detection, orphan cleanup, quota reconciliation — comprehensive |
| Idempotency | Redis dedup lock prevents re-processing |
| Latency | ~4s average (vs Meta's 250ms first-token target) — expected for full pipeline |
| Guardrails | Not implemented — NVIDIA Blueprint includes these |

---

## Cross-Cutting Analysis

### What We Do Better Than Most Production RAG Systems
1. **Multiple retrieval strategies implemented:** Query expansion + BM25 hybrid + reranking + Self-RAG + HyDE. Most production systems have 1-2 of these.
2. **Contextual enrichment with cost optimization:** DeepSeek caching mirrors Anthropic's recommendation.
3. **Adaptive MMR with video-guarantee search:** Novel for multi-source RAG.
4. **Conversation memory with multi-factor scoring:** More sophisticated than simple recency-based approaches.
5. **Citation jump URLs to exact timestamps:** Rare even in commercial products.

### What SOTA Systems Do That We Don't
1. **Hierarchical/GraphRAG for global queries** (Microsoft GraphRAG, RAPTOR)
2. **Memory evolution** — updating existing facts (Mem0, A-MEM)
3. **Adaptive retrieval** — deciding when retrieval is needed (Self-RAG's core insight)
4. **Context ordering** — "Lost in the Middle" mitigation
5. **Guardrails** — input/output safety checks (NVIDIA Blueprint)
6. **Proposition-based chunking** — atomic fact units (Dense-X)

### Configuration Values (verified Mar 2026)
| Setting | .env.example | Code Default | Status |
|---------|-------------|-------------|--------|
| chunk_target_tokens | 256 | 256 | Aligned |
| embedding_model | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | Aligned (BGE code-ready, not deployed) |
| reranking_model | (not set) | bge-reranker-base | Aligned |
| retrieval_top_k | 20 | 20 | Aligned |
| reranking_top_k | 7 | 7 | Aligned |

---

## Priority Upgrade Roadmap

### Tier 1: High Impact, Low Effort
| Change | Effort | Expected Impact | Source |
|--------|--------|----------------|--------|
| Reverse context ordering | 1 line | +10-30% answer quality | "Lost in the Middle" (Liu 2024) |
| Increase retrieval_top_k to 30-50 | Config change | +15-25% recall | Anthropic, Meta AI, "Best Practices" paper |
| Raise reranking_top_k to 7-10 | Config change | Better final context selection | Industry consensus |
| Raise max citations to 6-8 | Config change | Better multi-source coverage | GaRAGe benchmark |

### Tier 2: High Impact, Moderate Effort
| Change | Effort | Expected Impact | Source |
|--------|--------|----------------|--------|
| Upgrade embedding to BGE-base-en-v1.5 | Re-embed all + config | +7 MTEB points (~15% retrieval improvement) | MTEB leaderboard |
| Upgrade reranker to bge-reranker-v2-m3 | Config + memory check | Significant precision improvement | BGE benchmarks |
| Fix memory extraction quality | Prompt engineering | -30% junk facts, better slot utilization | Mem0 pattern |
| Implement fact value updates (MEM-004) | ~100 LOC in fact_extraction.py | Correct user context over time | Mem0, A-MEM |

### Tier 3: High Impact, High Effort
| Change | Effort | Expected Impact | Source |
|--------|--------|----------------|--------|
| Two-level hierarchical retrieval | New service + migration | Critical for 50+ video collections | RAPTOR, LlamaIndex |
| Adaptive retrieval (skip when unnecessary) | Modify conversation pipeline | Faster off-topic responses, less noise | Self-RAG (Asai 2023) |
| Memory evolution + inline consolidation | Refactor fact_extraction + new service | Scalable long conversations | Mem0, A-MEM |
| Convex combination fusion (replace RRF) | Modify vector_store.py | Better fusion quality | Bruch 2024 |

---

## References

### Academic Papers
1. Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique," NeurIPS 2023 / ICLR 2024
2. Bruch et al., "An Analysis of Fusion Functions for Hybrid Retrieval," ACM TOIS 42(1), 2024
3. Carbonell & Goldstein, "MMR for Reordering Documents," ACM SIGIR 1998
4. Chen et al., "Dense-X Retrieval: Proposition-Based Indexing," EMNLP 2024
5. Gao et al., "HyDE: Precise Zero-Shot Dense Retrieval," ACL 2023
6. Lee et al., "NV-Embed-v2," ICLR 2025
7. Liu et al., "Lost in the Middle: How Language Models Use Long Contexts," TACL 2024
8. Merola & Singh, "Reconstructing Context: Evaluating Chunking Strategies," arXiv 2504.19754, April 2025
9. Packer et al., "MemGPT: Towards LLMs as Operating Systems," arXiv 2310.08560, Oct 2023
10. Rackauckas, "RAG-Fusion," arXiv 2402.03367, Feb 2024
11. Sarthi et al., "RAPTOR: Recursive Abstractive Processing," ICLR 2024
12. "Searching for Best Practices in RAG," arXiv 2407.01219, July 2024
13. Es et al., "RAGAS: Automated Evaluation of RAG," EACL 2024
14. Saad-Falcon et al., "ARES: Automated Evaluation Framework," NAACL 2024
15. Chhikara et al., "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory," arXiv 2504.19413, April 2025
16. Xu et al., "A-MEM: Agentic Memory for LLM Agents," NeurIPS 2025
17. Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning," NeurIPS 2023
18. Dassen et al., "FACTUM: Mechanistic Detection of Citation Hallucination," arXiv 2601.05866, Jan 2026
19. "GaRAGe: Grounding Annotations for RAG Evaluation," Amazon Science, ACL 2025
20. "Agentic Retrieval-Augmented Generation: A Survey," arXiv 2501.09136, Jan 2025

### Industry Whitepapers
21. Anthropic, "Contextual Retrieval," Sept 2024
22. OpenAI, "New Embedding Models and API Updates," Jan 2024
23. Microsoft, "GraphRAG: From Local to Global," arXiv 2404.16130, April 2024
24. Microsoft, "Azure AI Search: Outperforming Vector Search with Hybrid Retrieval," 2024
25. NVIDIA, "NeMo Retriever: Production-Grade Text Retrieval for RAG," 2024
26. Google, "RAG and Grounding on Vertex AI," 2024
27. Cohere, "Rerank 3.5," Dec 2024
28. Chroma Research, "Evaluating Chunking Strategies for Retrieval," July 2024
29. SMMR, "Sampling-Based MMR Reranking," ACM SIGIR 2025
30. Qdrant, "Updated Benchmarks 2024"
