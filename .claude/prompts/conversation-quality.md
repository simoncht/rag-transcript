# Conversation Quality Analysis

Analyze conversation behavioral contracts after the shell script has run. The shell script checks structural patterns; your job is to perform semantic analysis that requires reading and understanding code.

## Context

Read `.claude/references/behavioral-contracts.md` for the full contract definitions (MEM-001 through MEM-004, CIT-001).

## Your Tasks

### 1. Evaluate Shell Script Output

Review the output from `conversation-quality.sh`. Note which contracts passed and which were flagged.

### 2. Deep Analysis of Flagged Contracts

For each flagged contract, read the implementing code and determine:

**MEM-001 (Memory Dead Zone):**
- Read `backend/app/api/routes/conversations.py` around line 1242 (`.limit()`) and line 1445 (`message_count >= 15`)
- Read `backend/app/api/utils.py` for `truncate_history_messages()`
- Map the exact lifecycle: when are messages loaded? When are they truncated? When does fact extraction run?
- Is there a bridging mechanism (e.g., facts extracted incrementally before messages leave the window)?
- Calculate the exact dead zone: messages N+1 through M-1 where N=history_limit and M=fact_threshold

**CIT-001 (Citation Tracking):**
- Read `backend/app/models/message.py` line 114 for the default
- Search the codebase for any code that sets `was_used_in_response = False`
- Read the message creation flow in `conversations.py` — does it parse `[N]` markers from LLM output?
- If broken: the field is a lie — every citation is marked "used" regardless of whether the LLM referenced it

**MEM-003 (Active Consolidation):**
- Read `backend/app/services/memory_consolidation.py` for consolidation logic
- Read `backend/app/core/celery_app.py` beat_schedule for when consolidation runs
- Is consolidation ever triggered during the message send flow?
- If only in beat tasks: conversations can accumulate unlimited facts until the next beat run

**MEM-004 (Fact Value Merge):**
- Read `backend/app/services/fact_extraction.py` dedup logic
- When a fact key matches an existing fact, is the value compared?
- If "speaker=Alice" is updated to "speaker=Alice and Bob", does the new value replace the old?

### 3. Report

```
## Conversation Quality Report

### Contract Status
| Contract | Status | Evidence |
|----------|--------|----------|
| MEM-001  | PASS/BROKEN/DEGRADED | [specific finding with file:line] |
| MEM-002  | PASS/BROKEN/DEGRADED | [specific finding] |
| MEM-003  | PASS/BROKEN/DEGRADED | [specific finding] |
| MEM-004  | PASS/BROKEN/DEGRADED | [specific finding] |
| CIT-001  | PASS/BROKEN/DEGRADED | [specific finding] |

### Impact Assessment
[What user-visible problems do broken contracts cause?]

### Recommended Fixes
[Prioritized list of fixes, with specific file:line targets]
```

### 4. Offer to Fix

If contracts are broken, offer specific code changes. Common fixes:
- MEM-001: Lower fact threshold or extract facts incrementally
- CIT-001: Add post-generation marker parsing
- MEM-003: Call consolidation inline when fact_count > MAX_FACTS
- MEM-004: Compare fact values in dedup, update if changed
