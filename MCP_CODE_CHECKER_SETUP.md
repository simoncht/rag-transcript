# MCP Code Checker Setup Guide

## Overview

**MCP Code Checker** is a Model Context Protocol server that integrates code quality tools (pylint, pytest, mypy) with Claude Code, enabling intelligent code analysis and test failure diagnosis.

**Project Repository:** [MarcusJellinghaus/mcp-code-checker](https://github.com/MarcusJellinghaus/mcp-code-checker)

---

## Why MCP Code Checker for This Project?

Our RAG Transcript project has:
- ✅ Complex async services (FastAPI, Celery, embeddings)
- ✅ Multiple test suites (unit, integration)
- ✅ Type annotations (mypy compatible)
- ✅ Code quality requirements (ruff, black in requirements.txt)

MCP Code Checker provides **real-time feedback** from three integrated tools:
1. **Pytest** - Detects failing tests with detailed error messages
2. **Pylint** - Identifies code quality and style issues
3. **Mypy** - Catches type checking errors

---

## Installation Steps

### Step 1: Install mcp-code-checker

```bash
# From your project root directory
pip install git+https://github.com/MarcusJellinghaus/mcp-code-checker.git
```

Or use the alternative Python server:
```bash
pip install git+https://github.com/mcpflow/mcp_server_code_checker_python.git
```

### Step 2: Verify Installation

```bash
# Test that the command is available
mcp-code-checker --help
```

---

## Configuration for Claude Code

### Option A: Manual Configuration (Recommended for Development)

Create or update your Claude Code configuration file:

**File location:** `~/.claude/mcp-config.json` (or in Claude Code settings)

```json
{
  "mcpServers": {
    "code_checker": {
      "command": "mcp-code-checker",
      "args": ["--project-dir", "/path/to/rag-transcript"]
    }
  }
}
```

**For this project specifically:**
```json
{
  "mcpServers": {
    "code_checker": {
      "command": "mcp-code-checker",
      "args": ["--project-dir", "C:\\Users\\PW278WC\\ai\\rag-transcript"]
    }
  }
}
```

### Option B: Using mcp-config Tool (Automatic Setup)

```bash
# Install the config management tool
pip install mcp-config

# Set up mcp-code-checker for your project
mcp-config setup mcp-code-checker "RAG Transcript" --project-dir C:\\Users\\PW278WC\\ai\\rag-transcript
```

---

## Configuration Files Already Created

We've set up pytest configuration to work seamlessly with mcp-code-checker:

### `backend/pytest.ini`
- Configures test discovery (testpaths = tests)
- Enables coverage reporting (--cov)
- Defines test markers for organization
- Sets up asyncio mode for async tests

### `backend/tests/conftest.py`
- Provides shared fixtures for tests:
  - `sample_embedding` - Random embedding vector
  - `sample_video_id` - Sample YouTube video ID
  - `sample_query` - Sample search query
  - `sample_chunk_text` - Sample transcript chunk
  - `sample_chunks` - Multiple sample chunks

---

## How It Works

### Running Code Checks

In Claude Code, you can ask:

```
Check the code quality of the backend using mcp-code-checker
```

This will:
1. Run `pylint` on `backend/app` to identify code issues
2. Run `pytest` in `backend/tests` to execute all tests
3. Run `mypy` for type checking
4. Provide LLM-friendly output with suggestions

### Using Test Results in Claude Code

Example workflow:
```
claude> Check tests and suggest fixes for any failures
```

MCP Code Checker will:
1. Execute all tests in `backend/tests`
2. Capture failures and error messages
3. Present them to Claude for analysis
4. Claude suggests fixes based on the actual errors

---

## Tools Integrated

| Tool   | Purpose | Configuration |
|--------|---------|---------------|
| **Pytest** | Test execution | `backend/pytest.ini` |
| **Pylint** | Code quality analysis | Uses default pylint rules |
| **Mypy** | Type checking | Uses project's type annotations |

---

## Testing Your Setup

Once installed, verify the setup works:

### Quick Test

```bash
# From backend directory
cd backend
pytest tests/ -v
```

### With MCP Code Checker

Ask Claude Code:
```
Run code quality checks with mcp-code-checker on the backend
```

You should see:
- ✅ Test results from pytest
- ✅ Code quality issues from pylint
- ✅ Type checking results from mypy

---

## Troubleshooting

### Issue: "mcp-code-checker: command not found"
**Solution:** Ensure it's installed in the same Python environment as Claude Code
```bash
pip install git+https://github.com/MarcusJellinghaus/mcp-code-checker.git
```

### Issue: Tests not found
**Solution:** Verify pytest.ini points to correct testpaths:
```bash
pytest tests/ --collect-only  # Should list all tests
```

### Issue: Configuration not recognized
**Solution:** Check configuration file location and format:
- Claude Desktop: `~/.config/Claude/claude_desktop_config.json`
- Claude Code: Check `/help` for current config location

---

## Next Steps

1. **Install mcp-code-checker** using the installation steps above
2. **Configure Claude Code** with your project path
3. **Run initial check:** `mcp-code-checker --project-dir /path/to/rag-transcript`
4. **Start using it:** Ask Claude Code to "check code quality" or "run tests"

---

## References

- [MCP Code Checker GitHub Repository](https://github.com/MarcusJellinghaus/mcp-code-checker)
- [Alternative Python Implementation](https://github.com/mcpflow/mcp_server_code_checker_python)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io)
- [Pytest Documentation](https://docs.pytest.org)
