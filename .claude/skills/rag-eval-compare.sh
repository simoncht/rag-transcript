#!/usr/bin/env bash
# RAG Evaluation Compare — compare current metrics against saved baseline
# Usage: rag-eval-compare.sh [baseline-name]
set -euo pipefail

cd "$(dirname "$0")/../.."

BASELINE_NAME="${1:-baseline}"

echo "[rag-eval-compare] Comparing against baseline: $BASELINE_NAME"
docker compose exec -T app python scripts/run_evaluation.py --compare "$BASELINE_NAME"

echo "[rag-eval-compare] Done."
