# Behavioral Contracts

Machine-readable list of behavioral promises the system makes to users. Each contract has a unique ID, a description of what it promises, where it's implemented, and how to validate it.

**Last updated:** 2026-02-25

---

## Memory Contracts (MEM-*)

| ID | Promise | Implementation | Validation |
|----|---------|----------------|------------|
| MEM-001 | No memory dead zone: fact injection threshold <= history limit | `conversations.py:1472` threshold `>= 10` (was 15), history `.limit(10)` at `conversations.py:1262` | **FIXED.** Threshold lowered to 10 to match history limit. Facts are extracted every turn unconditionally; threshold only gates injection into prompt. |
| MEM-002 | Identity facts survive indefinitely | `memory_consolidation.py:24-28` identity skip + `memory_scoring.py:38-44` category priority 1.0 | Identity facts from turn 1 still present at turn 100 — consolidation must not prune identity-category facts |
| MEM-003 | Consolidation runs during active conversations when fact count > threshold | `memory_tasks.py:85-100` inline check after extraction; `conversations.py:2603-2617` streaming inline check | **FIXED.** Both non-streaming (Celery task) and streaming paths check fact count after extraction and run `consolidate_conversation()` when count > 50. |
| MEM-004 | Fact values merge on update (not silently dropped) | `fact_extraction.py:336-348` updates existing fact value when key matches but value differs | **FIXED.** `_deduplicate_facts()` now compares values on key collision. When values differ, updates `fact_value`, `importance`, and `source_turn` instead of skipping. |

---

## Citation Contracts (CIT-*)

| ID | Promise | Implementation | Validation |
|----|---------|----------------|------------|
| CIT-001 | `was_used_in_response` reflects actual LLM output | `conversations.py` `_extract_used_markers()` → sets `was_used_in_response=(rank in used_markers)` on `MessageChunkReference` | **FIXED.** Both streaming and non-streaming paths parse `[N]` markers and set `was_used_in_response` accordingly. `chunks_used_count` also set on Message. |
| CIT-002 | All `[N]` markers in LLM output map to valid retrieved chunks | `conversations.py` `_validate_citation_markers()` | **FIXED.** Logs warning for out-of-bounds markers. Called in both streaming and non-streaming paths. |
| CIT-003 | Jump URLs have correct timestamps | `conversations.py` `_build_youtube_jump_url` | Assert URL `t=` parameter matches `chunk.start_timestamp` (within 1s tolerance) |

---

## Accuracy Contracts (ACC-*)

| ID | Promise | Implementation | Validation |
|----|---------|----------------|------------|
| ACC-001 | Storage vector size calculation uses actual embedding dimensions | `storage_calculator.py` `_calculate_bytes_per_vector()` dynamically reads `settings.embedding_model` | **FIXED.** `BYTES_PER_VECTOR` now computed from model dimensions lookup, not hardcoded. |
| ACC-002 | Token estimates within 20% of actual | `conversations.py` uses `word_count * 1.3` heuristic | Compare streaming token estimates vs actual token counts from LLM response usage metadata |
| ACC-003 | BM25 not skipped for entity/name queries | `bm25_search.py:50-65` `_has_proper_noun()` bypasses min-token gate | **FIXED.** `_should_skip_bm25()` checks for proper nouns before applying token count threshold. |

---

## Content Parity Contracts (PAR-*)

| ID | Promise | Implementation | Validation |
|----|---------|----------------|------------|
| PAR-001 | Documents get same enrichment quality as videos | `document_tasks.py` vs `video_tasks.py` | Both call `ContextualEnricher` with equivalent params (full_text, content_type, usage_collector) |
| PAR-002 | Enrichment logs warning when full-text is truncated | `enrichment.py:97-101` `logger.warning()` with char counts and content_id | **FIXED.** Truncation now emits warning with original size, truncated size, and content ID. |

---

## Retrieval Contracts (RET-*)

| ID | Promise | Implementation | Validation |
|----|---------|----------------|------------|
| RET-001 | Self-RAG corrective actions execute when enabled | `two_level_retriever.py:785-828` has REFORMULATE/EXPAND_SCOPE/INSUFFICIENT handlers | When `enable_relevance_grading=True`, REFORMULATE triggers actual re-retrieval with reformulated query, not just logging |

---

## How to Use This Document

### For proactive skills
Shell scripts grep for specific patterns (`.limit(N)`, `was_used_in_response`, etc.) and flag when contracts appear violated.

### For test-before-complete
Claude reads this file, identifies which contracts are touched by changed files, and verifies each touched contract still holds.

### For contract unit tests
`backend/tests/unit/test_memory_contracts.py` and `test_citation_contracts.py` encode the validation column as automated assertions.

### For full audit (`/behavioral-contracts`)
Claude reads every contract, checks the implementing code, and produces a pass/fail report.

---

## Contract Status Legend

When reporting contract status:
- **PASS** — Implementation matches promise, validation confirms
- **BROKEN** — Implementation contradicts promise (e.g., `was_used_in_response` always True)
- **DEGRADED** — Implementation partially fulfills promise (e.g., dead zone exists but is small)
- **UNTESTED** — Cannot verify without live infrastructure
