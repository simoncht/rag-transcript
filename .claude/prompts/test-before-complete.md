# Test Before Complete

Run this skill before considering any feature, bug fix, or refactoring complete.

The shell script (`test-coverage-check.sh`) has already run and provided output about changed files, test results, and basic coverage gaps. Your job is to perform the deeper analysis that requires understanding code semantics.

## Your Tasks

### 1. Evaluate Shell Script Output

Read the output from `test-coverage-check.sh` that was already executed. Note:
- Which tests passed/failed
- Which files have no corresponding test files
- Which new functions were detected

### 2. Run Tests in Parallel

Use the Task tool to launch parallel test runs for faster feedback:

- **Task 1 (Bash agent):** Run unit tests: `docker compose exec -T app pytest tests/unit -v --tb=short`
- **Task 2 (Bash agent):** Run integration tests: `docker compose exec -T app pytest tests/integration -v --tb=short`

Wait for both to complete before proceeding.

### 3. Semantic Gap Analysis

For each changed source file that has a corresponding test file, read BOTH files and evaluate:

- Are the main public functions tested?
- Are error paths covered (exception handling, edge cases)?
- Are the mocks realistic (do they match actual dependencies)?
- Are assertions checking the right things (not just "no exception thrown")?

This is the step where you add the most value - the shell script can only check if a test file exists, not whether the tests are meaningful.

### 4. Generate Report

Format your findings as:

```
## Test Results Summary

### Tests Executed
- Unit tests: X passed, Y failed
- Integration tests: X passed, Y failed

### Test Failures (if any)
[Details with root cause analysis]

### Coverage Gaps
| File | Issue | Priority |
|------|-------|----------|
| path/to/file.py | No test file exists | P0 - critical service |
| path/to/other.py | Missing error path tests | P1 - has happy path only |

### Quality Issues
| Test File | Issue |
|-----------|-------|
| test_x.py | Mocks are outdated (function signature changed) |
| test_y.py | Only tests happy path, no error cases |

### Verdict
- [ ] Ready to commit - all tests pass, no critical gaps
- [ ] Consider adding tests - gaps detected but not blocking
- [ ] Not ready - tests failing or critical coverage missing
```

### 5. Offer to Fix

If gaps are found, offer to write missing tests. Follow existing patterns from files like:
- `backend/tests/unit/test_chunking_service.py` (class-per-concern pattern)
- `backend/tests/unit/test_llm_providers.py` (proper mocking pattern)

### 6. Behavioral Contract Verification

This step ensures behavioral promises are not broken by code changes.

1. **Read contracts:** Read `.claude/references/behavioral-contracts.md` for the full contract list
2. **Map changed files to contracts:** For each changed file, identify which contracts it touches:
   - `conversations.py` → MEM-001, CIT-001, CIT-002, CIT-003, ACC-002
   - `fact_extraction.py` → MEM-001, MEM-004
   - `memory_consolidation.py` → MEM-002, MEM-003
   - `memory_scoring.py` → MEM-002
   - `message.py` → CIT-001
   - `storage_calculator.py` → ACC-001
   - `bm25_search.py` → ACC-003
   - `enrichment.py` → PAR-002
   - `two_level_retriever.py` → RET-001
   - `document_tasks.py` / `video_tasks.py` → PAR-001
3. **Verify each touched contract:** Read the implementing code and check the validation criteria from the contract definition
4. **Report contract status** in the verdict:

```
### Behavioral Contracts
| Contract | Status | Note |
|----------|--------|------|
| MEM-001  | PASS/BROKEN | [brief evidence] |
| CIT-001  | PASS/BROKEN | [brief evidence] |
```

**Contracts must pass for "Ready to commit" verdict.** If a contract is broken, it must be fixed before the change ships — this is the whole point of behavioral enforcement.

If no changed files touch any contracts, note: "No behavioral contracts affected by this change."

## Test File Mapping Rules

| Source Location | Test Location |
|-----------------|---------------|
| `backend/app/services/*.py` | `backend/tests/unit/test_*.py` |
| `backend/app/api/routes/*.py` | `backend/tests/integration/test_*_endpoints.py` |
| `backend/app/models/*.py` | `backend/tests/unit/test_*_model.py` |
| `backend/app/tasks/*.py` | `backend/tests/unit/test_*_tasks.py` |
