#!/bin/bash
# Targeted test runner - runs only tests matching changed files
# Designed for proactive use (<5s instead of 12-15s for full suite)
#
# Usage: Triggered automatically when backend/app/**/*.py changes
# Maps changed source files to their test files and runs only those

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo "Backend container not running. Start with: docker compose up -d"
    exit 1
fi

# Get changed backend source files (staged + unstaged)
STAGED=$(git diff --cached --name-only 2>/dev/null || echo "")
UNSTAGED=$(git diff --name-only 2>/dev/null || echo "")
ALL_CHANGED=$(echo -e "$STAGED\n$UNSTAGED" | sort -u | grep -v "^$" || echo "")

# Filter to backend source files (not tests, not __init__)
SOURCE_FILES=$(echo "$ALL_CHANGED" | grep "^backend/app/.*\.py$" | grep -v "__init__\.py$" || echo "")

if [ -z "$SOURCE_FILES" ]; then
    # If triggered on a test file change, run that test file directly
    TEST_FILES=$(echo "$ALL_CHANGED" | grep "^backend/tests/.*\.py$" | grep -v "__init__\.py$" || echo "")
    if [ -n "$TEST_FILES" ]; then
        CONTAINER_PATHS=""
        for tf in $TEST_FILES; do
            CONTAINER_PATHS="$CONTAINER_PATHS ${tf#backend/}"
        done
        echo "Running changed test files..."
        docker compose exec -T app pytest $CONTAINER_PATHS -v --tb=short -q 2>&1
        exit $?
    fi
    echo "No relevant backend files changed."
    exit 0
fi

# Map source files to test files
TESTS_TO_RUN=""
MISSING_TESTS=""

for file in $SOURCE_FILES; do
    filename=$(basename "$file" .py)
    dirpath=$(dirname "$file")

    # Skip migration files
    if [[ "$dirpath" == *"alembic"* ]]; then
        continue
    fi

    # Find matching test files
    # Convention: backend/app/services/chunking.py -> backend/tests/unit/test_chunking*.py
    #             backend/app/api/routes/videos.py -> backend/tests/*/test_video*.py
    matches=$(find "$PROJECT_ROOT/backend/tests" -name "test_${filename}*.py" -o -name "test_${filename}_*.py" 2>/dev/null || echo "")

    if [ -n "$matches" ]; then
        TESTS_TO_RUN="$TESTS_TO_RUN $matches"
    else
        MISSING_TESTS="$MISSING_TESTS $file"
    fi
done

# Dedupe
TESTS_TO_RUN=$(echo "$TESTS_TO_RUN" | tr ' ' '\n' | sort -u | grep -v "^$" | tr '\n' ' ')

if [ -z "$TESTS_TO_RUN" ] || [ "$TESTS_TO_RUN" = " " ]; then
    if [ -n "$MISSING_TESTS" ]; then
        echo "No test files found for changed files:"
        echo "$MISSING_TESTS" | tr ' ' '\n' | grep -v "^$" | sed 's/^/  /'
    fi
    exit 0
fi

# Convert to container-relative paths
CONTAINER_PATHS=""
for test in $TESTS_TO_RUN; do
    # Strip everything up to and including 'backend/'
    rel="${test#*backend/}"
    CONTAINER_PATHS="$CONTAINER_PATHS $rel"
done

# Count test files
NUM_FILES=$(echo "$CONTAINER_PATHS" | wc -w | tr -d ' ')
echo "Running $NUM_FILES test file(s) matching changed code..."

# Run targeted tests with compact output
docker compose exec -T app pytest $CONTAINER_PATHS -v --tb=short -q 2>&1
TEST_EXIT=$?

# Report missing test coverage (informational, not failure)
if [ -n "$MISSING_TESTS" ]; then
    echo ""
    echo "Files without tests:"
    echo "$MISSING_TESTS" | tr ' ' '\n' | grep -v "^$" | sed 's/^/  /'
fi

exit $TEST_EXIT
