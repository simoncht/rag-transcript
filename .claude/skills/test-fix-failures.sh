#!/bin/bash
# Runs pytest, captures failures with full tracebacks, and outputs structured data
# for the LLM prompt to analyze and fix
#
# Usage: /test-fix-failures (manual skill)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo "Backend container not running. Start with: docker compose up -d"
    exit 1
fi

echo "=========================================="
echo "TEST FAILURE DIAGNOSIS"
echo "=========================================="
echo ""

# Run tests with long tracebacks and capture output
echo "Running full test suite with detailed tracebacks..."
echo ""

TEST_OUTPUT=$(docker compose exec -T app pytest -v --tb=long 2>&1) || true
TEST_EXIT=$?

echo "$TEST_OUTPUT"
echo ""

if [ $TEST_EXIT -eq 0 ]; then
    echo "=========================================="
    echo "All tests passing - nothing to fix."
    echo "=========================================="
    exit 0
fi

echo "=========================================="
echo "FAILURE ANALYSIS DATA"
echo "=========================================="
echo ""

# Extract just the failure summaries
echo "--- FAILED TESTS ---"
echo "$TEST_OUTPUT" | grep "^FAILED " || echo "(no FAILED lines found)"
echo ""

# Extract error count
echo "--- ERROR SUMMARY ---"
echo "$TEST_OUTPUT" | tail -5
echo ""

# List test files that had failures
echo "--- AFFECTED TEST FILES ---"
echo "$TEST_OUTPUT" | grep "^FAILED " | sed 's/FAILED //' | sed 's/::.*//' | sort -u || echo "(none)"
echo ""

echo "=========================================="
echo "Failures detected. The LLM prompt will analyze and offer fixes."
echo "=========================================="

exit 1
