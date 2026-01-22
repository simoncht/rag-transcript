#!/bin/bash
# Checks all Docker services are running and healthy
# Triggers: At session start, after docker-compose.yml changes

set -e

echo "🐳 Checking Docker services health..."

# Define expected services
EXPECTED_SERVICES=("postgres" "redis" "qdrant" "app" "worker" "beat" "frontend")
FAILED_SERVICES=()
WARNINGS=()

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Start Docker Desktop first."
    exit 1
fi

# Check each service
for service in "${EXPECTED_SERVICES[@]}"; do
    status=$(docker compose ps --format "{{.Service}}:{{.Status}}" 2>/dev/null | grep "^${service}:" | cut -d':' -f2 || echo "not found")

    if [[ "$status" == "not found" ]] || [[ -z "$status" ]]; then
        FAILED_SERVICES+=("$service (not running)")
    elif [[ "$status" != *"Up"* ]]; then
        FAILED_SERVICES+=("$service ($status)")
    else
        echo "  ✓ $service: running"
    fi
done

# Check Ollama (runs on host, not in Docker)
echo ""
echo "🤖 Checking Ollama LLM service..."
if curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null 2>&1; then
    # Get available models
    models=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | head -3 | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
    echo "  ✓ Ollama: running (models: $models)"
else
    WARNINGS+=("Ollama not accessible at localhost:11434 - LLM calls will fail")
fi

# Check Qdrant is accessible
echo ""
echo "🔍 Checking Qdrant vector store..."
if curl -s --max-time 5 http://localhost:6333/collections > /dev/null 2>&1; then
    collections=$(curl -s http://localhost:6333/collections | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
    if [[ -n "$collections" ]]; then
        echo "  ✓ Qdrant: running (collections: $collections)"
    else
        echo "  ✓ Qdrant: running (no collections yet)"
    fi
else
    FAILED_SERVICES+=("qdrant (API not responding)")
fi

# Check PostgreSQL is accessible
echo ""
echo "🗄️  Checking PostgreSQL database..."
if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "  ✓ PostgreSQL: accepting connections"
else
    FAILED_SERVICES+=("postgres (not accepting connections)")
fi

# Check Redis is accessible
echo ""
echo "📮 Checking Redis..."
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo "  ✓ Redis: responding to ping"
else
    FAILED_SERVICES+=("redis (not responding)")
fi

# Report results
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo "⚠️  Warnings:"
    for warning in "${WARNINGS[@]}"; do
        echo "   - $warning"
    done
    echo ""
fi

if [[ ${#FAILED_SERVICES[@]} -gt 0 ]]; then
    echo "❌ Failed services:"
    for service in "${FAILED_SERVICES[@]}"; do
        echo "   - $service"
    done
    echo ""
    echo "Fix with: docker compose up -d"
    exit 1
else
    echo "✅ All services healthy! Ready for development."
fi
