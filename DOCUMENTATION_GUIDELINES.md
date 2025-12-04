# Documentation Guidelines for AI Coding Agents

**Target Audience**: Claude Code, OpenAI Codex, Cursor, and all AI-powered development assistants
**Purpose**: Maintain consistent, high-quality documentation across development sessions
**Last Updated**: 2025-12-03

---

## Documentation File Structure

This project maintains **4 core documentation files**, each with a specific purpose:

### 1. **RESUME.md** ⭐ (Quick Reference)
**When to Update**: After every major milestone, phase completion, or critical fix
**Update Style**: Replace/update sections (not append)
**Required Sections**:
- **Last Updated** timestamp at top
- **Status** one-liner (current phase + completion %)
- **System Check** - health check commands
- **Phase Summaries** - completed phases with ✅ checkboxes
- **In-Flight Work** - current active tasks with timestamps
- **Technical Notes** - configuration quirks, workarounds, model details
- **Common Commands** - frequently used bash commands
- **Key Files** - navigation guide to important files

**Level of Detail**: Concise bullet points, actionable commands, quick copy-paste snippets
**Example Entry**:
```markdown
## ✅ Phase 3.1 COMPLETE: Video Collections

### Backend (100%)
- ✅ Database migration (collections, collection_videos tables)
- ✅ 7 API endpoints (CRUD collections, add/remove videos)

### Git Commits:
- `07e511a` - Backend API and migration
```

**What NOT to Include**: Implementation details, debugging steps, error traces

---

### 2. **PROGRESS.md** 📝 (Detailed History)
**When to Update**: After significant changes (bug fixes, features, architecture decisions)
**Update Style**: Append chronologically (preserve history)
**Required Sections**:
- **Status** header matching RESUME.md
- **Recent Changes** - timestamped (YYYY-MM-DD) entries
- **Issues Fixed** - problem description, root cause, solution
- **Key Files Modified** - list changed files with line numbers
- **Phase N: Implementation** - detailed breakdown of each development phase

**Level of Detail**: Technical depth, debugging steps, error messages, code snippets
**Example Entry**:
```markdown
### Fixed Multi-Video Vector Search (2025-12-03)
- **Issue**: Qdrant Filter using AND logic for video IDs (returned zero results)
- **Root Cause**: `must_conditions` applied to all filters in vector_store.py:241-249
- **Fix**: Separated into `must` (user_id) and `should` (video_ids for OR logic)
- **Files Modified**:
  - `backend/app/services/vector_store.py` (lines 229-267)
- **Result**: Multi-video conversations now retrieve chunks from all selected videos
- **Commit**: `2780390`
```

**What to Include**:
- Error messages (full stack traces)
- Root cause analysis
- Alternative approaches considered
- Performance metrics (response times, token counts)

---

### 3. **README.md** 📚 (Architecture Overview)
**When to Update**: Only when architecture/technology stack changes
**Update Style**: Replace sections (keep stable)
**Required Sections**:
- **Project Description** - high-level purpose
- **Architecture Diagram** - component relationships
- **Technology Stack** - languages, frameworks, databases
- **Database Schema** - table descriptions
- **API Endpoints** - routes and request/response schemas
- **Development Setup** - installation instructions
- **Deployment** - production setup

**Level of Detail**: Architectural decisions, system design rationale
**Example Entry**:
```markdown
## Technology Stack

**Backend**:
- FastAPI (Python 3.11) - REST API framework
- SQLAlchemy - ORM with PostgreSQL
- Celery - Distributed task queue
- Qdrant - Vector database for embeddings

**Why Qdrant?** Chosen over pgvector for:
- Superior filtering performance (10x faster on large datasets)
- Native support for metadata filtering
- Horizontal scaling capabilities
```

**What NOT to Change**: Don't update for minor bug fixes, dependency version bumps, or temporary workarounds

---

### 4. **PHASE_*.md** 🎯 (Feature Specifications)
**When to Create**: Before implementing major features (Phase 3.1, Phase 4, etc.)
**Update Style**: Create once, update during implementation if scope changes
**Required Sections**:
- **Objective** - what problem this solves
- **Requirements** - backend/frontend checklists
- **API Contracts** - endpoint specs with examples
- **Database Changes** - schema modifications
- **UI Mockups** - (if frontend work)
- **Testing Plan** - how to verify completion

**Level of Detail**: Spec-level detail, acceptance criteria, edge cases
**Example Entry**:
```markdown
## Phase 3.1: Video Collections

### Backend Requirements
- [ ] Create `collections` table with JSONB metadata field
- [ ] Add `collection_videos` join table (many-to-many)
- [ ] Implement 7 API endpoints:
  * `POST /api/v1/collections` - Create collection
  * `GET /api/v1/collections` - List with video counts
  ...

### API Contract: Create Collection
**Endpoint**: `POST /api/v1/collections`
**Request**:
```json
{
  "name": "Machine Learning Course",
  "description": "CS229 Lectures",
  "metadata": {
    "instructor": "Andrew Ng",
    "semester": "Fall 2024"
  }
}
```
**Response**: `201 Created` with collection object
```

---

## Update Workflow for AI Agents

