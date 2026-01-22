#!/bin/bash
# Auto-run pytest tests after backend code changes
# Returns exit code 0 if tests pass, 1 if they fail

set -e

echo "🧪 Running tests..."

# Check if docker compose is running
if ! docker compose ps app | grep -q "Up"; then
    echo "❌ Backend container not running. Start with: docker compose up -d"
    exit 1
fi

# Run pytest with verbose output
docker compose exec -T app pytest -v --tb=short

echo "✅ All tests passed!"
