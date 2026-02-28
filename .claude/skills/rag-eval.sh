#!/usr/bin/env bash
# RAG Evaluation — run retrieval metrics against golden dataset
# Usage: rag-eval.sh [--baseline] [--compare [NAME]] [--k N] [--tags TAG1 TAG2]
set -euo pipefail

cd "$(dirname "$0")/../.."

ARGS="$@"

if echo "$ARGS" | grep -q -- '--compare'; then
    # Extract baseline name (default: "baseline")
    BASELINE_NAME=$(echo "$ARGS" | sed -n 's/.*--compare[= ]\?\([^ ]*\).*/\1/p')
    BASELINE_NAME="${BASELINE_NAME:-baseline}"
    echo "[rag-eval] Comparing against baseline: $BASELINE_NAME"
    docker compose exec -T app python scripts/run_evaluation.py --compare "$BASELINE_NAME"
elif echo "$ARGS" | grep -q -- '--baseline'; then
    echo "[rag-eval] Running evaluation and saving baseline..."
    docker compose exec -T app python scripts/run_evaluation.py --baseline $ARGS
else
    echo "[rag-eval] Running evaluation..."
    docker compose exec -T app python scripts/run_evaluation.py --report $ARGS
fi

echo "[rag-eval] Done."
