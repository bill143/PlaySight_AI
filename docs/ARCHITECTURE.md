# PlaySight_AI — Architecture

This document describes how the platform is put together. The binding
interface spec is [CONTRACTS.md](CONTRACTS.md); this document explains the
shape and the reasoning.

## 1. Module map

Everything ships in one installable Python package, `src/playsight/`
(`pip install -e .`), plus a Next.js dashboard.

| Module | Responsibility |
|---|---|
| `playsight.config` | `Settings` (pydantic-settings + YAML layer), feature flags (`flags.is_enabled` / `require_feature`) |
| `playsight.core` | structlog logging + correlation IDs, error hierarchy, `new_id()` (uuid4-hex PKs), shared pipeline dataclasses (`FrameDetection`, `TrackedBox`, `IdentityResult`, `EventSpan`, `EventType`) |
| `playsight.db` | SQLAlchemy 2.0 engine/session/`Base`, all Phase 1 models, Alembic scaffold (`db/alembic/env.py` wired to `Base.metadata`; no committed migrations yet) |
| `playsight.auth` | bcrypt password hashing, JWT HS256 access/refresh tokens, `Role` enum + `require_roles` RBAC dependency factory |
| `playsight.storage` | `ObjectStorage` protocol with `local` (filesystem) and `s3` (boto3, MinIO-compatible) backends; `get_storage(settings)` factory |
| `playsight.jobs` | Celery app (`jobs.celery_app`), task definitions with in-body retry, `dispatch.dispatch_job()` — the single dispatch entry point (eager or Celery) |
| `playsight.ingestion` | video probing (`probe_video`), frame iteration (stride/max_frames), `ingest_video` → `video_assets` row + storage copy |
| `playsight.detection` | `PersonDetector` interface; YOLO (`ultralytics`, lazy import) or deterministic `StubDetector`; `create_detector(settings)` |
| `playsight.tracking` | `Tracker` interface; ByteTrack via `supervision` (lazy import) or IOU-based `SimpleTracker`; `create_tracker(settings)` |
| `playsight.identification` | jersey OCR (EasyOCR, lazy import, stub fallback) + HSV color-histogram Re-ID; `identify_tracks()`; **no face recognition** |
| `playsight.analytics` | rule-based event segmentation (`compute_events`) and per-player stats (`compute_player_stats`) |
| `playsight.reporting` | `match_summary.json`, player reports (JSON + fpdf2 PDF), stats/identities CSVs |
| `playsight.highlights` | per-player highlight reels (ffmpeg clip extraction + concat) |
| `playsight.export` | annotated video MP4 (boxes + track ids), audio summary MP3 (gTTS → pyttsx3 → tone+transcript fallback) |
| `playsight.integrations.youtube` | OAuth2 installed-app flow, resumable uploads with tenacity backoff, structured error logs |
| `playsight.integrations.notifications` | `Notifier` protocol, `LogNotifier` (MVP), `EmailNotifier`/`PushNotifier` stubs (`TODO(phase2)`) |
| `playsight.pipeline` | `run_match_pipeline()` orchestrator + artifact registration helpers |
| `playsight.api` | FastAPI app factory, correlation middleware, deps (`get_current_user`, `get_tenant`), routers, pydantic v2 schemas |
| `playsight.evaluation` | detection/tracking/identification quality metrics |
| `playsight.cli` | Typer CLI (`playsight` entry point), demo data generator |
| `playsight.modules.*` | Phase 2/3 feature-flagged scaffolds: `competition`, `merchandise`, `playbook`, `training`, `nutrition`, `registration`, `payments`, `commerce`. Each has `models.py`/`schemas.py`/`service.py`/`router.py`/`README.md`; simple CRUD works, advanced flows answer 501 or raise `NotImplementedError` with `TODO(phase2/3)` markers |
| `dashboard/` | Next.js 14 App Router + TypeScript + Tailwind; talks to the API at `NEXT_PUBLIC_API_URL` |

`playsight.modules.import_all_models()` / `iter_routers()` discover the
scaffold submodules dynamically, so partial checkouts keep working and each
module router carries its own `require_feature` guard.

## 2. Data flow

