# RAG Best Practices Reference

A living catalog of RAG techniques organized by pipeline stage. Each technique includes source attribution, complexity, expected improvement, and relevance to this project's YouTube transcript use case.

**Last updated:** 2026-02-06

---

## 1. Chunking

### Fixed-Size Chunking
- **Source:** Baseline approach used in most RAG tutorials
- **How:** Split text every N tokens with M token overlap
- **Complexity:** Low
- **Expected improvement:** Baseline (0%)
- **When to use:** Starting point; good enough for well-structured documents
- **Project relevance:** Current implementation uses 256-token chunks with overlap. Adequate for transcripts.

### Semantic Chunking
- **Source:** LlamaIndex, Greg Kamradt's "5 Levels of Text Splitting"
- **How:** Split at points where embedding similarity between consecutive sentences drops below threshold
- **Complexity:** Medium
- **Expected improvement:** 5-10% over fixed-size for documents with varied topic density
- **When to use:** When content has natural topic boundaries at varying intervals
- **Project relevance:** Medium value. Transcripts shift topics unpredictably; semantic boundaries could capture this better than fixed windows.

### Contextual Chunking (Anthropic Pattern)
- **Source:** Anthropic "Contextual Retrieval" blog (2024)
- **How:** Prepend each chunk with document-level context (title, summary, position) before embedding
- **Complexity:** Medium (requires LLM call per chunk at index time)
- **Expected improvement:** ~35% reduction in retrieval failures (Anthropic's benchmark)
- **When to use:** Always beneficial; reduces "lost in the middle" problem
- **Project relevance:** Already implemented via enrichment service. This is a strength.

### RAPTOR (Recursive Abstractive Processing)
- **Source:** Stanford NLP, "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval" (2024)
- **How:** Build hierarchical tree of summaries. Leaf nodes = chunks, parent nodes = cluster summaries. Retrieval traverses tree.
- **Complexity:** High (clustering + LLM summarization at multiple levels)
- **Expected improvement:** 10-20% on multi-document synthesis tasks
- **When to use:** Large corpora (100+ documents) requiring cross-document reasoning
- **Project relevance:** Future consideration. Currently planned as two-level hierarchy (video summaries + chunks). Full RAPTOR warranted when adding multi-content types (PDFs, docs).

---

## 2. Embedding

### Model Selection (MTEB Leaderboard)
- **Source:** Hugging Face MTEB Leaderboard
- **Top models (2025-2026):** OpenAI text-embedding-3-large (3072d), Cohere embed-v3, BGE-M3 (multi-lingual), NV-Embed-v2
- **Complexity:** Low (swap model)
- **Expected improvement:** 5-15% depending on current model quality
- **When to use:** When current model underperforms on domain-specific queries
- **Project relevance:** Currently using local sentence-transformers (likely all-MiniLM-L6-v2 or similar). Upgrading to text-embedding-3-large or BGE-M3 could meaningfully improve retrieval quality, but adds API cost and latency.

### Contextual Embeddings
- **Source:** Anthropic Contextual Retrieval, various research
- **How:** Embed chunks with their surrounding context prepended (not just raw chunk text)
- **Complexity:** Low (modify embedding input)
- **Expected improvement:** 5-10% retrieval precision when combined with contextual chunking
- **When to use:** When chunks lack standalone meaning (common with transcripts)
- **Project relevance:** Already implemented via enrichment prepending. Aligned with best practice.

### HyDE (Hypothetical Document Embeddings)
- **Source:** Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance Labels" (2022)
- **How:** Generate a hypothetical answer to the query, embed that instead of (or alongside) the raw query
- **Complexity:** Medium (requires LLM call at query time, adds ~0.5-1s latency)
- **Expected improvement:** 10-15% on queries where user phrasing differs significantly from document language
- **When to use:** When vocabulary mismatch is high (academic queries vs conversational documents)
- **Project relevance:** Medium. Users ask natural questions; transcripts use casual language. Query expansion already addresses some vocabulary mismatch. HyDE could complement but adds latency.

### Embedding Fine-Tuning
- **Source:** Sentence-BERT, various fine-tuning guides
- **How:** Fine-tune embedding model on domain-specific query-document pairs
- **Complexity:** High (requires training data, compute, evaluation)
- **Expected improvement:** 10-25% for specialized domains
- **When to use:** When off-the-shelf models consistently fail on domain terminology
- **Project relevance:** Low priority. YouTube content is general-domain; pre-trained models handle it well.

---

## 3. Retrieval

### Hybrid Search (BM25 + Dense)
- **Source:** Multiple benchmarks, Qdrant hybrid search docs, Pinecone hybrid guide
- **How:** Run BM25 keyword search alongside dense vector search, merge results with Reciprocal Rank Fusion (RRF) or weighted combination
- **Complexity:** Medium (requires BM25 index alongside vector index)
- **Expected improvement:** 5-15% over dense-only, especially for entity/keyword queries
- **When to use:** Nearly always beneficial. BM25 catches exact matches that embeddings miss.
- **Project relevance:** **Biggest current gap.** Dense-only retrieval misses exact name/term matches. Qdrant supports sparse vectors (BM25) natively. Implementation: add SPLADE or BM25 sparse vectors to existing Qdrant collection.

### Multi-Query / RAG-Fusion
- **Source:** RAG-Fusion paper, LangChain implementation
- **How:** Generate 2-3 query variants, retrieve for each, merge results with max-score fusion
- **Complexity:** Medium (LLM call + multiple retrievals)
- **Expected improvement:** 20-30% recall improvement
- **When to use:** When single queries miss relevant documents due to phrasing specificity
- **Project relevance:** Already implemented. Query expansion generates variants and merges with max-score fusion.

### MMR (Maximal Marginal Relevance)
- **Source:** Carbonell & Goldstein (1998), widely adopted
- **How:** Balance relevance against diversity when selecting chunks. Penalize chunks too similar to already-selected ones.
- **Complexity:** Low
- **Expected improvement:** Qualitative improvement in answer coverage for multi-document queries
- **When to use:** When retrieving from collections with many similar chunks
- **Project relevance:** Already implemented with adaptive diversity factor (0.3-0.7 based on video count).

### ColBERT (Late Interaction)
- **Source:** Stanford IR Lab, "ColBERT: Efficient and Effective Passage Search" (2020)
- **How:** Token-level embeddings with late interaction scoring. More expressive than single-vector but cheaper than cross-encoder at retrieval time.
- **Complexity:** High (requires ColBERT index, different from standard dense index)
- **Expected improvement:** 5-10% over dense retrieval, with better latency than cross-encoder at scale
- **When to use:** When you need better-than-dense retrieval at scale without cross-encoder latency
- **Project relevance:** Low priority. Cross-encoder reranking already covers the precision gap. ColBERT adds infrastructure complexity.

### Adaptive Retrieval
- **Source:** Self-RAG paper, various implementations
- **How:** Decide dynamically whether retrieval is needed, how many chunks to fetch, and whether to re-retrieve
- **Complexity:** High
- **Expected improvement:** Reduces unnecessary retrieval calls; improves precision on simple queries
- **When to use:** When many queries don't need retrieval (e.g., conversational follow-ups)
- **Project relevance:** Medium. Intent classification already routes queries. Could extend to skip retrieval for pure conversational turns.

---

## 4. Reranking

### Cross-Encoder Reranking (Pointwise)
- **Source:** MS MARCO trained models, Sentence-BERT
- **Models:** ms-marco-MiniLM-L-6-v2 (fast), BGE-reranker-v2-m3 (multilingual), Cohere Rerank (API)
- **Complexity:** Low (add scoring step after retrieval)
- **Expected improvement:** 15-20% precision over bi-encoder retrieval alone
- **When to use:** Always beneficial when latency budget allows (~50-200ms for top-20)
- **Project relevance:** Already implemented with ms-marco-MiniLM-L-6-v2. Working well.

### Listwise Reranking (LLM-Based)
- **Source:** RankGPT, various LLM ranking papers
- **How:** Ask LLM to rank a list of passages by relevance to a query
- **Complexity:** Medium (LLM call, prompt engineering)
- **Expected improvement:** Can outperform cross-encoder on nuanced queries, but higher latency and cost
- **When to use:** When cross-encoder misses semantic nuance; budget allows LLM reranking
- **Project relevance:** Low priority. Cross-encoder handles well. LLM reranking would add 1-2s latency.

### Cohere Rerank API
- **Source:** Cohere
- **How:** API call to state-of-the-art reranking model
- **Complexity:** Low (API integration)
- **Expected improvement:** 5-10% over ms-marco-MiniLM; handles long passages better
- **When to use:** When quality improvement justifies API cost ($1/1000 searches)
- **Project relevance:** Worth benchmarking. Drop-in replacement for current cross-encoder. Cost is modest.

---

## 5. Generation

### Hallucination Prevention (ICE Method)
- **Source:** Various production RAG systems, Anthropic guidelines
- **How:** Instruct, Cite, Extract. System prompt explicitly says "only answer from provided context", require citations, extract claims for verification.
- **Complexity:** Low (prompt engineering)
- **Expected improvement:** Significant reduction in hallucinations (hard to quantify)
- **When to use:** Always in production RAG systems
- **Project relevance:** Already implemented with citation system and grounding instructions.

### Self-RAG
- **Source:** Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique" (2023)
- **How:** Model generates special tokens to decide when to retrieve, evaluates its own generation for support/relevance, and can re-retrieve if needed.
- **Complexity:** High (requires fine-tuned model or complex prompting)
- **Expected improvement:** 10-15% on factual accuracy benchmarks
- **When to use:** When hallucination rates are unacceptably high despite prompt engineering
- **Project relevance:** Low-medium. Worth monitoring but current citation system provides good grounding. Could approximate with LLM-as-judge verification step.

### CRAG (Corrective RAG)
- **Source:** Yan et al., "Corrective Retrieval Augmented Generation" (2024)
- **How:** After retrieval, evaluate if retrieved documents are relevant. If not, trigger web search or reformulate query.
- **Complexity:** Medium (adds evaluation + fallback retrieval step)
- **Expected improvement:** Reduces "I don't have enough information" failures by 20-30%
- **When to use:** When retrieval frequently returns marginally relevant results
- **Project relevance:** Medium. Could detect when retrieved chunks poorly match the query and trigger re-retrieval with different expansion. Relevance thresholds already help but don't trigger re-retrieval.

### Adaptive Context Window
- **Source:** Production best practices
- **How:** Dynamically size the context window based on query complexity and chunk relevance scores. Simple queries get fewer chunks; complex synthesis gets more.
- **Complexity:** Low
- **Expected improvement:** Better token efficiency, reduced noise in context
- **When to use:** When serving queries of varying complexity
- **Project relevance:** Already partially implemented with adaptive chunk limits (4-12 based on video count and mode).

---

## 6. Evaluation

### RAGAS Framework
- **Source:** RAGAS (Retrieval Augmented Generation Assessment), ragas.io
- **Metrics:**
  - **Faithfulness:** Are generated claims supported by retrieved context? (Target: >0.85)
  - **Answer Relevancy:** Does the answer address the question? (Target: >0.80)
  - **Context Precision:** Are retrieved chunks actually relevant? (Target: >0.75)
  - **Context Recall:** Are all relevant chunks retrieved? (Target: >0.70)
- **Complexity:** Medium (requires test dataset, LLM-as-judge evaluation)
- **Expected improvement:** Enables data-driven optimization (unmeasured systems can't improve)
- **When to use:** Before any optimization work. Establish baseline first.
- **Project relevance:** **Second biggest gap.** No formal evaluation framework exists. Without metrics, all optimization is guesswork.

### LLM-as-Judge
- **Source:** Various, including RAGAS, Anthropic evaluation guide
- **How:** Use LLM to score generated answers on dimensions like accuracy, relevance, completeness
- **Complexity:** Low-Medium
- **Expected improvement:** Enables automated regression detection
- **When to use:** When human evaluation doesn't scale
- **Project relevance:** High. Could integrate with existing admin QA feed for automated scoring.

### Human Evaluation Protocol
- **Source:** Production best practices
- **How:** Sample N queries/week, have humans rate answer quality on 1-5 scale
- **Complexity:** Low (process, not code)
- **Expected improvement:** Ground truth for calibrating automated metrics
- **When to use:** To validate automated evaluation metrics
- **Project relevance:** Admin QA feed already surfaces questions/answers. Add rating capability.

### Retrieval Evaluation (Hit Rate, MRR, NDCG)
- **Source:** Information retrieval fundamentals
- **Metrics:**
  - **Hit Rate@K:** Is at least one relevant chunk in top K? (Target: >0.85)
  - **MRR@K:** Mean reciprocal rank of first relevant chunk (Target: >0.70)
  - **NDCG@K:** Normalized discounted cumulative gain (Target: >0.65)
- **Complexity:** Medium (requires relevance judgments / ground truth)
- **Expected improvement:** Isolates retrieval quality from generation quality
- **When to use:** To diagnose whether poor answers stem from retrieval or generation
- **Project relevance:** High. Can build ground truth from citation feedback (which chunks users actually find useful).

---

## 7. Architecture Patterns

### Simple RAG
- **Pattern:** Query -> Retrieve -> Generate
- **When to use:** Starting point; sufficient for many use cases
- **Project relevance:** Project has evolved well beyond this.

### Two-Level Hierarchical RAG
- **Pattern:** Video summaries (Level 1) + Chunks (Level 2). Route broad queries to summaries, specific queries to chunks.
- **Source:** LlamaIndex hierarchical retrieval
- **Complexity:** Medium
- **Expected improvement:** Much better coverage for "summarize all videos about X" queries
- **When to use:** Collections with 20+ documents where chunk-level retrieval has coverage limits
- **Project relevance:** Planned. CLAUDE.md documents the design. Implementation requires video-level summaries and query routing.

### Agentic RAG
- **Pattern:** LLM agent decides which tools to use (retrieve, search, calculate, etc.) based on query analysis
- **Source:** LangChain agents, LlamaIndex agents
- **Complexity:** High
- **Expected improvement:** Handles complex multi-step queries that simple RAG cannot
- **When to use:** When queries require reasoning, comparison, or multi-step retrieval
- **Project relevance:** Future consideration. Intent classification is a lightweight precursor.

### Query Routing
- **Pattern:** Classify query intent, route to specialized retrieval pipeline per intent type
- **Source:** Various production RAG systems
- **Complexity:** Medium
- **Expected improvement:** 10-20% by optimizing each pipeline for its query type
- **When to use:** When query types have distinctly different optimal retrieval strategies
- **Project relevance:** Already implemented with COVERAGE/PRECISION/HYBRID intent classification.

### Graph RAG
- **Source:** Microsoft "GraphRAG: Unlocking LLM discovery on narrative private data" (2024)
- **How:** Build knowledge graph from documents, use graph traversal for retrieval alongside vector search
- **Complexity:** Very High (entity extraction, graph construction, query decomposition)
- **Expected improvement:** 20-30% on questions requiring reasoning across entity relationships
- **When to use:** When content has rich entity relationships (people, events, concepts) and queries require connecting them
- **Project relevance:** Low priority currently. YouTube transcripts have some entity structure (speakers, topics, references) but the complexity isn't justified yet. Revisit when evaluation data shows entity-relationship queries failing.

---

## Decision Framework

When considering a new technique, evaluate:

1. **Measured gap?** Do metrics show the current stage is the bottleneck?
2. **Expected uplift:** Does the technique provide meaningful improvement for this use case?
3. **Latency impact:** Does it fit within the 5s total pipeline budget?
4. **Complexity cost:** Is the implementation and maintenance burden justified?
5. **Reversibility:** Can you A/B test or easily roll back?

**Priority ordering for this project:**
1. Add evaluation framework (RAGAS) - you can't optimize what you can't measure
2. Add hybrid search (BM25 + dense) - biggest retrieval quality gap
3. Implement two-level hierarchy - planned, needed for large collections
4. Benchmark embedding model upgrade - potential quality gain with modest effort
5. Add CRAG-style retrieval evaluation - reduces "marginally relevant" failures

---

## 8. Conversation Memory

### History Window Management
- **Source:** OpenAI Weighted Memory Retrieval (WMR) pattern, Anthropic memory guidelines
- **How:** Keep N most recent messages in working memory; extract and store facts from older turns before they leave the window
- **Key invariant:** `FACT_THRESHOLD <= HISTORY_LIMIT` — facts must be extracted before messages leave the history window, or a "dead zone" of lost information exists
- **Project relevance:** Current implementation has history_limit=10 and fact_threshold=15, creating a 5-turn dead zone where messages are no longer in history but facts haven't been extracted yet

### Fact Extraction Timing
- **Source:** Production memory systems
- **How:** Extract facts incrementally (every N turns or on each turn) rather than waiting for a high threshold
- **When to use:** When conversation memory is important and history window is smaller than fact extraction threshold
- **Project relevance:** Critical gap. Consider lowering threshold to match history limit, or extracting facts incrementally.

### Identity Fact Preservation
- **Source:** OpenAI WMR, Anthropic memory guidelines
- **How:** Identity facts (names, roles, relationships) get highest priority and never decay. They are the foundation of personalized conversations.
- **Key rules:** Identity facts skip decay during consolidation, get category priority 1.0 in scoring, and are never pruned regardless of conversation length
- **Project relevance:** Already implemented correctly in `memory_scoring.py` and `memory_consolidation.py`.

### Dead Zone Prevention
- **Source:** Production best practices
- **Strategies:**
  1. **Lower threshold**: Set fact extraction threshold <= history limit
  2. **Incremental extraction**: Extract after every N turns instead of waiting for threshold
  3. **Bridging**: Store key-value summaries of messages before they leave the window
  4. **Expanding window**: Increase history limit (but increases token cost)
- **Project relevance:** Dead zone exists between turn 10 (history limit) and turn 15 (fact threshold). Strategy 1 or 2 recommended.

### Consolidation During Active Conversations
- **Source:** Production memory systems
- **How:** Run consolidation inline when fact count exceeds MAX_FACTS, not just in scheduled beat tasks
- **When to use:** Active conversations that accumulate many facts between beat task runs
- **Project relevance:** Consolidation only runs via Celery beat for stale conversations (24h inactive). Active conversations can accumulate unlimited facts.

---

## 9. Citation Verification

### Post-Generation Citation Parsing
- **Source:** Production RAG systems, RAGAS faithfulness metric
- **How:** After LLM generates response, parse citation markers (e.g., `[1]`, `[2]`) and validate against provided chunks
- **Key metrics:**
  - **Citation precision**: Do cited chunks actually support the claims?
  - **Citation recall**: Are all claims grounded in citations?
  - **was_used_in_response**: Track which provided chunks were actually referenced by the LLM
- **Project relevance:** Critical gap. `was_used_in_response` defaults to True and is never updated. All citations appear "used" regardless of LLM output. This undermines citation quality metrics and admin monitoring.

### Citation-Source Grounding
- **Source:** RAGAS faithfulness, Self-RAG critique tokens
- **How:** For each `[N]` marker in LLM output, verify the referenced chunk actually supports the preceding claim
- **Complexity:** Medium (requires additional LLM call or heuristic check)
- **Expected improvement:** Catches hallucinated citations (LLM cites a chunk but the claim isn't in it)
- **Project relevance:** Medium priority. Useful for quality monitoring but adds latency if done synchronously.

### Citation Completeness
- **Source:** Production RAG quality guidelines
- **How:** Check that:
  1. All `[N]` markers reference valid chunks (N <= total chunks provided)
  2. No orphan citations (markers pointing to non-existent chunks)
  3. No off-by-one errors (0-indexed vs 1-indexed)
- **Project relevance:** No bounds validation currently exists. LLM could generate `[5]` when only 4 chunks were provided.

### Jump URL Integrity
- **Source:** YouTube-specific RAG requirement
- **How:** Verify timestamp in jump URL matches chunk's `start_timestamp`. Handle edge cases: None timestamps (documents), timestamp=0 (start of video), very large timestamps.
- **Project relevance:** URL builder should validate timestamp is not None before including `t=` parameter. Document chunks should not generate YouTube jump URLs.
