#!/bin/bash
# content-parity: Validate document and video processing parity
# Checks enrichment equivalence, chunking features, and truncation warnings.
# Runs statically (no Docker required).

set -euo pipefail

echo "=== Content Parity Gate ==="
echo ""

ISSUES=0

# ── 1. Enrichment Parity (PAR-001) ───────────────────────────────────
echo "--- PAR-001: Enrichment Parity ---"

# Count enrichment-related calls in document_tasks vs video_tasks
DOC_ENRICHMENT=$(grep -c 'ContextualEnricher\|enrich\|Enricher' \
    backend/app/tasks/document_tasks.py 2>/dev/null || echo "0")

VIDEO_ENRICHMENT=$(grep -c 'ContextualEnricher\|enrich\|Enricher' \
    backend/app/tasks/video_tasks.py 2>/dev/null || echo "0")

echo "  Enrichment references: document_tasks=$DOC_ENRICHMENT, video_tasks=$VIDEO_ENRICHMENT"

if [ "$DOC_ENRICHMENT" -eq 0 ] && [ "$VIDEO_ENRICHMENT" -gt 0 ]; then
    echo "  WARNING: Document tasks have NO enrichment calls but video tasks do"
    echo "  Contract PAR-001 BROKEN"
    ISSUES=$((ISSUES + 1))
elif [ "$DOC_ENRICHMENT" -eq 0 ] && [ "$VIDEO_ENRICHMENT" -eq 0 ]; then
    echo "  NOTE: Neither pipeline has enrichment calls (may use shared service)"
else
    echo "  OK: Both pipelines reference enrichment"
fi

# Check if both pass full_text for contextual enrichment
DOC_FULLTEXT=$(grep -c 'full_text' backend/app/tasks/document_tasks.py 2>/dev/null || echo "0")
VIDEO_FULLTEXT=$(grep -c 'full_text' backend/app/tasks/video_tasks.py 2>/dev/null || echo "0")

echo "  full_text references: document_tasks=$DOC_FULLTEXT, video_tasks=$VIDEO_FULLTEXT"

if [ "$VIDEO_FULLTEXT" -gt 0 ] && [ "$DOC_FULLTEXT" -eq 0 ]; then
    echo "  WARNING: Video tasks pass full_text for contextual enrichment but documents don't"
    ISSUES=$((ISSUES + 1))
fi

echo ""

# ── 2. Truncation Warning (PAR-002) ──────────────────────────────────
echo "--- PAR-002: Enrichment Truncation Warning ---"

# Check if enrichment.py logs a warning when full_text is truncated
TRUNCATION_LINE=$(grep -n '48000\|truncat' backend/app/services/enrichment.py 2>/dev/null || echo "")
WARNING_LOG=$(grep -n 'logger\.warn\|logging\.warn' backend/app/services/enrichment.py 2>/dev/null \
    | grep -i 'truncat' || echo "")

if [ -n "$TRUNCATION_LINE" ]; then
    echo "  Truncation found in enrichment.py:"
    echo "$TRUNCATION_LINE" | head -3 | sed 's/^/    /'

    if [ -z "$WARNING_LOG" ]; then
        echo "  WARNING: Truncation occurs silently (no logger.warning)"
        echo "  Contract PAR-002 BROKEN"
        ISSUES=$((ISSUES + 1))
    else
        echo "  OK: Truncation logs a warning"
    fi
else
    echo "  No truncation logic found in enrichment.py"
fi

echo ""

# ── 3. Document Chunker Metadata ─────────────────────────────────────
echo "--- Content-Specific Metadata ---"

# Check if document_chunker sets section/heading metadata
DOC_METADATA=$(grep -n 'section_heading\|page_number\|metadata\[' \
    backend/app/services/document_chunker.py 2>/dev/null | head -5 || echo "")

if [ -n "$DOC_METADATA" ]; then
    echo "  Document chunker metadata fields:"
    echo "$DOC_METADATA" | sed 's/^/    /'
else
    echo "  NOTE: No section_heading or page_number metadata in document chunker"
fi

# Check if video chunking sets timestamp metadata
VIDEO_METADATA=$(grep -n 'start_time\|timestamp\|metadata\[' \
    backend/app/services/chunking.py 2>/dev/null | head -5 || echo "")

if [ -n "$VIDEO_METADATA" ]; then
    echo "  Video chunker metadata fields:"
    echo "$VIDEO_METADATA" | sed 's/^/    /'
else
    echo "  NOTE: No timestamp metadata in video chunker"
fi

echo ""

# ── 4. Processing Pipeline Stages ────────────────────────────────────
echo "--- Pipeline Stage Comparison ---"

# Extract pipeline stages from both task files
DOC_STAGES=$(grep -c 'status.*=\|update_status\|\.status\s*=' \
    backend/app/tasks/document_tasks.py 2>/dev/null || echo "0")
VIDEO_STAGES=$(grep -c 'status.*=\|update_status\|\.status\s*=' \
    backend/app/tasks/video_tasks.py 2>/dev/null || echo "0")

echo "  Status transitions: document_tasks=$DOC_STAGES, video_tasks=$VIDEO_STAGES"

if [ "$VIDEO_STAGES" -gt 0 ] && [ "$DOC_STAGES" -eq 0 ]; then
    echo "  WARNING: Video tasks track status but document tasks don't"
    ISSUES=$((ISSUES + 1))
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────
echo "=== Content Parity Summary ==="
if [ "$ISSUES" -eq 0 ]; then
    echo "  All content parity contracts verified: PASS"
else
    echo "  $ISSUES issue(s) need attention: NEEDS REVIEW"
    exit 1
fi
