# Architectural Impact Checklist

A pre-implementation checklist to consult during plan mode before making RAG pipeline changes. Prevents regressions by mapping blast radius, verifying contracts, and identifying test gaps.

**When to use:** Before implementing any feature that touches the RAG pipeline (retrieval, embedding, chunking, enrichment, reranking, memory, citations, or conversation handling).

---

## 1. Blast Radius Mapping

Before writing code, trace the change through the pipeline. Mark all affected layers.

| Layer | Key Files | Ask |
|-------|-----------|-----|
| Embedding | `embeddings.py`, `config.py` | Does this change vector dimensions? Requires re-indexing? |
| Vector Store | `vector_store.py` | Does this change collection schema, similarity metric, or index params? |
| Chunking | `chunking.py` | Does chunk size/overlap change? Affects all downstream (enrichment, embedding, retrieval) |
| Enrichment | `enrichment.py` | Does enrichment prompt change? Affects chunk quality for all existing + new content |
| Query Processing | `query_expansion.py`, `hyde.py`, `relevance_grader.py` | Does query format change? Check BGE prefix requirement |
| Retrieval | `vector_store.py`, `bm25_search.py` | Does scoring, filtering, or deduplication logic change? |
| Reranking | `reranker.py` | Does model or threshold change? Check latency budget (~200ms) |
| Context Building | `conversations.py` | Does chunk limit, context format, or system prompt change? |
| Memory | `fact_extraction.py`, `memory_consolidation.py`, `memory_scoring.py` | Does fact threshold, extraction logic, or consolidation change? |
| Citations | `conversations.py` | Does citation parsing, marker format, or jump URL construction change? |
| Storage/Billing | `storage_calculator.py`, `pricing.py` | Does vector size, chunk storage, or quota calculation change? |
| LLM Provider | `llm_providers.py`, `pricing.py` | Does model selection, token limits, or API format change? |

### Ripple Effects to Check

```
Embedding change    → re-index ALL vectors → storage recalculation → billing impact
Chunk size change   → re-chunk ALL content → re-enrich → re-embed → re-index
Enrichment change   → re-enrich ALL chunks → re-embed (if enriched text is embedded)
Retrieval change    → score thresholds may need recalibration
Model change        → token limits, pricing, reasoning_content handling
Config flag change  → verify both enabled AND disabled paths are tested
```

---

## 2. Contract Cross-Reference

Check which behavioral contracts (`.claude/references/behavioral-contracts.md`) are affected by the change.

| If you're changing... | Check these contracts |
|-----------------------|---------------------|
| Conversation history or memory | MEM-001 (dead zone), MEM-002 (identity survival), MEM-003 (consolidation), MEM-004 (dedup) |
| Citation generation or parsing | CIT-001 (was_used_in_response), CIT-002 (marker bounds), CIT-003 (jump URLs) |
| Embedding model or dimensions | ACC-001 (vector size calculation) |
| Token estimation or context building | ACC-002 (token estimate accuracy) |
| BM25 or keyword search | ACC-003 (proper noun bypass) |
| Enrichment pipeline | PAR-001 (document/video parity), PAR-002 (truncation warning) |
| Self-RAG or relevance grading | RET-001 (corrective action execution) |

**Rule:** If a contract is currently BROKEN, do not make changes that depend on it working. Fix the contract first or explicitly document the dependency.

---

## 3. Test Requirements

Before implementing, verify test coverage exists for the change.

### Required Test Checks

- [ ] **Unit tests exist** for the file being changed (check `backend/tests/unit/test_<service>.py`)
- [ ] **Contract tests pass** for affected contracts (`test_memory_contracts.py`, `test_citation_contracts.py`)
- [ ] **Edge cases covered:** empty input, None values, boundary conditions
- [ ] **Both code paths tested** if change involves a config flag (enabled + disabled)
- [ ] **Error path tested:** what happens when the new code fails? Graceful fallback or crash?

