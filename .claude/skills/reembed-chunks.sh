#!/usr/bin/env bash
# Re-embed all chunks after embedding model change
# Usage: reembed-chunks.sh [--dry-run] [--batch-size N] [--video-id UUID]
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "[reembed-chunks] Starting re-embedding..."
docker compose exec -T app python scripts/reembed_all_chunks.py "$@"
echo "[reembed-chunks] Done."
