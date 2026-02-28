#!/bin/bash
# rag-quality-gate: Validate RAG retrieval quality
# Tests intent classification accuracy, coverage metrics, and summary availability.
# Requires live Docker infrastructure.

set -euo pipefail

echo "=== RAG Quality Gate ==="
echo ""

# Check Docker is running
if ! docker compose ps --format json 2>/dev/null | grep -q "app"; then
    echo "SKIP: Docker services not running. Start with 'docker compose up -d'"
    exit 0
fi

# ── 1. Intent Classification Benchmark ──────────────────────────────

echo "--- Intent Classification Benchmark ---"

INTENT_PASS=0
INTENT_FAIL=0
INTENT_TOTAL=0

run_intent_test() {
    local query="$1"
    local expected="$2"
    local num_videos="$3"
    local mode="${4:-summarize}"
    INTENT_TOTAL=$((INTENT_TOTAL + 1))

    result=$(docker compose exec -T app python -c "
from app.services.intent_classifier import IntentClassifier
c = IntentClassifier()
r = c.classify_sync('$query', '$mode', $num_videos)
print(r.intent.value)
" 2>/dev/null | tr -d '\r' || echo "error")

    if [ "$result" = "$expected" ]; then
        INTENT_PASS=$((INTENT_PASS + 1))
        echo "  PASS: '$query' -> $result (expected $expected)"
    else
        INTENT_FAIL=$((INTENT_FAIL + 1))
        echo "  FAIL: '$query' -> $result (expected $expected)"
    fi
}

# Broad queries -> COVERAGE (multi-video)
run_intent_test "what are the different themes can each of these sources be grouped by?" "coverage" 40
run_intent_test "what topics do these videos cover?" "coverage" 40
run_intent_test "group these by subject matter" "coverage" 40
run_intent_test "organize these sources into categories" "coverage" 40
run_intent_test "what kind of content do I have?" "coverage" 40
run_intent_test "what can I learn from all these videos?" "coverage" 40
run_intent_test "how would you organize these videos?" "coverage" 40
run_intent_test "what is each video about?" "coverage" 40
run_intent_test "list the main ideas from every source" "coverage" 40
run_intent_test "give me an overview of everything" "coverage" 40
run_intent_test "summarize all the videos" "coverage" 40

# Document/single-source queries -> COVERAGE
run_intent_test "what is this document all about?" "coverage" 1
run_intent_test "what is this about?" "coverage" 1
run_intent_test "summarize this PDF" "coverage" 1
run_intent_test "what is this file about?" "coverage" 1
run_intent_test "what is it about?" "coverage" 1
run_intent_test "what is this podcast about?" "coverage" 1

# Specific queries -> PRECISION
run_intent_test "why do schools kill creativity?" "precision" 10
run_intent_test "what did Ken Robinson say about mistakes?" "precision" 10
run_intent_test "find the part about procrastination" "precision" 5
run_intent_test "when did they discuss AI?" "precision" 5
run_intent_test "what is the dispute handling process?" "precision" 1 "deep_dive"

echo ""
echo "Intent Classification: $INTENT_PASS/$INTENT_TOTAL passed ($INTENT_FAIL failed)"
echo ""

# ── 2. Summary Coverage ──────────────────────────────────────────────

echo "--- Summary Coverage ---"

SUMMARY_STATS=$(docker compose exec -T app python -c "
from app.db.base import SessionLocal
from app.models import Video
db = SessionLocal()
total = db.query(Video).filter(Video.status == 'completed', Video.is_deleted.is_(False)).count()
with_summary = db.query(Video).filter(Video.status == 'completed', Video.summary.isnot(None), Video.is_deleted.is_(False)).count()
pct = (with_summary / total * 100) if total > 0 else 0
print(f'{with_summary}/{total} ({pct:.0f}%)')
db.close()
" 2>/dev/null | tr -d '\r' || echo "error")

echo "  Videos with summaries: $SUMMARY_STATS"

# Extract percentage for threshold check (macOS-compatible, no grep -P)
SUMMARY_PCT=$(echo "$SUMMARY_STATS" | grep -o '[0-9]*%' | grep -o '[0-9]*' || echo "0")
if [ "$SUMMARY_PCT" -lt 50 ]; then
    echo "  WARNING: <50% summary coverage - COVERAGE path degraded"
    echo "  ACTION: Run POST /api/v1/admin/videos/backfill-summaries"
else
    echo "  OK: Summary coverage sufficient for COVERAGE retrieval path"
fi

echo ""

# ── 3. Chunk Limit Adequacy ──────────────────────────────────────────

echo "--- Chunk Limit Adequacy ---"

docker compose exec -T app python -c "
from app.db.base import SessionLocal
from app.models import Collection
from app.models.collection import CollectionVideo
from sqlalchemy import func
db = SessionLocal()

# Find collections by video count
stats = (
    db.query(
        Collection.id,
        Collection.name,
        func.count(CollectionVideo.video_id).label('video_count'),
    )
    .join(CollectionVideo, Collection.id == CollectionVideo.collection_id)
    .filter(Collection.is_deleted.is_(False))
    .group_by(Collection.id, Collection.name)
    .having(func.count(CollectionVideo.video_id) > 5)
    .order_by(func.count(CollectionVideo.video_id).desc())
    .limit(10)
    .all()
)

if not stats:
    print('  No collections with >5 videos found')
else:
    for coll_id, name, count in stats:
        coverage_limit = min(count, 50)
        print(f'  Collection \"{name[:30]}\": {count} videos, coverage_limit={coverage_limit}')

db.close()
" 2>/dev/null || echo "  Could not query collections"

echo ""

# ── 4. Memory Health ─────────────────────────────────────────────────

echo "--- Memory Health ---"

MEMORY_ISSUES=0

MEMORY_STATS=$(docker compose exec -T app python -c "
from app.db.base import SessionLocal
from app.models import Conversation
from app.models.conversation import ConversationFact
from sqlalchemy import func
db = SessionLocal()

# Find conversations with >30 messages
long_convos = db.query(Conversation).filter(
    Conversation.message_count > 30,
    Conversation.is_deleted.is_(False)
).all()

if not long_convos:
    print('NO_LONG_CONVOS')
else:
    for conv in long_convos[:5]:
        early_facts = db.query(ConversationFact).filter(
            ConversationFact.conversation_id == conv.id,
            ConversationFact.source_turn <= 5
        ).count()
        total_facts = db.query(ConversationFact).filter(
            ConversationFact.conversation_id == conv.id
        ).count()
        print(f'CONV|{conv.id}|{conv.message_count}|{total_facts}|{early_facts}')

db.close()
" 2>/dev/null | tr -d '\r' || echo "ERROR")

if echo "$MEMORY_STATS" | grep -q "ERROR"; then
    echo "  Could not query memory health"
elif echo "$MEMORY_STATS" | grep -q "NO_LONG_CONVOS"; then
    echo "  No conversations with >30 messages found (cannot test)"
else
    while IFS='|' read -r prefix conv_id msg_count total_facts early_facts; do
        if [ "$prefix" = "CONV" ]; then
            echo "  Conversation $conv_id: $msg_count msgs, $total_facts facts, $early_facts early-turn facts"
            if [ "$total_facts" -eq 0 ] && [ "$msg_count" -gt 15 ]; then
                echo "    WARNING: No facts extracted despite $msg_count messages"
                MEMORY_ISSUES=$((MEMORY_ISSUES + 1))
            elif [ "$early_facts" -eq 0 ] && [ "$msg_count" -gt 30 ]; then
                echo "    WARNING: No early-turn facts preserved (turns 1-5)"
                MEMORY_ISSUES=$((MEMORY_ISSUES + 1))
            fi
        fi
    done <<< "$MEMORY_STATS"
fi

echo ""

# ── 5. Citation Tracking ─────────────────────────────────────────────

echo "--- Citation Tracking ---"

CITATION_STATS=$(docker compose exec -T app python -c "
from app.db.base import SessionLocal
from app.models.message import MessageChunkReference
from sqlalchemy import func
db = SessionLocal()

total = db.query(func.count(MessageChunkReference.id)).scalar() or 0
used_true = db.query(func.count(MessageChunkReference.id)).filter(
    MessageChunkReference.was_used_in_response.is_(True)
).scalar() or 0
used_false = db.query(func.count(MessageChunkReference.id)).filter(
    MessageChunkReference.was_used_in_response.is_(False)
).scalar() or 0

print(f'{total}|{used_true}|{used_false}')
db.close()
" 2>/dev/null | tr -d '\r' || echo "ERROR")

CITATION_ISSUE=0
if echo "$CITATION_STATS" | grep -q "ERROR"; then
    echo "  Could not query citation tracking"
else
    IFS='|' read -r total_refs true_refs false_refs <<< "$CITATION_STATS"
    echo "  Total chunk references: $total_refs"
    echo "  was_used_in_response=True: $true_refs"
    echo "  was_used_in_response=False: $false_refs"

    if [ "$total_refs" -gt 0 ] && [ "$false_refs" -eq 0 ]; then
        echo "  WARNING: All citations marked as 'used' — tracking likely broken (CIT-001)"
        echo "  was_used_in_response is never set to False after LLM generation"
        CITATION_ISSUE=1
    fi
fi

echo ""

# ── 6. BM25 Activation ──────────────────────────────────────────────

echo "--- BM25 Activation ---"

BM25_STATUS=$(docker compose exec -T app python -c "
from app.core.config import settings
print('ENABLED' if settings.enable_bm25_search else 'DISABLED')
" 2>/dev/null | tr -d '\r' || echo "ERROR")

if echo "$BM25_STATUS" | grep -q "ERROR"; then
    echo "  Could not check BM25 config"
elif [ "$BM25_STATUS" = "DISABLED" ]; then
    echo "  WARNING: BM25 hybrid search is disabled"
    echo "  Set enable_bm25_search=True for 5-15% retrieval improvement"
else
    echo "  OK: BM25 hybrid search enabled"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────

echo "=== Quality Gate Summary ==="
if [ "$INTENT_FAIL" -eq 0 ]; then
    echo "  Intent Classification: ALL PASSED"
else
    echo "  Intent Classification: $INTENT_FAIL FAILURES"
fi
echo "  Summary Coverage: $SUMMARY_STATS"
echo "  Memory Issues: $MEMORY_ISSUES"
echo "  Citation Tracking: $([ "$CITATION_ISSUE" -eq 0 ] && echo 'OK' || echo 'BROKEN')"
echo "  BM25: $BM25_STATUS"

if [ "$INTENT_FAIL" -gt 0 ] || [ "$SUMMARY_PCT" -lt 50 ] || [ "$MEMORY_ISSUES" -gt 0 ] || [ "$CITATION_ISSUE" -gt 0 ]; then
    echo ""
    echo "  RESULT: NEEDS ATTENTION"
    exit 1
else
    echo ""
    echo "  RESULT: PASS"
fi