### Known Coverage Gaps (verify current state before relying)

| File | Last Known Coverage | Risk |
|------|-------------------|------|
| `video_tasks.py` | ~11% | High — processing pipeline largely untested |
| `vector_store.py` | ~34% | High — retrieval correctness depends on this |
| `enrichment.py` | ~21% | Medium — enrichment quality affects all downstream |

**Rule:** If the file you're changing has <50% coverage, write tests for the affected code paths BEFORE making the change. Test the current behavior first, then modify.

---

## 4. Migration Safety

### Database Changes
- [ ] Migration file follows naming convention (`NNN_description.py` in `backend/alembic/versions/`)
- [ ] Migration is reversible (has `downgrade()` that undoes `upgrade()`)
- [ ] New columns have sensible defaults (don't break existing rows)
- [ ] No data loss on downgrade

### Vector Store Changes
- [ ] If dimensions change: plan for full re-indexing (downtime or dual-collection strategy)
- [ ] If similarity metric changes: existing scores become incomparable
- [ ] If collection schema changes: verify Qdrant migration path

### Config Changes
- [ ] New config flags have defaults that preserve current behavior (feature off by default)
- [ ] `.env.example` updated with new variables
- [ ] Config documented in CLAUDE.md if user-facing

### Celery Task Changes
- [ ] Long-running tasks account for Redis `visibility_timeout` (5h) — see Celery bug in memory
- [ ] Idempotency: task can be safely re-run if redelivered
- [ ] Cancellation checkpoints: task checks for `canceled` status between stages

---

## 5. Anti-Bandaid Patterns

Reject these patterns during review. They indicate a deeper problem that should be fixed properly.

| Pattern | Why It's Bad | Fix Instead |
|---------|-------------|-------------|
| Hardcoded magic numbers | Break when context changes | Use config values or derive from model/data |
| Silent fallbacks (`except: pass`) | Hides bugs, makes debugging impossible | Log the error, raise or return explicit failure |
| `# TODO: fix later` without issue | Never gets fixed, accumulates debt | Fix now or create a tracked issue |
| Skipping validation (`--no-verify`) | Bypasses safety checks | Fix what the check is catching |
| `always True` / `always False` flags | Dead code path, false sense of coverage | Remove the flag or implement both paths |
| Duplicate logic across services | Diverges over time, one gets updated the other doesn't | Extract shared function or use single source |
| Re-exporting removed code for "compatibility" | Prevents cleanup, confuses readers | Delete it. If something breaks, that's a real dependency to address |
| Catching broad exceptions to "handle" them | Masks the actual error type | Catch specific exceptions, let unexpected ones propagate |

---

## 6. Performance Budget

Total RAG pipeline budget: **~5s** (target for user-perceived latency)

| Stage | Budget | Current |
|-------|--------|---------|
| Query expansion | 1.0s | ~0.8s |
| Vector retrieval | 0.5s | ~0.3s |
| BM25 retrieval | 0.2s | ~0.1s |
| Reranking | 0.3s | ~0.2s |
| Context building | 0.1s | <0.1s |
| LLM generation | 3.0s | ~2.5s |
| **Total** | **5.1s** | **~4.0s** |

**Rule:** Any new stage that adds >200ms needs justification. If it pushes total beyond 5s, something else must be optimized or the new stage should be async/optional.

---

## How to Use This Checklist

1. **During plan mode:** Read this before writing the implementation plan
2. **Map sections 1-2:** Identify blast radius and affected contracts
3. **Check section 3:** Verify test coverage exists or plan to write tests first
4. **Review section 4:** Identify any migration/infrastructure changes needed
5. **Apply section 5:** Screen the planned approach for bandaid patterns
6. **Verify section 6:** Confirm the change fits within performance budget
7. **Include findings in the plan:** Explicitly state which contracts, tests, and migrations are affected