### 🚀 After Completing a Major Feature:
1. **Update RESUME.md**:
   - Change status header: `Phase X.Y COMPLETE`
   - Add ✅ checkboxes to completed section
   - Clear "In-Flight Work" or update with next tasks
   - Add git commit hashes to "Git Commits" section
   - Update "Last Updated" timestamp

2. **Append to PROGRESS.md**:
   - Add timestamped section: `## Phase X.Y: [Feature Name] (YYYY-MM-DD)`
   - List implementation details, files modified
   - Document any issues encountered and fixes

3. **Update README.md** (if needed):
   - Only if new services, databases, or architecture changes
   - Add new API endpoints to endpoints list
   - Update technology stack if new dependencies

4. **Create PHASE_*.md** (for next phase):
   - Before starting new major work
   - Get user approval on spec before implementation

### 🐛 After Fixing a Critical Bug:
1. **Update RESUME.md**:
   - Update "Last Updated" timestamp
   - Add one-liner to "In-Flight Work" with commit hash

2. **Append to PROGRESS.md**:
   - Add "### Fixed [Bug Name] (YYYY-MM-DD)" section
   - Include: Issue, Root Cause, Fix, Files Modified, Result, Commit hash

3. **Do NOT update README.md** (unless bug revealed architecture issue)

### 🔧 After Minor Changes (dependency updates, config tweaks):
1. **Update RESUME.md** only:
   - Timestamp in "In-Flight Work" section
   - One-line description

2. **Optionally append to PROGRESS.md** if change is significant

---

## Style Guidelines

### ✅ DO:
- Use **bold** for key terms (Issue, Root Cause, Fix, Result)
- Include file paths with line numbers: `backend/app/services/vector_store.py:229-267`
- Add git commit hashes: `` `2780390` ``
- Use checkboxes: `- ✅ Feature complete` or `- [ ] In progress`
- Include timestamps: `(2025-12-03)` or `**Last Updated**: 2025-12-03 21:40 PST`
- Add code blocks with language tags: ` ```python `, ` ```bash `
- Link between docs: `See PHASE_3_ENHANCEMENTS.md for details`
- Include copy-paste commands: `docker-compose restart app`

### ❌ DON'T:
- Use vague language: "fixed some issues" → ❌ (be specific)
- Omit error messages when documenting bug fixes
- Update RESUME.md with verbose implementation details (that's for PROGRESS.md)
- Change README.md for minor fixes
- Delete old PROGRESS.md entries (append only)
- Use relative dates: "yesterday" → ❌ (use YYYY-MM-DD)
- Forget to update "Last Updated" timestamps

---

## Markdown Formatting Standards

### Headers:
```markdown
# Top-level title (use once per file)
## Major sections
### Subsections
#### Detail sections (rare)
```

### Code Blocks:
````markdown
```bash
# Shell commands with comments
docker-compose ps
```

```python
# Python code with language tag
def example():
    return "properly formatted"
```
````

### Lists:
```markdown
- ✅ Completed items with checkmark
- ⏳ In-progress items with hourglass
- [ ] Uncompleted checklist items
- 1. Numbered lists for sequential steps
```

### Emphasis:
```markdown
**Bold** for key terms, filenames, headers
`code` for inline code, commands, file paths
> Blockquotes for important warnings
```

---

## Example Commit Messages (for reference)

When updating documentation, use clear commit messages:

```bash
# Good examples:
git commit -m "docs: Update RESUME.md - Phase 3.1 complete"
git commit -m "docs: Add multi-video search bug fix to PROGRESS.md"
git commit -m "docs: Create PHASE_4_AUTH.md specification"

# Bad examples:
git commit -m "update docs" ❌ (too vague)
git commit -m "fixed readme" ❌ (lowercase, no context)
```

---

## Quality Checklist

Before committing documentation updates, verify:

- [ ] RESUME.md timestamp updated
- [ ] Status header matches current phase completion
- [ ] Git commit hashes included (7 characters: `` `abc1234` ``)
- [ ] File paths include line numbers where relevant
- [ ] Code blocks have language tags
- [ ] All checkboxes use ✅ (complete) or [ ] (incomplete)
- [ ] Timestamps use YYYY-MM-DD format
- [ ] No broken internal links (e.g., `See PHASE_3.md` when file is `PHASE_3_ENHANCEMENTS.md`)
- [ ] Bash commands are copy-paste ready (no placeholders without explanation)

---

## When in Doubt

**Ask yourself**:
1. Is this a quick reference item? → **RESUME.md**
2. Is this a detailed implementation story? → **PROGRESS.md**
3. Is this an architecture decision? → **README.md**
4. Is this a feature specification? → **PHASE_*.md**

**Golden Rule**: Future developers (human or AI) should be able to:
- Understand current status in < 2 minutes (RESUME.md)
- Debug past issues without re-reading code (PROGRESS.md)
- Understand system design without running the app (README.md)
- Implement new features from spec alone (PHASE_*.md)

---

## Version Control for Docs

- Always commit documentation updates **together with code changes** in the same commit
- Exception: If docs need fixes (typos, clarifications), use separate `docs:` prefixed commits
- When merging branches, reconcile PROGRESS.md entries chronologically

---

**This guideline is itself a living document. If you discover better documentation practices while working on this project, update this file and note the change in PROGRESS.md.**
