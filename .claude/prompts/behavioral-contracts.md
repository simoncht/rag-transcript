# Behavioral Contracts Full Audit

Run a comprehensive audit of all behavioral promises the system makes to users. This is the manual skill invoked with `/behavioral-contracts`.

## Procedure

### Step 1: Load Contract Definitions

Read `.claude/references/behavioral-contracts.md` for the full list of contracts with their IDs, promises, implementation locations, and validation criteria.

### Step 2: Verify Each Contract

For each contract, read the implementing code and run a pass/fail assessment:

**Memory Contracts:**

| ID | What to Check |
|----|---------------|
| MEM-001 | Read `conversations.py` — find `.limit(N)` for history and `message_count >= M` for facts. Is M > N? If so, dead zone exists. |
| MEM-002 | Read `memory_consolidation.py` `_apply_decay()` and `_prune_facts()` — do they skip identity facts? Read `memory_scoring.py` — is identity priority 1.0? |
| MEM-003 | Search for consolidation calls outside of `tasks/` and `celery_app.py`. If none, consolidation only runs in beat tasks (not during active conversations). |
| MEM-004 | Read `fact_extraction.py` dedup logic. When a fact key matches an existing fact, is the value compared or just the key? |

**Citation Contracts:**

| ID | What to Check |
|----|---------------|
| CIT-001 | Search entire backend for `was_used_in_response = False`. If not found, the field is always True (broken). |
| CIT-002 | Read system prompt in `conversations.py` for how chunks are numbered. Check if marker bounds are validated after LLM response. |
| CIT-003 | Read jump URL builder. Does it handle None timestamps? Does it correctly convert seconds to `t=` parameter? |

**Accuracy Contracts:**

| ID | What to Check |
|----|---------------|
| ACC-001 | Read `storage_calculator.py` BYTES_PER_VECTOR constant. Read `config.py` for embedding_model. Do the dimensions match? |
| ACC-002 | Read token estimation in `conversations.py`. Is it `word_count * 1.3` or a proper tokenizer? How far off could it be? |
| ACC-003 | Read `bm25_search.py` `_should_skip_bm25()`. Does it skip queries with proper nouns that have <3 tokens? |

**Content Parity Contracts:**

| ID | What to Check |
|----|---------------|
| PAR-001 | Compare enrichment calls in `document_tasks.py` vs `video_tasks.py`. Are parameters equivalent? |
| PAR-002 | Read `enrichment.py` truncation logic. Is there a `logger.warning()` when full_text > 48K? |

**Retrieval Contracts:**

| ID | What to Check |
|----|---------------|
| RET-001 | Read `two_level_retriever.py` around lines 785-828. When `enable_relevance_grading=True`, do REFORMULATE/EXPAND_SCOPE actually trigger re-retrieval? Or are they just logged? |

### Step 3: Produce Report

```
## Behavioral Contracts Audit Report

**Date:** [current date]
**Audited by:** Claude Code

### Summary
- Total contracts: X
- Passing: Y
- Broken: Z
- Degraded: W

### Detailed Results

| ID | Promise | Status | Evidence |
|----|---------|--------|----------|
| MEM-001 | No memory dead zone | PASS/BROKEN/DEGRADED | [file:line citation + specific finding] |
| MEM-002 | Identity facts survive | PASS/BROKEN/DEGRADED | [file:line citation] |
| ... | ... | ... | ... |

### Critical Issues (Must Fix)
[List broken contracts that cause user-visible problems, ordered by severity]

### Degraded Contracts (Should Fix)
[List degraded contracts with impact assessment]

### Passing Contracts
[Brief confirmation of passing contracts]

### Recommendations
[Prioritized list of fixes with specific file:line targets and estimated effort]
```

### Step 4: Prioritize Recommendations

Order recommendations by:
1. **User impact** — Does the broken contract cause visible problems?
2. **Fix complexity** — How many files need to change?
3. **Risk** — Could the fix introduce regressions?

### Step 5: Offer to Fix

For each broken contract, offer a specific code change. Focus on the highest-impact fixes first.

## Contract Status Legend

- **PASS** — Implementation matches promise, validation confirms
- **BROKEN** — Implementation contradicts promise (e.g., `was_used_in_response` always True)
- **DEGRADED** — Implementation partially fulfills promise (e.g., dead zone exists but is small)
- **UNTESTED** — Cannot verify without live infrastructure (e.g., needs Docker)
