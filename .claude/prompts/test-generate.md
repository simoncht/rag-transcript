# Test Generate

Generate comprehensive tests for a specific source file. The user will specify which file to generate tests for (e.g., `/test-generate backend/app/services/enrichment.py`).

## Your Tasks

### 1. Learn Existing Patterns

Before writing any tests, read these exemplar test files to understand the codebase's testing conventions:

- `backend/tests/unit/test_chunking_service.py` - class-per-concern organization
- `backend/tests/unit/test_llm_providers.py` - LLM service mocking patterns
- `backend/tests/conftest.py` - shared fixtures

Note the patterns: how mocks are structured, how fixtures are used, assertion style, class organization.

### 2. Analyze the Target File

Read the source file specified by the user. Identify:

- **Public functions/methods** that need testing (skip private helpers unless complex)
- **Dependencies** that need mocking (database sessions, external services, HTTP clients)
- **Error paths** (try/except blocks, validation errors, edge cases)
- **Return types** and data transformations
- **Configuration** the code reads from settings

### 3. Determine Test File Location

Follow the mapping convention:

| Source | Test Location |
|--------|--------------|
| `backend/app/services/X.py` | `backend/tests/unit/test_X.py` |
| `backend/app/api/routes/X.py` | `backend/tests/integration/test_X_endpoints.py` |
| `backend/app/tasks/X.py` | `backend/tests/unit/test_X_tasks.py` |
| `backend/app/models/X.py` | `backend/tests/unit/test_X_model.py` |

If the test file already exists, read it and add only missing test cases.

### 4. Generate Tests

Write tests following these rules:

**Structure:**
- One test class per logical concern (e.g., `TestChunkCreation`, `TestChunkMerging`)
- Use descriptive test names: `test_returns_empty_list_when_no_chunks_found`
- Group related assertions in single tests, but keep tests focused

**Mocking:**
- Mock at the boundary (database, external APIs, file I/O)
- Use `unittest.mock.patch` with the correct import path (patch where used, not where defined)
- Create realistic mock return values that match actual schemas
- Use `conftest.py` fixtures for commonly-needed mocks

**Assertions:**
- Test both happy path AND error paths
- Test edge cases (empty input, None values, large inputs)
- Assert specific values, not just "no exception"
- For functions that return dicts/objects, check key fields

**Imports:**
- Use `pytest` style (not `unittest.TestCase`)
- Import from `app.services.X` not relative imports

### 5. Run and Fix

After writing the test file:

1. Run it: `docker compose exec -T app pytest <test_file> -v --tb=short`
2. If tests fail, read the error, fix the test (not the source unless there's a genuine bug)
3. Re-run until all pass
4. Report: how many tests written, what they cover, any gaps intentionally skipped

### 6. Priority Targets

If no file is specified, suggest these files in priority order (highest coverage gaps):

1. `backend/app/tasks/video_tasks.py` - Critical pipeline, ~11% coverage
2. `backend/app/services/vector_store.py` - Core RAG, ~34% coverage
3. `backend/app/services/enrichment.py` - LLM enrichment, ~21% coverage
4. `backend/app/services/youtube.py` - Download service, minimal tests
5. `backend/app/services/transcription.py` - Whisper integration, minimal tests
