#!/bin/bash
# Auto-run code quality checks (black, ruff) after backend code changes
# Returns exit code 0 if checks pass, 1 if they fail

set -e

echo "🔍 Running quality checks..."

# Check if docker compose is running
if ! docker compose ps app | grep -q "Up"; then
    echo "❌ Backend container not running. Start with: docker compose up -d"
    exit 1
fi

# Run black in check mode (main app code only)
echo "  → Checking code formatting (black)..."
docker compose exec -T app black app/ alembic/ --check --quiet

# Run ruff (main app code only, exclude alembic generated code)
echo "  → Checking code quality (ruff)..."
docker compose exec -T app ruff check app/

echo "✅ Quality checks passed!"
