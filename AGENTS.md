# Repository Guidelines

## Project Structure & Module Organization
- `backend/app/main.py` is the FastAPI entrypoint; `app/api/routes` holds HTTP routes and should stay thin, delegating to services.
- Domain logic lives in `app/services/*.py` (chunking, enrichment, embeddings, storage, LLM, vector store); share helpers there rather than re-implementing in routes.
- Persistence is split between `app/models` (SQLAlchemy) and `app/schemas` (Pydantic). Add migrations in `backend/alembic/versions` and keep filenames ordered (e.g., `003_describe_change.py`).
- Celery tasks belong in `app/tasks` and should call the same service functions the API uses.
- Local artifacts (audio/transcripts) default to `storage/` (mounted into containers). `frontend/src` now contains the Next.js App Router UI, including Shadcn-based pages for videos, collections, and conversations.

## Build, Test, and Development Commands
- Install deps: `python -m venv venv && venv\Scripts\activate && pip install -r backend/requirements.txt`.
- Run API locally: `cd backend && uvicorn app.main:app --reload` (requires Postgres/Redis/Qdrant—start with `docker-compose up -d` from repo root).
- Celery workers: `celery -A app.core.celery_app worker --loglevel=info` and `celery -A app.core.celery_app beat --loglevel=info`.
- DB migrations: `alembic upgrade head`; create new ones with `alembic revision -m "describe change" --autogenerate`.
- Tests: `pytest` for full suite, or `pytest backend/tests/unit` for targeted runs; add `--cov=app` when checking coverage.

## Coding Style & Naming Conventions
- Python 3.11, 4-space indentation. Run `black .` and `ruff .` before sending changes; prefer adding type hints and keep `mypy`-clean where practical.
- Use snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE_CASE for settings. Name new modules `lower_snake.py` and tests `test_<module>.py`.
- Keep API responses typed via Pydantic schemas; avoid leaking ORM objects directly.
- Prefer service-level functions for shared logic; keep route handlers and tasks declarative.

## Testing Guidelines
- Framework: pytest + pytest-asyncio. Put small unit tests in `backend/tests/unit`, integration/HTTP or task flows in `backend/tests/integration`.
- Name tests descriptively (`test_ingest_rejects_invalid_url`) and cover failure paths (invalid YouTube URLs, storage errors, model fallbacks) alongside happy paths.
- When introducing migrations or new Celery tasks, include a regression test that exercises the affected path (e.g., job status transitions, chunk counts).

## Commit & Pull Request Guidelines
- Use concise, imperative commit messages (e.g., `Add job status polling API`); Conventional Commit prefixes (`feat`, `fix`, `chore`, `test`, `docs`) are encouraged for clarity.
- PRs should include: summary of intent, key testing notes/commands run, and any config/env changes (`backend/.env` keys, ports). Attach screenshots or example API responses when behavior changes.
- Keep changes scoped; update docs (`README.md`, `SETUP.md`, `TEST_GUIDE.md`) when altering workflows or external dependencies.

## Security & Configuration Tips
- Never commit secrets; copy `backend/.env.example` to `backend/.env` and document new variables there.
- Default local storage writes to `storage/`; ensure this path exists or update `LOCAL_STORAGE_PATH` accordingly.
- When touching schema or storage behavior, run `docker-compose up -d` and `alembic upgrade head` to validate against live services before merging.

## Frontend / Shadcn Notes
- The frontend is a Next.js App Router app under `frontend/src/app` with Shadcn UI integrated via `frontend/components.json`, `frontend/tailwind.config.ts`, and `frontend/src/app/globals.css`.
- Core layout and theming live in `frontend/src/app/layout.tsx`, `frontend/src/app/providers.tsx`, and `frontend/src/components/layout/MainLayout.tsx` (with dark/light mode powered by `next-themes`).
- Key Shadcn-migrated pages:
  - `frontend/src/app/videos/page.tsx` – videos dashboard.
  - `frontend/src/app/collections/page.tsx` – collections management.
  - `frontend/src/app/conversations/page.tsx` – unified conversations list + creation form.
  - `frontend/src/app/conversations/[id]/page.tsx` – single-card chat UI with sources panel.
- When adding new UI, prefer existing Shadcn primitives (`Card`, `Button`, `Badge`, `Input`, `Table`, etc.) and the shared layout, and keep API contracts unchanged.
