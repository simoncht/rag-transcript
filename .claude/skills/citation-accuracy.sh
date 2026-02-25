#!/bin/bash
# citation-accuracy: Validate citation grounding and tracking
# Checks was_used_in_response tracking, jump URL correctness, citation marker consistency.
# Runs statically (no Docker required).

set -euo pipefail

echo "=== Citation Accuracy Gate ==="
echo ""

ISSUES=0

# ── 1. Citation Marker Parsing (CIT-001) ─────────────────────────────
echo "--- CIT-001: Post-Generation Citation Parsing ---"

# Check if any code parses [N] markers from LLM output to update was_used_in_response
MARKER_PARSERS=$(grep -rn '\[.*\]\|citation.*marker\|parse.*\[.*\]\|was_used_in_response\s*=\s*False' \
    backend/app/api/routes/conversations.py \
    backend/app/services/ \
    --include="*.py" 2>/dev/null \
    | grep -v '__pycache__' \
    | grep -v 'system.*prompt\|instruction\|#.*\[\|test\|import' \
    | grep -iv 'default=True' \
    | grep -i 'parse\|marker\|was_used.*False\|re\.find\|regex.*\[' || echo "")

if [ -z "$MARKER_PARSERS" ]; then
    echo "  WARNING: No code parses [N] markers from LLM output"
    echo "  was_used_in_response (message.py:114) defaults to True and is never updated"
    echo "  Contract CIT-001 BROKEN"
    ISSUES=$((ISSUES + 1))
else
    echo "  OK: Citation marker parsing found:"
    echo "$MARKER_PARSERS" | head -5 | sed 's/^/    /'
fi

echo ""

# ── 2. Chunk Reference Indexing (CIT-002) ─────────────────────────────
echo "--- CIT-002: Citation Marker Bounds ---"

# Check system prompt for how chunks are numbered
NUMBERING=$(grep -n '\[1\]\|\[{i\|citation.*number\|chunk.*index\|Source \[' \
    backend/app/api/routes/conversations.py 2>/dev/null \
    | grep -v '__pycache__' \
    | head -5 || echo "")

if [ -n "$NUMBERING" ]; then
    echo "  System prompt chunk numbering references found:"
    echo "$NUMBERING" | sed 's/^/    /'
else
    echo "  No explicit chunk numbering in system prompt found"
fi

# Check if there's validation that [N] doesn't exceed chunk count
BOUNDS_CHECK=$(grep -rn 'max.*marker\|marker.*bound\|citation.*valid\|chunk_ref.*len\|len(chunk' \
    backend/app/api/routes/conversations.py 2>/dev/null \
    | grep -v '__pycache__' \
    | grep -v 'import\|#' || echo "")

if [ -z "$BOUNDS_CHECK" ]; then
    echo "  WARNING: No validation that citation markers [N] are within bounds"
    echo "  LLM could generate [5] when only 4 chunks were provided"
    echo "  Contract CIT-002 POTENTIALLY BROKEN"
    ISSUES=$((ISSUES + 1))
else
    echo "  OK: Citation bounds validation found"
fi

echo ""

# ── 3. Jump URL Timestamp Validation (CIT-003) ───────────────────────
echo "--- CIT-003: Jump URL Timestamps ---"

# Check if jump URL builder validates timestamp is not None
URL_BUILDER=$(grep -n 'jump_url\|youtube.*url\|_build.*url\|start_timestamp\|t=' \
    backend/app/api/routes/conversations.py 2>/dev/null \
    | grep -v '__pycache__' \
    | grep -v '#\|import' \
    | head -10 || echo "")

if [ -n "$URL_BUILDER" ]; then
    echo "  Jump URL references found:"
    echo "$URL_BUILDER" | sed 's/^/    /'

    # Check if None/null timestamp is handled
    NULL_CHECK=$(echo "$URL_BUILDER" | grep -i 'None\|null\|if.*timestamp\|timestamp.*is\b' || echo "")
    if [ -z "$NULL_CHECK" ]; then
        echo "  WARNING: No null-timestamp guard in URL builder"
        echo "  Contract CIT-003 POTENTIALLY BROKEN"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo "  No jump URL builder found in conversations.py"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────
echo "=== Citation Accuracy Summary ==="
if [ "$ISSUES" -eq 0 ]; then
    echo "  All citation contracts verified: PASS"
else
    echo "  $ISSUES contract(s) need attention: NEEDS REVIEW"
    exit 1
fi
