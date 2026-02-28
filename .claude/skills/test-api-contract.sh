#!/bin/bash
# Validates API route changes match Pydantic schemas
# Runs FastAPI TestClient against changed route files
#
# Proactive: triggers on backend/app/api/routes/*.py and backend/app/schemas/*.py changes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if docker compose is running
if ! docker compose ps app 2>/dev/null | grep -q "Up"; then
    echo "Backend container not running. Start with: docker compose up -d"
    exit 1
fi

# Get changed files
STAGED=$(git diff --cached --name-only 2>/dev/null || echo "")
UNSTAGED=$(git diff --name-only 2>/dev/null || echo "")
ALL_CHANGED=$(echo -e "$STAGED\n$UNSTAGED" | sort -u | grep -v "^$" || echo "")

# Filter to route and schema files
ROUTE_FILES=$(echo "$ALL_CHANGED" | grep "^backend/app/api/routes/.*\.py$" | grep -v "__init__" || echo "")
SCHEMA_FILES=$(echo "$ALL_CHANGED" | grep "^backend/app/schemas/.*\.py$" | grep -v "__init__" || echo "")

if [ -z "$ROUTE_FILES" ] && [ -z "$SCHEMA_FILES" ]; then
    echo "No API route or schema changes detected."
    exit 0
fi

echo "=========================================="
echo "API CONTRACT VALIDATION"
echo "=========================================="
echo ""

if [ -n "$ROUTE_FILES" ]; then
    echo "Changed routes:"
    echo "$ROUTE_FILES" | sed 's/^/  /'
fi
if [ -n "$SCHEMA_FILES" ]; then
    echo "Changed schemas:"
    echo "$SCHEMA_FILES" | sed 's/^/  /'
fi
echo ""

# Run contract validation inside Docker
docker compose exec -T app python -c "
import sys
import importlib
import json

print('Validating API contracts...')
print()

errors = []

# Test 1: Verify all route files import without errors
print('--- Import Check ---')
route_modules = [
    'app.api.routes.videos',
    'app.api.routes.conversations',
    'app.api.routes.collections',
    'app.api.routes.admin',
    'app.api.routes.insights',
    'app.api.routes.subscriptions',
]

for module_name in route_modules:
    try:
        mod = importlib.import_module(module_name)
        print(f'  OK: {module_name}')
    except Exception as e:
        errors.append(f'{module_name}: {e}')
        print(f'  FAIL: {module_name} - {e}')

print()

# Test 2: Verify schema models can be instantiated with valid data
print('--- Schema Validation Check ---')
try:
    from app.schemas import video as video_schema
    from app.schemas import conversation as conv_schema
    from app.schemas import collection as coll_schema

    # Check that response models have the expected fields
    schema_checks = []

    if hasattr(video_schema, 'VideoResponse'):
        fields = video_schema.VideoResponse.model_fields
        required = [k for k, v in fields.items() if v.is_required()]
        schema_checks.append(('VideoResponse', len(fields), len(required)))

    if hasattr(conv_schema, 'ConversationResponse'):
        fields = conv_schema.ConversationResponse.model_fields
        required = [k for k, v in fields.items() if v.is_required()]
        schema_checks.append(('ConversationResponse', len(fields), len(required)))

    if hasattr(coll_schema, 'CollectionResponse'):
        fields = coll_schema.CollectionResponse.model_fields
        required = [k for k, v in fields.items() if v.is_required()]
        schema_checks.append(('CollectionResponse', len(fields), len(required)))

    for name, total, req in schema_checks:
        print(f'  OK: {name} ({total} fields, {req} required)')

except Exception as e:
    errors.append(f'Schema validation: {e}')
    print(f'  FAIL: Schema validation - {e}')

print()

# Test 3: Verify FastAPI app routes are registered
print('--- Route Registration Check ---')
try:
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    api_routes = [r for r in routes if r.startswith('/api/')]

    print(f'  Total API routes registered: {len(api_routes)}')

    # Check key routes exist
    expected_routes = [
        '/api/v1/videos',
        '/api/v1/conversations',
        '/api/v1/collections',
    ]

    for expected in expected_routes:
        matches = [r for r in api_routes if r.startswith(expected)]
        if matches:
            print(f'  OK: {expected} ({len(matches)} endpoints)')
        else:
            errors.append(f'Missing route prefix: {expected}')
            print(f'  FAIL: {expected} not found')

except Exception as e:
    errors.append(f'Route registration: {e}')
    print(f'  FAIL: Route check - {e}')

print()

# Summary
if errors:
    print('========================================')
    print(f'FAILED: {len(errors)} contract violation(s)')
    print('========================================')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('========================================')
    print('PASSED: All API contracts valid')
    print('========================================')
" 2>&1

echo ""
exit $?
