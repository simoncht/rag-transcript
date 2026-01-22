# AI Prompt: Update CLAUDE.md

This prompt can be used with any AI assistant (OpenAI Codex, GPT-4, Claude, etc.) to update CLAUDE.md after significant codebase changes.

---

## Prompt for AI Assistant

```
I need you to update CLAUDE.md to reflect recent changes in this codebase. CLAUDE.md serves as a guide for future AI coding assistants working in this repository.

### Your Task

1. Analyze recent changes to these key areas:
   - New services in `backend/app/services/`
   - Changes to RAG pipeline in `backend/app/api/routes/conversations.py`
   - New database migrations in `backend/alembic/versions/`
   - Configuration updates in `backend/.env.example`
   - New architectural patterns or processing flows
   - Performance optimizations or feature additions

2. Update CLAUDE.md following these guidelines:

**DO include:**
- High-level architecture requiring multiple files to understand
- New processing pipelines with performance characteristics
- Significant services with purpose and key functionality
- Configuration changes affecting system behavior
- Database schema changes affecting table relationships
- Important implementation details not obvious from code
- New external dependencies or infrastructure

**DO NOT include:**
- Generic development practices
- Information discoverable from single file reading
- Detailed API documentation (use /docs)
- Complete file/component listings
- Step-by-step basic task guides
- Motivational content or general tips

### Structure to Maintain

Keep existing CLAUDE.md structure:
1. Project Overview - Current state summary
2. Quick Start - Commands to get running
3. Development Commands - Docker and local development
4. Architecture - Backend/frontend structure, key services
5. RAG Pipeline Architecture - Query processing with performance
6. Database - Tables and relationships
7. Infrastructure - Docker services and dependencies
8. Important Implementation Details - Recent features
9. Code Style - Brief guidelines
10. Key Configuration Files - Quick reference

### Specific Updates Needed

Check and update:
- [ ] Current LLM model name (in Quick Start)
- [ ] New services (in Key Services table)
- [ ] RAG Pipeline flow (if query processing changed)
- [ ] Database tables (if migrations added)
- [ ] Configuration parameters (if .env.example changed)
- [ ] Performance metrics (if optimizations done)
- [ ] Implementation Details (if new features added)

### Writing Guidelines

- Be concise - each section scannable in 30 seconds
- Focus on architectural "why" not code "what"
- Include performance context when relevant
- Update model/version references to current
- Keep file under 200 lines
- Remove outdated information

### Current Context

CLAUDE.md currently documents:
- Query expansion with multi-query retrieval
- Conversation memory with fact extraction
- Comprehensive logging and observability
- Citation system with rich metadata
- 8-step RAG pipeline with timing breakdown

Look for changes that help future AI assistants understand the codebase better.

### Output Format

Provide:
1. Brief summary of changes (2-3 bullets)
2. Full updated CLAUDE.md content
3. Reasoning for major additions/removals
```

---

## Usage Examples

### With OpenAI Codex or GPT-4

```bash
# Copy the prompt above and provide it with context:
cat .claude/prompts/update-claude-md.md | pbcopy

# Then in your AI chat:
# "Use this prompt to update CLAUDE.md. Here are the recent changes:
# - Added new service X for Y
# - Modified RAG pipeline to include Z
# - Updated database with table W"
```

### With Claude Code

```bash
# Run the detection skill first:
./.claude/skills/update-claude-md.sh

# Then use the prompt with context from the output
```

### With GitHub Copilot Chat

```
@workspace Use the prompt in .claude/prompts/update-claude-md.md to update CLAUDE.md based on recent changes to the codebase.
```

---

## Automation Options

### Git Hook (Post-Commit)

Create `.git/hooks/post-commit`:
```bash
#!/bin/bash
# Check if CLAUDE.md needs updating after commits

if ./.claude/skills/update-claude-md.sh; then
    exit 0
else
    echo ""
    echo "💡 Tip: Consider updating CLAUDE.md with recent changes"
    echo "   Run: ./.claude/skills/update-claude-md.sh"
    exit 0  # Don't block commit
fi
```

### CI/CD Check

Add to GitHub Actions workflow:
```yaml
- name: Check CLAUDE.md freshness
  run: |
    ./.claude/skills/update-claude-md.sh || echo "::warning::CLAUDE.md may need updating"
```

### Pre-Push Hook

Create `.git/hooks/pre-push`:
```bash
#!/bin/bash
# Remind to update CLAUDE.md before pushing

if ! ./.claude/skills/update-claude-md.sh; then
    echo ""
    read -p "CLAUDE.md may be outdated. Continue push? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

---

## Tips for Effective Updates

1. **Run detection first** - Use `update-claude-md.sh` to identify changes
2. **Be selective** - Not every change needs documentation
3. **Focus on architecture** - Document system-level understanding
4. **Keep it fresh** - Update after major features, not minor tweaks
5. **Test with AI** - After updating, test if AI understands the changes

---

## File Structure

```
.claude/
├── skills/
│   └── update-claude-md.sh     # Detection script
├── prompts/
│   └── update-claude-md.md     # This file - AI prompt guide
└── skills.json                 # Skill registry
```

---

## Maintenance

Update this prompt when:
- CLAUDE.md structure changes significantly
- New documentation standards are adopted
- Additional context becomes important for AI assistants
- Automation workflows change

---

Last updated: 2026-01-17