```
video file
   │  ingestion.ingest_video (probe: duration/fps/size → video_assets row,
   │                          copy to storage matches/<match_id>/source/<filename>)
   ▼
frame loop (frame_stride, optional max_frames)
   │  detection.PersonDetector.detect(frame) → list[FrameDetection]
   │  tracking.Tracker.update(detections, frame) → list[TrackedBox]
   ▼
tracks dataframe  ──▶ outputs/<match_id>/player_tracks.parquet
   │  columns: frame_index:int64, t_s:float64, track_id:int64,
   │           x1,y1,x2,y2:float64, confidence:float64
   ▼
identification.identify_tracks(video, tracks_df, settings)
   │  jersey OCR (EasyOCR|stub) + appearance Re-ID → IdentityResult per track,
   │  mapped to rostered players by jersey number → player_identities rows + CSV
   ▼
analytics.compute_events(tracks_df, video_info, settings)
   │  heuristic EventSpans (touch/pass/tackle/shot_attempt/turnover/
   │  scoring_event), each with confidence + [t_start_s, t_end_s]
   │  → match_events rows
   ▼
analytics.compute_player_stats(...)
   │  minutes_tracked, distance proxy, event counts, 12x8 heatmap grid
   │  → player_match_stats rows + player_stats.csv
   ▼
reporting: match_summary.json, player_report_<ref>.json/.pdf
   ▼
artifact registration: every file → outputs/<match_id>/ AND object storage
   (matches/<match_id>/<filename>) AND an `artifacts` row
   ▼
matches.status: processing → processed (or failed; error re-raised to the job)
```

On-demand jobs reuse the persisted parquet/artifacts instead of re-running
detection: `highlights` (event windows for one identity/track → ffmpeg reel),
`annotate` (draw boxes/ids over the source video), `export_audio` (narrated
summary), `publish` (YouTube upload; writes `upload_status.json` at terminal
state).

### Engine selection & stub fallbacks

Heavy CV dependencies are optional (`[cv]` extra) and imported lazily inside
functions. Factories choose the best available engine:

| Stage | Real engine | Fallback | Summary marker |
|---|---|---|---|
| detection | YOLO (`ultralytics`) | deterministic `StubDetector` | `engine.detector: "yolo"\|"stub"` |
| tracking | ByteTrack (`supervision`) | IOU `SimpleTracker` | `engine.tracker: "bytetrack"\|"simple"` |
| jersey OCR | EasyOCR | deterministic `StubOcr` | `engine.ocr: "easyocr"\|"stub"` |
| TTS | gTTS | pyttsx3, else tone + `.txt` transcript | artifact metadata |

Stub output is honest: `match_summary.json` records the engines used, and
stub-generated data is deterministic so tests are reproducible.

## 3. Job lifecycle

`processing_jobs` rows are the source of truth for background work. Kinds:
`analyze`, `highlights`, `annotate`, `export_audio`, `publish` (and `report`
reserved). API/CLI create a row and call `playsight.jobs.dispatch.dispatch_job(db, job)`
— the only dispatch entry point.

```
                       dispatch_job(db, job)
                              │
              eager mode? ────┴──── otherwise
   (PLAYSIGHT_EAGER_JOBS=1,            │
    env == "test", or                  │ task.delay(job_id)
    empty redis_url)                   │ celery_task_id stored on row
              │                        ▼
   task.run(job_id) in-process    Celery worker picks it up
              │                        │
              └──────────┬─────────────┘
                         ▼
                ┌──────────────────┐
   queued ────▶ │     running      │  started_at set, correlation_id bound
                └──────┬───────────┘  progress: 0.0 → 1.0 (throttled commits)
                       │
        ┌──────────────┼─────────────────────┐
        ▼              ▼                     ▼
   ┌───────────┐  ┌─────────┐          ┌────────────┐
   │ succeeded │  │ failed  │          │ cancelled  │ (reserved status)
   │ result_json│ │ error + │          └────────────┘
   │ + artifacts│ │ retries │
   └───────────┘  └─────────┘
```

Retry policy: transient failures (`ExternalServiceError`, `ConnectionError`,
`TimeoutError`) retry inside the task body with exponential backoff (2s, 4s,
8s; max 3 retries) so behavior is identical in eager mode and under a worker.
Domain errors fail immediately. All exceptions are captured into `job.error`
— the job row is always the source of truth. The Celery app (`playsight`)
uses `task_acks_late=True` and JSON serializers.

## 4. Tenancy & RBAC

- **Tenant = club.** Every core entity carries `club_id` (FK `clubs.id`,
  indexed); most also carry a nullable `team_id`.
- `api.deps.get_current_user` validates the bearer access token (JWT HS256;
  claims `sub`, `club_id`, `roles`, `type`, `jti`, `exp`, `iat`) and loads an
  active user. `get_tenant` builds a `TenantContext(club_id, team_ids, user,
  roles)` and stores it on `request.state.tenant` (feature-flag checks read
  the club id from there).
- **Every core router filters queries by `tenant.club_id`. Cross-club access
  answers 404 — never 403 — so resource existence is not leaked.**
