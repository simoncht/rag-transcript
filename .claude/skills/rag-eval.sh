#!/usr/bin/env bash
# RAG Evaluation — run retrieval metrics against golden dataset
# Usage: rag-eval.sh [--baseline] [--k N] [--tags TAG1 TAG2]
set -euo pipefail

cd "$(dirname "$0")/../.."

ARGS="$@"

# Check if --baseline flag is passed
if echo "$ARGS" | grep -q -- '--baseline'; then
    echo "[rag-eval] Running evaluation and saving baseline..."
    docker compose exec -T app python scripts/run_evaluation.py --baseline $ARGS
else
    echo "[rag-eval] Running evaluation..."
    docker compose exec -T app python scripts/run_evaluation.py --report $ARGS
fi

echo "[rag-eval] Done."
