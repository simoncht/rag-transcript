#!/bin/bash
# Auto-run TypeScript type checks after frontend code changes
# Returns exit code 0 if type checks pass, 1 if they fail

set -e

echo "📝 Running TypeScript type checks..."

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "❌ node_modules not found. Run: npm install"
    exit 1
fi

# Run type check
npm run type-check

echo "✅ Type checks passed!"