- Roles (`playsight.auth.rbac.Role`): `admin`, `coach`, `analyst`, `player`,
  `guardian`, `registrar`, `finance_admin`, `shop_manager`. Roles live in
  `user_roles` rows, optionally scoped to a team. `require_roles(*roles)`
  is a FastAPI dependency factory; **`admin` always passes**.
- Refresh tokens rotate: each refresh's `jti` is persisted in
  `refresh_tokens`; `POST /auth/refresh` revokes the presented token and
  issues a fresh pair. Passwords are bcrypt-hashed.
- Bootstrap: `POST /auth/register-club` creates the club + first admin, open
  only while no club exists or `env == "dev"` (403 otherwise).
- Feature flags: global `settings.features` overridden per club via
  `club_modules`. `require_feature(key)` raises `FeatureDisabledError`
  (HTTP 403, code `feature_disabled`) when off.
- Sensitive mutations (club registration, match create/delete, publish
  requests, ...) write `audit_logs` rows with before/after JSON.

## 5. Storage layout

`playsight.storage.ObjectStorage` protocol (`put_file`, `put_bytes`,
`open_stream`, `download_to`, `exists`, `url_for`, `delete`), with two
backends selected by `settings.storage.backend`:

- **local** — files under `storage.local_root` (default `./outputs/storage`).
- **s3** — boto3 against S3 or MinIO (`s3_endpoint`, bucket `playsight` by
  default). The compose stack provisions the bucket automatically.

Keys are POSIX-style relative paths and never contain PII:

```
matches/<match_id>/<filename>            # generated artifacts (CONTRACTS §9 names)
matches/<match_id>/source/<filename>     # ingested source videos
```

Generated files are additionally written locally to `outputs/<match_id>/`
(gitignored) for direct inspection, and every artifact is registered in the
`artifacts` table (id, kind, storage_key, filename, content_type, size_bytes,
meta) — the API's `GET /artifacts/{id}/download` streams from storage with
the stored content type and filename.

## 6. Errors, logging, correlation IDs

**Errors** (`playsight.core.errors`): all application errors derive from
`PlaySightError(message, code)`; each class carries a canonical HTTP status.

| Exception | code | HTTP |
|---|---|---|
| `NotFoundError` | `not_found` | 404 |
| `AuthError` | `auth_error` | 401 |
| `PermissionDeniedError` | `permission_denied` | 403 |
| `ValidationFailed` | `validation_failed` | 422 |
| `ExternalServiceError` | `external_service_error` | 502 |
| `FeatureDisabledError` | `feature_disabled` | 403 |

The API exception handler renders every `PlaySightError` (and a generic 500
for anything unhandled, leaking no internals) as:

```json
{"error": {"code": "not_found", "message": "...", "correlation_id": "..."}}
```

**Logging**: structlog JSON everywhere. `playsight.core.logging.configure_logging()`
sets up the pipeline; `get_logger(name)` returns a bound logger. **No
`print()` in library code** — only the CLI uses `rich` output.

**Correlation IDs**: `CorrelationIdMiddleware` reads the incoming
`X-Correlation-ID` header (or generates a uuid4 hex), binds it into the
structlog contextvars for the request, stores it on
`request.state.correlation_id`, echoes it on the response header, and emits
`request_started`/`request_finished` access logs with duration. Jobs persist
the creating request's correlation id on the `processing_jobs` row and re-bind
it when the task runs — one id traces an operation across API, queue, and
worker. Error bodies include it so users can quote it in reports.

## 7. Configuration

Load order (highest precedence first): constructor kwargs (tests) →
environment variables (`PLAYSIGHT_` prefix, `__` nested delimiter) → `.env` →
YAML file (`PLAYSIGHT_CONFIG`, default `configs/default.yaml`) → field
defaults. `get_settings()` is a process-wide cached singleton
(`get_settings.cache_clear()` in tests). Using the dev JWT secret with
`env=prod` logs an `insecure_auth_secret_key` warning.

## 8. Testing & CI shape

Unit tests cover config, auth, storage, stub engines (determinism), event
heuristics, reporting, ffmpeg command building (mocked subprocess), the
YouTube client (mocked googleapiclient), and idempotency. Integration tests
drive the FastAPI TestClient end-to-end on SQLite + eager jobs + local
storage — including the tenancy 404 guarantee. Tests never require network,
GPU, Docker, or the `[cv]` extra; CV-dependent tests are marked
`@pytest.mark.cv` and skipped in CI (`pytest -m "not cv"`). CI runs
lint (ruff+black), mypy, pytest on Python 3.11/3.12, and the dashboard
lint+build.
