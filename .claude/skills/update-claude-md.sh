#!/bin/bash
# Analyze codebase changes and suggest updates to CLAUDE.md
# Can be run manually with: /update-claude-md

set -e

echo "📝 Analyzing codebase for CLAUDE.md updates..."
echo ""

# Track if we found changes
NEEDS_UPDATE=0

# Check for new services
echo "🔍 Checking for new services..."
NEW_SERVICES=$(find backend/app/services -name "*.py" -type f -newer CLAUDE.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$NEW_SERVICES" -gt 0 ]; then
    echo "  ⚠️  Found $NEW_SERVICES service file(s) newer than CLAUDE.md"
    find backend/app/services -name "*.py" -type f -newer CLAUDE.md 2>/dev/null | sed 's/^/    - /'
    NEEDS_UPDATE=1
fi

# Check for new migrations
echo ""
echo "🔍 Checking for new database migrations..."
NEW_MIGRATIONS=$(find backend/alembic/versions -name "*.py" -type f -newer CLAUDE.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$NEW_MIGRATIONS" -gt 0 ]; then
    echo "  ⚠️  Found $NEW_MIGRATIONS migration(s) newer than CLAUDE.md"
    find backend/alembic/versions -name "*.py" -type f -newer CLAUDE.md 2>/dev/null | sed 's/^/    - /'
    NEEDS_UPDATE=1
fi

# Check for .env.example changes
echo ""
echo "🔍 Checking configuration changes..."
if [ backend/.env.example -nt CLAUDE.md ]; then
    echo "  ⚠️  .env.example has been updated"
    NEEDS_UPDATE=1
fi

# Check for docker-compose changes
if [ docker-compose.yml -nt CLAUDE.md ]; then
    echo "  ⚠️  docker-compose.yml has been updated"
    NEEDS_UPDATE=1
fi

# Check for changes to key RAG pipeline files
echo ""
echo "🔍 Checking RAG pipeline changes..."
RAG_FILES=(
    "backend/app/api/routes/conversations.py"
    "backend/app/services/llm_providers.py"
    "backend/app/services/vector_store.py"
    "backend/app/services/query_expansion.py"
    "backend/app/services/reranker.py"
)

for file in "${RAG_FILES[@]}"; do
    if [ -f "$file" ] && [ "$file" -nt CLAUDE.md ]; then
        echo "  ⚠️  $file has been updated"
        NEEDS_UPDATE=1
    fi
done

# Check documentation files for context
echo ""
echo "🔍 Checking for new documentation..."
DOC_FILES=$(find . -maxdepth 1 -name "*.md" -type f -newer CLAUDE.md ! -name "CLAUDE.md" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DOC_FILES" -gt 0 ]; then
    echo "  ℹ️  Found $DOC_FILES new documentation file(s):"
    find . -maxdepth 1 -name "*.md" -type f -newer CLAUDE.md ! -name "CLAUDE.md" 2>/dev/null | sed 's/^/    - /'
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$NEEDS_UPDATE" -eq 1 ]; then
    echo "⚠️  CLAUDE.md may need updating!"
    echo ""
    echo "📋 Review these changes and consider updating CLAUDE.md with:"
    echo "   • New services and their purpose"
    echo "   • Database schema changes (new tables, relationships)"
    echo "   • Configuration parameter changes"
    echo "   • Pipeline architecture updates"
    echo "   • Performance characteristics"
    echo ""
    echo "📖 Use the AI prompt guide:"
    echo "   cat .claude/prompts/update-claude-md.md"
    echo ""
    echo "Or manually update CLAUDE.md with relevant changes."
    exit 1
else
    echo "✅ CLAUDE.md appears up-to-date with recent changes."
    echo ""
    echo "💡 If you've made significant architectural changes, consider"
    echo "   reviewing CLAUDE.md to ensure it reflects current state."
    exit 0
fi
