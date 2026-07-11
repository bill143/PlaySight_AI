# Contributing to PlaySight AI

Thanks for contributing to PlaySight AI. This document covers the day-to-day workflow for backend, dashboard, data, and infrastructure changes.

## Development setup

1. Copy the local environment template:
   ```bash
   cp .env.example .env
   ```
2. Start the full stack for local development:
   ```bash
   make dev
   ```
3. For local Python development outside Docker, create a virtual environment and install dependencies:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   make backend-install
   ```
4. Install dashboard dependencies when working on the frontend:
   ```bash
   make dashboard-install
   ```
5. Run migrations before testing API changes:
   ```bash
   make migrate
   ```

Common commands:

- `make dev` — start the local stack with Docker Compose
- `make test` — run the Python test suite
- `make lint` — run backend Ruff checks and dashboard linting
- `make format` — apply backend formatting fixes
- `make down` — stop local services

## Branch naming

Use short, descriptive branch names with a category prefix:

- `feat/video-ingest-endpoint`
- `fix/auth-refresh-token`
- `chore/ci-cleanup`
- `docs/api-reference`

## Commit message conventions

Prefer Conventional Commit style so history stays easy to scan:

- `feat: add match ingest endpoint`
- `fix: handle missing youtube credentials`
- `docs: expand api overview`
- `chore: update compose healthchecks`

Keep commits focused. If a change spans backend and dashboard, mention both scopes clearly in the body.

## Pull request process

1. Rebase or merge from the latest default branch before opening a PR.
2. Run the relevant quality checks locally:
   ```bash
   make lint
   make test
   ```
3. Open a PR with:
   - a concise summary of the problem being solved,
   - implementation notes,
   - screenshots or recordings for dashboard changes,
   - API examples for new endpoints,
   - migration notes if schema changes are included.
4. Link related issues, roadmap items, or follow-up work.
5. Wait for CI and at least one review before merging.

## Code style

### Python backend

- Use `black` for formatting.
- Use `ruff` for linting and import hygiene.
- Add or update Pydantic schemas, models, and tests together when behavior changes.
- Keep business logic out of route handlers where possible; prefer service-layer functions.

### TypeScript / Next.js dashboard

- Use the repository ESLint configuration.
- Format with Prettier-compatible style.
- Keep shared API clients and request helpers in `dashboard/src/lib`.
- Keep reusable UI in `dashboard/src/components` and route-specific logic in `dashboard/src/app`.

## Adding a new API endpoint

1. Add or update request/response schemas in `backend/schemas/`.
2. Implement the route in the relevant API module under `backend/`.
3. Wire the route into the API router under the `/api/v1` namespace.
4. Add validation, authorization, and service-layer logic as needed.
5. Add tests covering success, validation failure, and authorization failure paths.
6. Document the endpoint in `docs/api.md` and update `README.md` if it changes developer workflows.

## Adding a new migration

1. Update the SQLAlchemy models.
2. Generate or author the Alembic revision:
   ```bash
   alembic -c backend/alembic.ini revision --autogenerate -m "describe change"
   ```
3. Review the generated migration carefully, especially defaults, indexes, and destructive operations.
4. Apply it locally:
   ```bash
   make migrate
   ```
5. Include migration impact notes in your PR description.

## Testing expectations

- Add regression tests for bugs.
- Add integration coverage for new API workflows when practical.
- Keep fixtures deterministic and avoid coupling tests to external services unless explicitly mocked.

We value small, well-documented pull requests that move the platform forward safely.
