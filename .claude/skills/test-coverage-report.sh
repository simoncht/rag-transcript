#!/bin/bash
# Generate a live test coverage report with per-file breakdown
# Shows uncovered functions sorted by priority (critical services first)
#
# Usage: /test-coverage-report (manual skill)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo "Backend container not running. Start with: docker compose up -d"
    exit 1
fi

echo "=========================================="
echo "LIVE TEST COVERAGE REPORT"
echo "=========================================="
echo ""
echo "Running pytest with coverage analysis..."
echo "(this may take 15-30 seconds)"
echo ""

# Run pytest with coverage, output JSON for parsing and terminal for display
COVERAGE_OUTPUT=$(docker compose exec -T app pytest --cov=app --cov-report=term-missing --cov-report=json:/tmp/coverage.json -q --tb=no 2>&1) || true

echo "$COVERAGE_OUTPUT"
echo ""

# Extract and parse the JSON coverage report
echo "=========================================="
echo "DETAILED COVERAGE ANALYSIS"
echo "=========================================="
echo ""

docker compose exec -T app python -c "
import json
import sys

try:
    with open('/tmp/coverage.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print('Coverage JSON not found. Tests may have failed to run.')
    sys.exit(1)

files = data.get('files', {})
totals = data.get('totals', {})

# Print overall summary
print(f'Overall Coverage: {totals.get(\"percent_covered\", 0):.1f}%')
print(f'Total Statements: {totals.get(\"num_statements\", 0)}')
print(f'Covered: {totals.get(\"covered_lines\", 0)}')
print(f'Missing: {totals.get(\"missing_lines\", 0)}')
print()

# Critical service files to prioritize
critical_prefixes = [
    'app/services/',
    'app/api/routes/',
    'app/tasks/',
]

# Categorize files
critical_files = []
other_files = []

for filepath, info in files.items():
    summary = info.get('summary', {})
    pct = summary.get('percent_covered', 0)
    stmts = summary.get('num_statements', 0)
    missing = summary.get('missing_lines', 0)

    # Skip tiny files
    if stmts < 5:
        continue

    entry = {
        'path': filepath,
        'pct': pct,
        'stmts': stmts,
        'missing': missing,
        'missing_lines': info.get('missing_lines', []),
    }

    is_critical = any(filepath.startswith(p) for p in critical_prefixes)
    if is_critical:
        critical_files.append(entry)
    else:
        other_files.append(entry)

# Sort by coverage % ascending (worst first)
critical_files.sort(key=lambda x: x['pct'])
other_files.sort(key=lambda x: x['pct'])

# Print critical services
print('--- CRITICAL SERVICES (sorted by coverage, worst first) ---')
print(f'{\"File\":<55} {\"Stmts\":>5} {\"Miss\":>5} {\"Cover\":>6}')
print('-' * 75)
for f in critical_files:
    print(f'{f[\"path\"]:<55} {f[\"stmts\"]:>5} {f[\"missing\"]:>5} {f[\"pct\"]:>5.0f}%')

print()

# Print other files
print('--- OTHER FILES ---')
print(f'{\"File\":<55} {\"Stmts\":>5} {\"Miss\":>5} {\"Cover\":>6}')
print('-' * 75)
for f in other_files[:20]:  # Top 20 worst
    print(f'{f[\"path\"]:<55} {f[\"stmts\"]:>5} {f[\"missing\"]:>5} {f[\"pct\"]:>5.0f}%')

if len(other_files) > 20:
    print(f'  ... and {len(other_files) - 20} more files')

print()

# Recommendations
print('--- RECOMMENDED NEXT TESTS ---')
print()
priority = [f for f in critical_files if f['pct'] < 50][:5]
for i, f in enumerate(priority, 1):
    print(f'{i}. {f[\"path\"]} ({f[\"pct\"]:.0f}% covered, {f[\"missing\"]} lines missing)')
print()
print('Use /test-generate <filepath> to generate tests for any of these files.')
" 2>&1 || echo "Failed to parse coverage JSON. Check test output above for errors."

echo ""
echo "=========================================="
echo "Report complete."
echo "=========================================="
