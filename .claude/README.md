# Claude Code Skills for RAG Transcript

This directory contains automated skills that help with development workflow on the RAG Transcript project.

## Available Skills

### Code Quality Skills

| Skill | Triggers After | What It Does |
|-------|---------------|--------------|
| **test-targeted** | `backend/app/**/*.py`, `backend/tests/**/*.py` | Runs only tests matching changed files |
| **test-before-complete** | Manual (`/test-before-complete`) | Comprehensive test coverage check with gap analysis, uses sub-agents |
| **quality-check** | `backend/app/**/*.py` | Runs `black --check` and `ruff check` |
| **type-check** | `frontend/src/**/*.{ts,tsx}` | Runs `npm run type-check` |

### Infrastructure Skills

| Skill | Triggers After | What It Does |
|-------|---------------|--------------|
| **docker-health** | `docker-compose.yml`, `Dockerfile`, session start | Checks all 7 Docker services + Qdrant |

### RAG Pipeline Skills

| Skill | Triggers After | What It Does |
|-------|---------------|--------------|
| **rag-smoke-test** | RAG service files (`chunking.py`, `embeddings.py`, `vector_store.py`, etc.) | Tests full pipeline: embed → retrieve → LLM |
| **pipeline-status** | `video_tasks.py`, manual | Shows processing status, queue depth, system config |

### Documentation Skills

| Skill | Triggers After | What It Does |
|-------|---------------|--------------|
| **update-claude-md** | Service files, migrations, config changes, manual | Detects if CLAUDE.md needs updating based on code changes |

## Automation Triggers

Skills run automatically when you modify files matching their patterns:

```
Edit backend/app/services/chunking.py
  → quality-check runs
  → rag-smoke-test runs

Edit frontend/src/components/Chat.tsx
  → type-check runs

Edit docker-compose.yml
  → docker-health runs
```

## Manual Execution

Run any skill manually:

```bash
# Check all Docker services
.claude/skills/docker-health.sh

# Test RAG pipeline
.claude/skills/rag-smoke-test.sh

# View pipeline status
.claude/skills/pipeline-status.sh

# Run tests
.claude/skills/test-targeted.sh

# Check code quality
.claude/skills/quality-check.sh

# Check TypeScript types
.claude/skills/type-check.sh

# Check if CLAUDE.md needs updating
.claude/skills/update-claude-md.sh
```

## Skill Details

### docker-health.sh
Verifies your development environment is ready:
- All 7 Docker containers running (postgres, redis, qdrant, app, worker, beat, frontend)
- PostgreSQL accepting connections
- Redis responding to ping
- Qdrant API available

### rag-smoke-test.sh
Tests the complete RAG pipeline:
1. **Embedding Service**: Generates test embedding, reports dimensions and timing
2. **Vector Store**: Connects to Qdrant, reports collection stats
3. **Database**: Checks video and conversation counts
4. **Retrieval**: Runs actual search query, shows top result with score
5. **LLM Provider**: Initializes LLM service, reports model and provider

### pipeline-status.sh
System diagnostics for debugging:
- Video processing status (pending, completed, failed, stuck)
- Chunk indexing status (indexed vs unindexed)
- Qdrant vector count (detects DB/Qdrant mismatches)
- Celery queue depth
- Conversation statistics
- Current RAG configuration

### test-coverage-check.sh (test-before-complete)
Comprehensive test coverage verification with gap analysis:
1. **Change Detection**: Identifies modified files (staged, unstaged, recent commits)
2. **Test Mapping**: Maps source files to their corresponding test files
3. **Test Execution**: Runs relevant unit and integration tests
4. **Gap Analysis**: Identifies files without tests, new functions without coverage
5. **Recommendations**: Suggests specific tests to add

**Usage with Claude Code (recommended):**
```bash
# Invoke as skill - uses sub-agents for parallel analysis
/test-before-complete
```

**Manual usage:**
```bash
./.claude/skills/test-coverage-check.sh
```

**Sub-agents used:**
- `unit-test-runner` - Runs unit tests in parallel
- `integration-test-runner` - Runs integration tests in parallel
- `coverage-analyzer` - Analyzes test coverage gaps

See `.claude/prompts/test-before-complete.md` for the full Claude Code prompt with sub-agent configuration.

### update-claude-md.sh
Analyzes codebase for changes that should be documented in CLAUDE.md:
- Detects new services in `backend/app/services/`
- Finds new database migrations
- Checks for `.env.example` and `docker-compose.yml` updates
- Identifies changes to key RAG pipeline files
- Lists new documentation files
- Suggests what to update in CLAUDE.md

**Usage with AI assistants:**
```bash
# Check if updates needed
./.claude/skills/update-claude-md.sh

# Get AI prompt for updating
cat .claude/prompts/update-claude-md.md

# Copy prompt and use with OpenAI Codex, GPT-4, Claude, etc.
```

The skill also provides a structured prompt in `.claude/prompts/update-claude-md.md` that can be used with any AI assistant to systematically update CLAUDE.md based on recent changes.

## Setup Requirements

1. **Docker Compose** must be running:
   ```bash
   docker compose up -d
   ```

2. **Frontend dependencies** (for type-check):
   ```bash
   cd frontend && npm install
   ```

## Configuration

Skills are configured in `skills.json`:

```json
{
  "name": "rag-smoke-test",
  "command": ".claude/skills/rag-smoke-test.sh",
  "trigger": {
    "proactive": true,
    "patterns": [
      "backend/app/services/chunking.py",
      "backend/app/services/embeddings.py",
      ...
    ]
  }
}
```

## Adding New Skills

1. Create script in `.claude/skills/`
2. Make executable: `chmod +x .claude/skills/your-skill.sh`
3. Add entry to `skills.json` with trigger patterns
