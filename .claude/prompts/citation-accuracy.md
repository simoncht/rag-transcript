# Citation Accuracy Analysis

Analyze citation behavioral contracts after the shell script has run. The shell script checks structural patterns; your job is to trace the full citation flow from system prompt through storage to frontend display.

## Context

Read `.claude/references/behavioral-contracts.md` for contracts CIT-001 through CIT-003.

## Your Tasks

### 1. Evaluate Shell Script Output

Review the output from `citation-accuracy.sh`. Note which contracts passed and which were flagged.

### 2. Trace the Full Citation Flow

Read the following files and trace how citations work end-to-end:

1. **System prompt** (`backend/app/api/routes/conversations.py`): How does the prompt instruct the LLM to cite sources? What format (e.g., `[1]`, `[Source 1]`)?
2. **Chunk assembly**: How are chunks numbered when building the context? Is numbering 0-indexed or 1-indexed?
3. **LLM response**: After streaming completes, is the response parsed for citation markers?
4. **Storage** (`backend/app/models/message.py`): How are `MessageChunkReference` records created? Is `was_used_in_response` ever updated?
5. **Frontend** (`frontend/src/components/shared/CitationBadge.tsx`): How does the UI render citations? Does it rely on `was_used_in_response`?

### 3. Deep Analysis of Flagged Contracts

**CIT-001 (was_used_in_response tracking):**
- Search the entire codebase for any code that sets `was_used_in_response = False`
- Read the message creation flow — does it parse `[N]` markers from the completed LLM response?
- If broken: every citation appears "used" even if the LLM ignored the chunk — this undermines citation quality metrics

**CIT-002 (Marker bounds):**
- Count how many chunks are provided to the LLM in the system prompt
- Check if there's validation that prevents `[5]` when only 4 chunks exist
- Check for off-by-one errors (0-indexed chunks but 1-indexed markers, or vice versa)

**CIT-003 (Jump URL timestamps):**
- Read the URL builder function
- Does it handle `None` timestamps (e.g., for document chunks that don't have timestamps)?
- Does it correctly convert chunk `start_timestamp` (seconds) to YouTube `t=` parameter?
- Are there edge cases (timestamp=0, negative timestamps, very large timestamps)?

### 4. Report

```
## Citation Accuracy Report

### Citation Flow Trace
[Step-by-step description of how citations flow through the system]

### Contract Status
| Contract | Status | Evidence |
|----------|--------|----------|
| CIT-001  | PASS/BROKEN | [specific finding with file:line] |
| CIT-002  | PASS/BROKEN | [specific finding] |
| CIT-003  | PASS/BROKEN | [specific finding] |

### Impact Assessment
[What user-visible problems do broken contracts cause?]

### Recommended Fixes
[Prioritized list with specific code changes]
```

### 5. Offer to Fix

Common citation fixes:
- CIT-001: After LLM streaming completes, parse response text for `[N]` markers using regex, set `was_used_in_response=False` for chunk_refs not referenced
- CIT-002: Add bounds validation before storing chunk references
- CIT-003: Add null-timestamp guard in URL builder, handle document chunks separately
