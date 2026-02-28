#!/bin/bash
# Comprehensive test coverage check for code changes
# This skill ensures adequate testing before changes are considered complete
#
# What it does:
# 1. Identifies changed files (staged or recent)
# 2. Finds related test files
# 3. Runs relevant tests
# 4. Analyzes test coverage gaps
# 5. Suggests missing tests
#
# Exit codes:
# 0 - All tests pass and coverage is adequate
# 1 - Tests failed or coverage gaps detected

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "🧪 COMPREHENSIVE TEST COVERAGE CHECK"
echo "=========================================="
echo ""

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo -e "${RED}❌ Backend container not running. Start with: docker compose up -d${NC}"
    exit 1
fi

# 1. Identify changed files
echo -e "${BLUE}📁 Step 1: Identifying changed files...${NC}"
echo ""

# Get staged files
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || echo "")

# Get unstaged modified files
UNSTAGED_FILES=$(git diff --name-only 2>/dev/null || echo "")

# Get recently committed files (last commit)
RECENT_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")

# Combine and dedupe
ALL_CHANGED_FILES=$(echo -e "$STAGED_FILES\n$UNSTAGED_FILES\n$RECENT_FILES" | sort -u | grep -v "^$" || echo "")

if [ -z "$ALL_CHANGED_FILES" ]; then
    echo -e "${YELLOW}⚠️  No changed files detected. Running full test suite...${NC}"
    ALL_CHANGED_FILES="full_suite"
fi

# Filter to Python backend files
BACKEND_CHANGED=$(echo "$ALL_CHANGED_FILES" | grep "^backend/app/.*\.py$" || echo "")
TEST_CHANGED=$(echo "$ALL_CHANGED_FILES" | grep "^backend/tests/.*\.py$" || echo "")

echo "Changed backend files:"
if [ -n "$BACKEND_CHANGED" ]; then
    echo "$BACKEND_CHANGED" | sed 's/^/  - /'
else
    echo "  (none)"
fi
echo ""

echo "Changed test files:"
if [ -n "$TEST_CHANGED" ]; then
    echo "$TEST_CHANGED" | sed 's/^/  - /'
else
    echo "  (none)"
fi
echo ""

# 2. Map changed files to test files
echo -e "${BLUE}📋 Step 2: Mapping to test files...${NC}"
echo ""

RELATED_TESTS=""

for file in $BACKEND_CHANGED; do
    # Extract the module path
    # backend/app/services/chunking.py -> test_chunking.py
    # backend/app/api/routes/conversations.py -> test_conversations.py

    filename=$(basename "$file" .py)

    # Look for corresponding test files
    possible_tests=$(find backend/tests -name "test_${filename}*.py" -o -name "*${filename}_test.py" 2>/dev/null || echo "")

    if [ -n "$possible_tests" ]; then
        RELATED_TESTS="$RELATED_TESTS $possible_tests"
    fi
done

# Add explicitly changed test files
RELATED_TESTS="$RELATED_TESTS $TEST_CHANGED"

# Dedupe
RELATED_TESTS=$(echo "$RELATED_TESTS" | tr ' ' '\n' | sort -u | grep -v "^$" | tr '\n' ' ')

if [ -n "$RELATED_TESTS" ]; then
    echo "Related test files found:"
    echo "$RELATED_TESTS" | tr ' ' '\n' | sed 's/^/  - /'
else
    echo -e "${YELLOW}  No related test files found for changed files${NC}"
fi
echo ""

# 3. Run tests
echo -e "${BLUE}🧪 Step 3: Running tests...${NC}"
echo ""

TEST_EXIT_CODE=0

if [ -n "$RELATED_TESTS" ] && [ "$RELATED_TESTS" != " " ]; then
    echo "Running targeted tests for changed files..."
    echo ""

    # Convert paths to container paths and filter existing files
    CONTAINER_TESTS=""
    for test in $RELATED_TESTS; do
        # Strip 'backend/' prefix for container path
        container_path="${test#backend/}"
        CONTAINER_TESTS="$CONTAINER_TESTS $container_path"
    done

    # Run specific tests (paths relative to /app in container)
    docker compose exec -T app pytest $CONTAINER_TESTS -v --tb=short 2>&1 || TEST_EXIT_CODE=$?
else
    echo "Running full test suite..."
    echo ""

    # Run all tests
    docker compose exec -T app pytest -v --tb=short 2>&1 || TEST_EXIT_CODE=$?
fi

echo ""

# 4. Check for test coverage gaps
echo -e "${BLUE}📊 Step 4: Analyzing test coverage gaps...${NC}"
echo ""

GAPS_FOUND=0
GAP_REPORT=""

for file in $BACKEND_CHANGED; do
    filename=$(basename "$file" .py)
    dirpath=$(dirname "$file")

    # Skip __init__.py and migration files
    if [[ "$filename" == "__init__" ]] || [[ "$dirpath" == *"alembic"* ]]; then
        continue
    fi

    # Check if test file exists
    test_exists=$(find backend/tests -name "test_${filename}*.py" -o -name "*${filename}_test.py" 2>/dev/null | head -1)

    if [ -z "$test_exists" ]; then
        GAPS_FOUND=1
        GAP_REPORT="${GAP_REPORT}\n  ❌ ${file} - No test file found"

        # Suggest test file location
        if [[ "$dirpath" == *"services"* ]]; then
            GAP_REPORT="${GAP_REPORT}\n     Suggested: backend/tests/unit/test_${filename}.py"
        elif [[ "$dirpath" == *"api/routes"* ]]; then
            GAP_REPORT="${GAP_REPORT}\n     Suggested: backend/tests/integration/test_${filename}_endpoints.py"
        fi
    fi
done

if [ $GAPS_FOUND -eq 1 ]; then
    echo -e "${YELLOW}⚠️  Test coverage gaps detected:${NC}"
    echo -e "$GAP_REPORT"
    echo ""
else
    echo -e "${GREEN}✅ All changed files have corresponding tests${NC}"
fi
echo ""

# 5. Check for new code paths without tests
echo -e "${BLUE}🔍 Step 5: Checking for untested code paths...${NC}"
echo ""

NEW_FUNCTIONS=""
for file in $BACKEND_CHANGED; do
    if [ -f "$file" ]; then
        # Look for new function definitions (simplified check)
        funcs=$(git diff HEAD -- "$file" 2>/dev/null | grep "^+.*def " | grep -v "^+++" | sed 's/^+//' || echo "")
        if [ -n "$funcs" ]; then
            NEW_FUNCTIONS="${NEW_FUNCTIONS}\n  📝 $file:\n$(echo "$funcs" | sed 's/^/     /')"
        fi
    fi
done

if [ -n "$NEW_FUNCTIONS" ]; then
    echo -e "${YELLOW}New/modified functions detected:${NC}"
    echo -e "$NEW_FUNCTIONS"
    echo ""
    echo -e "${YELLOW}⚠️  Verify these functions have test coverage${NC}"
else
    echo -e "${GREEN}✅ No new function definitions detected${NC}"
fi
echo ""

# 6. Summary
echo "=========================================="
echo "📋 SUMMARY"
echo "=========================================="
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed${NC}"
else
    echo -e "${RED}❌ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

if [ $GAPS_FOUND -eq 1 ]; then
    echo -e "${YELLOW}⚠️  Test coverage gaps detected - consider adding tests${NC}"
fi

echo ""

# Exit with appropriate code
if [ $TEST_EXIT_CODE -ne 0 ]; then
    exit 1
elif [ $GAPS_FOUND -eq 1 ]; then
    # Warning but don't fail - gaps are advisory
    exit 0
else
    exit 0
fi
