# PlaySight_AI — DEPLOY_LOG (append-only)

## 2026-09-04 — Phase 0 gate: STOPPED (operator inputs missing)

- Read `PlaySight_AI.md` autonomous deploy loop prompt. Repo is on `main`, clean and synced with `origin/main` (only untracked docs: `PlaySight_AI.md`, `docs/DEPLOY_LOOP_PROMPT.md`).
- `deploy/.secrets/deploy.env` did **not** exist. Created `deploy/.secrets/` with a blank template and appended `deploy/.secrets/` to `.gitignore` (line 45) so it can never be committed.
- **Missing REQUIRED values:** `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `DOMAIN` (all three empty).
- **Missing optional values:** `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` (loop will fall back to MinIO-on-Railway), `CLOUDFLARE_API_TOKEN` (loop will print manual DNS records).
- Per the prompt, this is the single permitted stop. Phase 0 human checklist printed to the operator verbatim.

BLOCKER: Cannot begin Phase 1–7 — no deployment credentials or domain.
CAUSE: `deploy/.secrets/deploy.env` REQUIRED values (`RAILWAY_TOKEN`, `VERCEL_TOKEN`, `DOMAIN`) are empty; Claude never creates accounts or tokens by policy.
RESOLUTION (minimum human action): Complete the Phase 0 checklist (~10 min): create a Railway token, create a Vercel token, and enter your base domain into `C:\DEVELOP\02_ACTIVE_BUILD\PlaySight_AI\deploy\.secrets\deploy.env`. R2 + Cloudflare values optional.
AFTER RESOLUTION: Re-run the deploy loop prompt; it proceeds automatically through Phase 1 (production hardening) → Phase 7 (ops hardening) without further questions.

## 2026-09-11 — Phase 1: Production hardening (attempt 1) — COMPLETE

Operator inputs now present: `RENDER_API_KEY` + `RENDER_OWNER_ID` validated upstream (workspace `tea-d8bkt4t7vvec73f4q4j0`, zero existing services). Backend platform is **Render** (not Railway). Repo is public on GitHub (`bill143/PlaySight_AI`).

Repo changes (all verified by the local gate below):

1. **CORS from env** — `Settings.cors_origins` added (`src/playsight/config/settings.py`): `list[str]`, accepts a comma-separated `PLAYSIGHT_CORS_ORIGINS` env var (pydantic-settings `NoDecode` + before-validator split) or a YAML list; default `["http://localhost:3000"]`. `create_app()` (`src/playsight/api/main.py`) now reads `get_settings().cors_origins`; the hardcoded constant is removed.
2. **Prod secret fail-fast** — `Settings._finalize` now **raises** `ValueError` at startup when `env == "prod"` and `auth.secret_key` is the dev default (previously only warned). Acceptance criterion 4 hardening.
3. **`docker/Dockerfile.api` CMD** — `sh -c` wrapper binding `0.0.0.0` on `${PORT:-8000}` (Render injects `PORT` for Docker web services).
4. **`docker/Dockerfile.worker`** — installs CPU-only torch first (`pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`), then `pip install ".[cv]"`. ffmpeg kept. Verified `[cv]` extra in `pyproject.toml` lists `ultralytics`, `torch`, `torchvision`, `easyocr`, `supervision` — real engines activate in the worker image.
5. **Storage bucket auto-create** — verified already present: `S3Storage.ensure_bucket()` exists (`src/playsight/storage/s3.py`) and `get_storage()` calls it whenever the s3 backend is constructed (`src/playsight/storage/factory.py`). No change needed; MinIO fallback covered.
6. **Alembic baseline** — `src/playsight/db/alembic/env.py` now also imports Phase 2/3 module models (`import_all_models()`) so autogenerate sees full metadata. Generated ONE initial migration `5830d6e42a5b` (`versions/20260911_1655_5830d6e42a5b_initial_schema_baseline.py`, 40+ tables) against a scratch SQLite URL. Hand-reviewed: generic `sa.*` types only (String/Integer/Boolean/DateTime(timezone=True)/JSON/Float/BigInteger/Date/Text), named constraints via `op.f()`, no dialect-specific constructs, no server defaults — portable to Postgres. Verified `upgrade head` + `downgrade base` round-trip on scratch SQLite.
   **PRODUCTION SCHEMA DECISION:** startup `init_db()`/`create_all` remains the schema creator for this launch; migration `5830d6e42a5b` is the committed baseline for future upgrades. Alembic is NOT wired into the deploy path.
7. **`render.yaml`** authored at repo root (documentation + reproducibility mirror of what Phase 2 provisions via API): web `playsight-api` (docker, dockerContext `.`, dockerfilePath `./docker/Dockerfile.api`, plan starter, healthCheckPath `/api/v1/health/live`), worker `playsight-worker` (docker, `./docker/Dockerfile.worker`, plan standard — 2 GB RAM floor for torch/YOLO), `playsight-kv` Key Value (plan free, `maxmemoryPolicy: noeviction` — Celery broker must not evict), Postgres `playsight-db` (plan basic-256mb). Secrets declared `sync: false` (set via API/dashboard only). MinIO pserv fallback included as a commented block, activated only if R2 creds are absent. Structure validated against the current Render Blueprint spec (render.com/docs/blueprint-spec): Key Value declared under `services` with `type: keyvalue`; `fromDatabase`/`fromService` env references used.
8. **LOCAL GATE — ALL GREEN:**
   - `ruff check src tests` → All checks passed (after auto-fix + black on the generated migration)
   - `black --check src tests` → 174 files unchanged
   - `mypy src` → Success: no issues found in 153 source files
   - `pytest -q -m "not cv"` (PLAYSIGHT_EAGER_JOBS=1) → **140 passed**
   - `dashboard: npm run build` → compiled successfully (5 routes)
9. **Secret scan before push** — `git grep` for the `rnd_` Render key prefix across the staged tree: no hits. `deploy/.secrets/` gitignored (.gitignore line 45, committed in this change).

Committed to `main` and pushed to `origin` (HTTPS, cached credentials). Also committed previously-untracked `docs/DEPLOY_LOOP_PROMPT.md`, `PlaySight_AI.md`, and this log.

Note for Phase 2: Render `connectionString` may use the `postgres://` scheme; SQLAlchemy 2 requires `postgresql://` — normalize when setting `PLAYSIGHT_DATABASE_URL`, or map the scheme in the env var value set via API.
