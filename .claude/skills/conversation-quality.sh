#!/bin/bash
# conversation-quality: Validate conversation behavioral contracts
# Checks memory retention, history limits, fact extraction timing, citation tracking.
# Runs statically (no Docker required).

set -euo pipefail

echo "=== Conversation Quality Gate ==="
echo ""

ISSUES=0

# ── 1. Memory Dead Zone Check (MEM-001) ──────────────────────────────
echo "--- MEM-001: Memory Dead Zone ---"

# Extract history limit from conversations.py (.limit(N) on message history query)
# Use sed instead of grep -P for macOS compatibility
HISTORY_LIMIT=$(sed -n '1235,1250p' backend/app/api/routes/conversations.py \
    | grep '\.limit(' \
    | sed 's/.*\.limit(\([0-9]*\)).*/\1/' \
    | head -1 || echo "")

if [ -z "$HISTORY_LIMIT" ]; then
    # Broader search: any .limit(N) with small N
    HISTORY_LIMIT=$(grep '\.limit(' backend/app/api/routes/conversations.py \
        | sed 's/.*\.limit(\([0-9]*\)).*/\1/' \
        | awk '$1 > 0 && $1 <= 50' \
        | head -1 || echo "")
fi

# Extract fact extraction threshold (message_count >= N)
FACT_THRESHOLD=$(grep 'message_count.*>=' backend/app/api/routes/conversations.py \
    | grep -o '>= *[0-9]*' \
    | grep -o '[0-9]*' \
    | head -1 || echo "")

if [ -n "$HISTORY_LIMIT" ] && [ -n "$FACT_THRESHOLD" ]; then
    echo "  History limit: $HISTORY_LIMIT messages"
    echo "  Fact extraction threshold: $FACT_THRESHOLD messages"

    # Dead zone exists if facts aren't extracted before messages leave the window
    # With limit=10 and threshold=15, turns 11-14 are in the dead zone
    if [ "$FACT_THRESHOLD" -gt "$HISTORY_LIMIT" ]; then
        GAP=$((FACT_THRESHOLD - HISTORY_LIMIT))
        echo "  WARNING: Dead zone of $GAP turns (messages $((HISTORY_LIMIT + 1))-$((FACT_THRESHOLD - 1)) lost before fact extraction)"
        echo "  Contract MEM-001 BROKEN"
        ISSUES=$((ISSUES + 1))
    else
        echo "  OK: No dead zone (threshold <= history limit)"
    fi
else
    echo "  SKIP: Could not extract history limit ($HISTORY_LIMIT) or fact threshold ($FACT_THRESHOLD)"
fi

echo ""

# ── 2. Citation Tracking Check (CIT-001) ─────────────────────────────
echo "--- CIT-001: Citation was_used_in_response Tracking ---"

# Check if was_used_in_response is ever set to False anywhere
FALSE_SETS=$(grep -rn 'was_used_in_response\s*=\s*False\|was_used_in_response.*False' \
    backend/app/ --include="*.py" 2>/dev/null | grep -v '__pycache__' | grep -v 'default=' || echo "")

if [ -z "$FALSE_SETS" ]; then
    echo "  WARNING: was_used_in_response is never set to False in codebase"
    echo "  Default is True (message.py:114) — all citations marked as 'used' regardless of LLM output"
    echo "  Contract CIT-001 BROKEN"
    ISSUES=$((ISSUES + 1))
else
    echo "  OK: was_used_in_response is set to False in:"
    echo "$FALSE_SETS" | head -5 | sed 's/^/    /'
fi

echo ""

# ── 3. Consolidation Trigger Check (MEM-003) ─────────────────────────
echo "--- MEM-003: Active Conversation Consolidation ---"

# Check if consolidation is called anywhere outside of beat/scheduled tasks
INLINE_CONSOLIDATION=$(grep -rn 'consolidat\|MemoryConsolidat' \
    backend/app/api/ backend/app/services/fact_extraction.py \
    --include="*.py" 2>/dev/null \
    | grep -v '__pycache__' \
    | grep -v 'import' \
    | grep -v '#.*consolidat' || echo "")

BEAT_CONSOLIDATION=$(grep -rn 'consolidat' \
    backend/app/tasks/ backend/app/core/celery_app.py \
    --include="*.py" 2>/dev/null \
    | grep -v '__pycache__' \
    | grep -v 'import' || echo "")

if [ -z "$INLINE_CONSOLIDATION" ]; then
    echo "  WARNING: Consolidation not called during active conversations"
    echo "  Only runs via beat tasks (24h stale threshold)"
    echo "  Contract MEM-003 BROKEN"
    ISSUES=$((ISSUES + 1))
else
    echo "  OK: Consolidation called inline:"
    echo "$INLINE_CONSOLIDATION" | head -3 | sed 's/^/    /'
fi

echo ""

# ── 4. Fact Dedup Value Check (MEM-004) ───────────────────────────────
echo "--- MEM-004: Fact Value Merge on Update ---"

# Check if fact dedup compares values (not just keys)
DEDUP_CODE=$(grep -A5 -n 'dedup\|duplicate\|existing.*fact\|fact.*exist' \
    backend/app/services/fact_extraction.py 2>/dev/null \
    | grep -v '__pycache__' || echo "")

VALUE_COMPARE=$(echo "$DEDUP_CODE" | grep -i 'value\|fact_value\|content' || echo "")

if [ -z "$VALUE_COMPARE" ]; then
    echo "  WARNING: Fact dedup may not compare values (only keys)"
    echo "  Updated facts could be silently dropped instead of merged"
    echo "  Contract MEM-004 POTENTIALLY BROKEN"
    ISSUES=$((ISSUES + 1))
else
    echo "  OK: Dedup appears to check values"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────
echo "=== Conversation Quality Summary ==="
if [ "$ISSUES" -eq 0 ]; then
    echo "  All contracts verified: PASS"
else
    echo "  $ISSUES contract(s) need attention: NEEDS REVIEW"
    exit 1
fi
