# Test Fix Failures

Diagnose and fix failing tests. The shell script has already run the full test suite and captured failures with detailed tracebacks.

## Your Tasks

### 1. Parse Failures

From the shell script output, identify each failing test:
- Test file path and test function name
- The assertion or exception that caused failure
- The full traceback

### 2. Classify Root Cause

For each failure, read BOTH the test file AND the source file it tests. Classify the root cause as one of:

| Category | Description | Fix Strategy |
|----------|-------------|--------------|
| **Stale mock** | Source function signature changed, mock doesn't match | Update mock to match current signature |
| **Fixture issue** | Test fixture missing, outdated, or wrong scope | Fix/add fixture in conftest.py |
| **Assertion outdated** | Expected value no longer correct due to code changes | Update expected value |
| **Import error** | Module moved, renamed, or dependency missing | Fix import path |
| **Code regression** | Source code has a genuine bug | Fix the source code, not the test |
| **Environment issue** | Test depends on Docker/DB/external service | Add skip decorator or fix setup |

### 3. Fix Each Failure

For each failure:
1. Read the failing test file
2. Read the source file being tested
3. Apply the appropriate fix based on root cause
4. If the fix is in the source code (regression), explain why the code is wrong

### 4. Verify Fixes

After fixing all failures, run the tests again:
```
docker compose exec -T app pytest <specific_test_files> -v --tb=short
```

Only run the previously-failing test files, not the full suite.

### 5. Report

Summarize what was fixed:

```
## Failures Fixed

| Test | Root Cause | Fix Applied |
|------|-----------|-------------|
| test_x::test_func | Stale mock | Updated mock for new `limit` parameter |
| test_y::test_other | Code regression | Fixed off-by-one in source `calculate()` |

## Verification
- X tests now passing
- Y tests still failing (reason: ...)
```

## Guidelines

- Prefer fixing tests over source code, unless the source has a genuine bug
- When updating mocks, check the current source function signature carefully
- When a test depends on infrastructure (DB, Qdrant, Redis), use `@pytest.mark.skipif` with a clear condition rather than removing the test
- Follow existing test patterns in the codebase (class-per-concern, conftest fixtures)
