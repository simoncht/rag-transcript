#!/bin/bash
# doc-drift-check.sh — Detect documentation drift against code
# Proactive skill: fires when config, services, models, or celery change
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CLAUDE_MD="$ROOT/CLAUDE.md"
MEMORY_MD="$HOME/.claude/projects/-Users-simonchia-projects-rag-transcript/memory/MEMORY.md"
CONFIG_PY="$ROOT/backend/app/core/config.py"
CELERY_PY="$ROOT/backend/app/core/celery_app.py"
SERVICES_DIR="$ROOT/backend/app/services"
SKILLS_JSON="$ROOT/.claude/skills.json"
ENV_EXAMPLE="$ROOT/backend/.env.example"

DRIFT_FOUND=0

echo "=== Documentation Drift Check ==="
echo ""

# 1. Check service count: files vs CLAUDE.md table
echo "--- Service Files vs CLAUDE.md ---"
SERVICE_FILES=$(ls "$SERVICES_DIR"/*.py 2>/dev/null | grep -v __pycache__ | grep -v __init__ | wc -l | tr -d ' ')
CLAUDE_SERVICES=$(grep -c '| `.*\.py`' "$CLAUDE_MD" 2>/dev/null || echo 0)
echo "INFO: $SERVICE_FILES service files, CLAUDE.md lists $CLAUDE_SERVICES (table is curated, not exhaustive)"

# 2. Check beat schedule count
echo ""
echo "--- Celery Beat Schedule vs CLAUDE.md ---"
BEAT_TASKS=$(grep -c '"task":' "$CELERY_PY" 2>/dev/null || echo 0)
CLAUDE_TASKS=$(grep -c '^| `' "$CLAUDE_MD" 2>/dev/null | head -1)
# Count rows in the Scheduled Tasks table specifically
CLAUDE_BEAT_ROWS=$(sed -n '/### Scheduled Tasks/,/^###/p' "$CLAUDE_MD" | grep -c '^| `' 2>/dev/null || echo 0)
if [ "$BEAT_TASKS" -ne "$CLAUDE_BEAT_ROWS" ]; then
    echo "DRIFT: $BEAT_TASKS beat tasks in code, CLAUDE.md Scheduled Tasks table has $CLAUDE_BEAT_ROWS rows"
    DRIFT_FOUND=1
else
    echo "OK: $BEAT_TASKS scheduled tasks match"
fi

# 3. Check key config defaults match CLAUDE.md
echo ""
echo "--- Config Defaults vs CLAUDE.md ---"
check_config() {
    local key="$1"
    local expected_in_claude="$2"
    local actual
    actual=$(grep "^ *${key}:" "$CONFIG_PY" | head -1 | sed 's/.*= *//' | tr -d ' ')
    if [ -n "$actual" ] && ! grep -q "${expected_in_claude}" "$CLAUDE_MD" 2>/dev/null; then
        echo "DRIFT: $key = $actual in config.py, but '$expected_in_claude' not found in CLAUDE.md"
        DRIFT_FOUND=1
    else
        echo "OK: $key"
    fi
}
check_config "retrieval_top_k" "RETRIEVAL_TOP_K=20"
check_config "reranking_top_k" "RERANKING_TOP_K=7"

# 4. Check skill counts in MEMORY.md
echo ""
echo "--- Skill Counts vs MEMORY.md ---"
if [ -f "$SKILLS_JSON" ] && [ -f "$MEMORY_MD" ]; then
    # Count proactive skills in skills.json
    PROACTIVE_COUNT=$(python3 -c "
import json
with open('$SKILLS_JSON') as f:
    data = json.load(f)
count = sum(1 for s in data.get('skills', []) if s.get('trigger', {}).get('proactive'))
print(count)
" 2>/dev/null || echo "?")

    # Count manual skills in skills.json
    MANUAL_COUNT=$(python3 -c "
import json
with open('$SKILLS_JSON') as f:
    data = json.load(f)
count = sum(1 for s in data.get('skills', []) if s.get('trigger', {}).get('manual'))
print(count)
" 2>/dev/null || echo "?")

    MEMORY_PROACTIVE=$(grep 'Proactive Skills.*— [0-9]' "$MEMORY_MD" | sed 's/.*— //' | sed 's/ total.*//' || echo "?")
    MEMORY_MANUAL=$(grep 'Manual Skills.*— [0-9]' "$MEMORY_MD" | sed 's/.*— //' | sed 's/ total.*//' || echo "?")

    if [ "$PROACTIVE_COUNT" != "$MEMORY_PROACTIVE" ]; then
        echo "DRIFT: $PROACTIVE_COUNT proactive skills in skills.json, MEMORY.md says $MEMORY_PROACTIVE"
        DRIFT_FOUND=1
    else
        echo "OK: $PROACTIVE_COUNT proactive skills match"
    fi

    if [ "$MANUAL_COUNT" != "$MEMORY_MANUAL" ]; then
        echo "DRIFT: $MANUAL_COUNT manual skills in skills.json, MEMORY.md says $MEMORY_MANUAL"
        DRIFT_FOUND=1
    else
        echo "OK: $MANUAL_COUNT manual skills match"
    fi
fi

# 5. Check .env.example has all config.py fields
echo ""
echo "--- Config Fields vs .env.example ---"
MISSING_VARS=0
for var in enable_reranking enable_query_expansion enable_relevance_grading enable_hyde enable_bm25_search enable_query_rewriting enrichment_max_workers; do
    VAR_UPPER=$(echo "$var" | tr '[:lower:]' '[:upper:]')
    if grep -q "^ *${var}:" "$CONFIG_PY" 2>/dev/null && ! grep -q "$VAR_UPPER" "$ENV_EXAMPLE" 2>/dev/null; then
        echo "DRIFT: $VAR_UPPER is in config.py but missing from .env.example"
        MISSING_VARS=$((MISSING_VARS + 1))
        DRIFT_FOUND=1
    fi
done
if [ "$MISSING_VARS" -eq 0 ]; then
    echo "OK: All checked config fields present in .env.example"
fi

# 6. Check for stale Phase references in production code
echo ""
echo "--- Stale Phase References ---"
PHASE_REFS=$(grep -rn "Phase [0-9]" "$ROOT/backend/app/" --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "test_" | grep -v ".pyc" | wc -l | tr -d ' ')
if [ "$PHASE_REFS" -gt 0 ]; then
    echo "WARNING: $PHASE_REFS 'Phase N' references in production code (may be stale)"
    grep -rn "Phase [0-9]" "$ROOT/backend/app/" --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "test_" | grep -v ".pyc" | head -5
    # Don't flag as drift — some phase refs may be intentional (algorithm phases in vector_store.py)
else
    echo "OK: No Phase references in production code"
fi

echo ""
echo "==================================="
if [ "$DRIFT_FOUND" -eq 1 ]; then
    echo "RESULT: Documentation drift detected — review items above"
    exit 1
else
    echo "RESULT: All documentation checks pass"
    exit 0
fi
