# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI app, Celery workers, and domain services (`app/api`, `app/services`, `app/models`, `app/schemas`).
- `frontend/`: Next.js 14 App Router UI (`src/app`, `src/components`).
- `backend/tests/`: Pytest suites (unit/integration).
- `backend/alembic/`: DB migrations (`versions/` filenames are ordered).
- `storage/` and `hf_cache/`: local runtime assets and model caches.

## Build, Test, and Development Commands
- `docker compose up -d`: start postgres, redis, qdrant, backend, worker, beat, and frontend.
- `docker compose exec app alembic upgrade head`: apply migrations.
- `docker compose exec app pytest`: run backend tests in Docker.
- `docker compose exec app black . && ruff .`: format and lint backend.
- `cd frontend && npm run dev`: run the Next.js dev server.
- `cd frontend && npm run build`: production build check.
- `cd frontend && npm run lint` / `npm run type-check`: frontend linting and TS checks.

## Coding Style & Naming Conventions
- Python: 4-space indent, type hints preferred, `snake_case` for functions/vars, `PascalCase` for classes. Format with `black` and lint with `ruff`.
- Frontend: follow existing App Router patterns and Shadcn component usage. Use `camelCase` for TS/JS identifiers.

## Testing Guidelines
- Backend tests use `pytest` (`backend/tests/unit`, `backend/tests/integration`).
- Run focused tests with: `PYTHONPATH=backend pytest backend/tests/unit/test_chunking.py -v`.
- Frontend does not appear to have automated tests; rely on `npm run lint` and `npm run type-check`.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commit prefixes (`feat:`, `fix:`, `wip:`).
- PRs should include: clear summary, test results (commands + outcome), and UI screenshots for frontend changes.
- Link relevant issues or notes when applicable.

## Security & Configuration Tips
- Store secrets in `backend/.env` (see `backend/.env.example`); never commit keys.
- Default LLM is Ollama; if using OpenAI/Anthropic, set `LLM_PROVIDER` and API keys in `backend/.env`.
