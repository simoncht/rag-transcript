#!/bin/bash
# Regression guard - detects when test edits reduce test count or break passing tests
# Proactive: triggers on backend/tests/**/*.py changes
#
# Compares current test file against the git HEAD version to detect:
# 1. Test count decrease (tests removed)
# 2. Previously-passing tests now failing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo "Backend container not running. Start with: docker compose up -d"
    exit 1
fi

# Get changed test files
STAGED=$(git diff --cached --name-only 2>/dev/null || echo "")
UNSTAGED=$(git diff --name-only 2>/dev/null || echo "")
ALL_CHANGED=$(echo -e "$STAGED\n$UNSTAGED" | sort -u | grep -v "^$" || echo "")

TEST_FILES=$(echo "$ALL_CHANGED" | grep "^backend/tests/.*\.py$" | grep -v "__init__\.py$" | grep -v "conftest\.py$" || echo "")

if [ -z "$TEST_FILES" ]; then
    echo "No test files changed."
    exit 0
fi

WARNINGS=""
HAD_ERRORS=0

for test_file in $TEST_FILES; do
    filename=$(basename "$test_file")
    container_path="${test_file#backend/}"

    # Count test functions in current version
    if [ -f "$PROJECT_ROOT/$test_file" ]; then
        CURRENT_COUNT=$(grep -c "def test_" "$PROJECT_ROOT/$test_file" 2>/dev/null || echo "0")
    else
        # File was deleted
        CURRENT_COUNT=0
    fi

    # Count test functions in HEAD version
    HEAD_COUNT=$(git show HEAD:"$test_file" 2>/dev/null | grep -c "def test_" 2>/dev/null || echo "0")

    # Compare counts
    if [ "$CURRENT_COUNT" -lt "$HEAD_COUNT" ]; then
        DIFF=$((HEAD_COUNT - CURRENT_COUNT))
        WARNINGS="${WARNINGS}\n  $test_file: $DIFF test(s) removed ($HEAD_COUNT -> $CURRENT_COUNT)"
    fi

    # Run the changed test file to verify it passes
    if [ "$CURRENT_COUNT" -gt 0 ] && [ -f "$PROJECT_ROOT/$test_file" ]; then
        echo "Running $filename ($CURRENT_COUNT tests)..."
        if ! docker compose exec -T app pytest "$container_path" -v --tb=short -q 2>&1; then
            HAD_ERRORS=1
            WARNINGS="${WARNINGS}\n  $test_file: Tests failing after edit"
        fi
    fi
done

echo ""

if [ -n "$WARNINGS" ]; then
    echo "=========================================="
    echo "REGRESSION GUARD WARNINGS"
    echo "=========================================="
    echo -e "$WARNINGS"
    echo ""
    echo "Review these changes to ensure they are intentional."
    echo "=========================================="
fi

if [ $HAD_ERRORS -ne 0 ]; then
    exit 1
fi

exit 0
