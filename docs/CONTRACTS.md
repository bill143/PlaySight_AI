# PlaySight_AI — Engineering Contracts (Master Spec)

> **This document is the single source of truth for module boundaries, naming, schemas,
> and interfaces.** All contributors (human or agent) MUST implement against it exactly.
> If a contract must change, change it here first, then in code.

Platform: multi-sport video analytics, club operations, and athlete development.
Delivery: Phase 1 fully implemented; Phase 2/3 scaffolded behind feature flags.

---

## 1. Repository layout

```
PlaySight_AI/
├── src/playsight/                  # Python package (installed via `pip install -e .`)
│   ├── __init__.py                 # __version__ = "0.1.0"
│   ├── config/                     # settings (pydantic-settings + YAML), feature flags
│   ├── core/                       # logging, errors, correlation IDs, shared types/utils
│   ├── db/                         # SQLAlchemy engine/session/models, alembic scaffold
│   ├── auth/                       # JWT (access+refresh), password hashing, RBAC
│   ├── storage/                    # object storage abstraction (local / MinIO / S3)
│   ├── jobs/                       # Celery app, task definitions, retry policies
│   ├── ingestion/                  # video file ingest, probing, metadata
│   ├── detection/                  # YOLO-based person detection (lazy import, stub fallback)
│   ├── tracking/                   # ByteTrack via `supervision` (IOU fallback)
│   ├── identification/             # jersey OCR (EasyOCR opt.) + embedding Re-ID fallback
│   ├── analytics/                  # per-player stats, event segmentation heuristics
│   ├── reporting/                  # match summary JSON, player reports JSON/PDF, CSV
│   ├── highlights/                 # per-player highlight reel building (ffmpeg)
│   ├── export/                     # annotated video MP4, audio summary MP3
│   ├── integrations/               # youtube/ (OAuth2 upload), notifications/
│   ├── pipeline/                   # orchestrator: run_match_pipeline()
│   ├── api/                        # FastAPI app: main.py, deps.py, routers/, schemas/
│   ├── evaluation/                 # metrics for detection/tracking/id quality
│   ├── cli/                        # Typer CLI (`playsight` entry point)
│   └── modules/                    # Phase 2/3 scaffolds (feature-flagged)
│       ├── competition/            # fixtures/standings sync adapters
│       ├── merchandise/            # catalog abstraction + Shopify/Woo adapter stubs
│       ├── playbook/               # plays, diagrams, clip links
│       ├── training/               # templates, periodization, attendance
│       ├── nutrition/              # profiles, meal templates, macro targets
│       ├── registration/           # registrations, documents, approval workflow
│       ├── payments/               # Stripe abstraction, fee rules, webhooks
│       └── commerce/               # cart/checkout/orders
├── dashboard/                      # Next.js 14 (App Router) + TypeScript + Tailwind
├── tests/                          # pytest (unit/ + integration/)
├── docs/                           # ARCHITECTURE.md, API.md, ROADMAP.md, CONTRACTS.md
├── configs/default.yaml            # base config (overridable by env)
├── scripts/                        # run scripts (process_video.ps1/.sh, seed_demo.py, …)
├── data/                           # input videos & intermediates (gitignored)
├── outputs/                        # generated artifacts (gitignored)
├── docker/                         # Dockerfile.api, Dockerfile.worker, Dockerfile.dashboard
├── docker-compose.yml              # api, worker, dashboard, postgres, redis, minio
├── Makefile                        # dev tasks (also works via `make` on Windows w/ gnu make; scripts mirror it)
├── pyproject.toml                  # deps + ruff/black/mypy/pytest config
├── .env.example
└── .github/workflows/ci.yml       # lint + type + tests (core deps only)
```

## 2. Python dependencies (pyproject)

Python `>=3.11`. Core (always installed):

- fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, PyYAML
- sqlalchemy>=2.0, alembic, psycopg2-binary
- celery[redis], redis
- boto3 (S3/MinIO), python-multipart
- PyJWT, bcrypt (direct use, no passlib)
- typer, rich, httpx, tenacity, structlog
- pandas, pyarrow, numpy
- opencv-python-headless, pillow
- fpdf2 (PDF reports), imageio-ffmpeg (ffmpeg binary resolution; prefer system ffmpeg)
- google-api-python-client, google-auth, google-auth-oauthlib (YouTube)
- gtts (optional at runtime — MP3 TTS; fallback to pyttsx3 if installed, else tone+transcript)

Optional extra `[cv]` (heavy — NOT installed in CI):
- ultralytics, torch, torchvision, easyocr, supervision

**Rule: every heavy CV import is lazy (inside functions) and wrapped so the platform
degrades to deterministic stub implementations when `[cv]` isn't installed.** Stub
implementations must be honest: mark their output `"engine": "stub"` in metadata.

Dev extra `[dev]`: pytest, pytest-asyncio, pytest-cov, ruff, black, mypy, types-PyYAML,
httpx, faker.

Tooling config: black line-length 100; ruff (E,F,I,UP,B,SIM — line-length 100);
mypy non-strict (`ignore_missing_imports = true`, `check_untyped_defs = true`).

## 3. Configuration

`playsight.config.settings.Settings` (pydantic-settings). Load order: defaults →
`configs/default.yaml` (path via `PLAYSIGHT_CONFIG`, default `configs/default.yaml`) →
environment variables (prefix `PLAYSIGHT_`, nested delimiter `__`) → `.env`.

Key settings (env var in parens):

| Setting | Default | Notes |
|---|---|---|
| `env` | `dev` | dev/test/prod |
| `database_url` (`PLAYSIGHT_DATABASE_URL`) | `sqlite:///./playsight.db` | Postgres in docker |
| `redis_url` | `redis://localhost:6379/0` | |
| `storage.backend` | `local` | `local` \| `s3` (MinIO is `s3` w/ endpoint) |
| `storage.local_root` | `./outputs/storage` | |
| `storage.s3_endpoint / bucket / access_key / secret_key` | MinIO defaults | bucket `playsight` |
| `auth.secret_key` (`PLAYSIGHT_AUTH__SECRET_KEY`) | dev-only default, warn in prod | |
| `auth.access_ttl_minutes` / `auth.refresh_ttl_days` | 30 / 14 | |
| `pipeline.detection_conf` | 0.35 | |
| `pipeline.frame_stride` | 2 | process every Nth frame |
| `pipeline.max_frames` | null | cap for smoke runs |
| `youtube.client_secrets_file` / `youtube.token_file` | `configs/google_client_secret.json` / `configs/youtube_token.json` | |
| `features.*` | see §10 | feature flags |

## 4. Core conventions

- **Logging**: `structlog` JSON logs. `playsight.core.logging.configure_logging()` +
  `get_logger(name)`. Every API request and job binds `correlation_id` (uuid4 hex).
  API middleware reads/sets `X-Correlation-ID`.
- **Errors**: `playsight.core.errors` defines `PlaySightError(message, code)` and
  subclasses: `NotFoundError`, `AuthError`, `PermissionDeniedError`, `ValidationFailed`,
  `ExternalServiceError`, `FeatureDisabledError`. API handler maps them to
  404/401/403/422/502/403 with body `{"error": {"code", "message", "correlation_id"}}`.
- **IDs**: DB primary keys are `String(32)` uuid4 hex, generated via
  `playsight.core.ids.new_id()`.
- **Time**: UTC everywhere, `datetime.now(timezone.utc)`.

## 5. Database models (`playsight.db.models`)

SQLAlchemy 2.0 declarative, `Base` in `playsight.db.base`. All Phase-1 core entities
carry tenancy columns `club_id` (required, FK clubs.id, indexed) and `team_id`
(nullable where noted). `init_db()` = `Base.metadata.create_all`. Alembic scaffolded
(env.py wired to `Base.metadata`), no committed migrations yet (documented).

Phase 1 tables:

- `clubs`: id, name, slug (unique), settings_json (JSON, default {}), created_at
- `teams`: id, club_id, name, sport (str), age_group (nullable)
- `users`: id, club_id, email (unique), hashed_password, full_name, is_active (bool), created_at
- `user_roles`: id, user_id FK, role (str enum, see §6), club_id, team_id (nullable)
- `refresh_tokens`: id, user_id, jti (unique), expires_at, revoked (bool)
- `players`: id, club_id, team_id, full_name, jersey_number (int, nullable), position (nullable), external_ref (nullable)
- `matches`: id, club_id, team_id, opponent, sport, kickoff_at (nullable), venue (nullable), period_config_json (JSON: `{"periods": 2, "period_minutes": 45}`), status (`created|processing|processed|failed`), created_at
- `video_assets`: id, club_id, match_id, storage_key, filename, duration_s (float), fps (float), width, height, status (`registered|ready|failed`), meta_json
- `processing_jobs`: id, club_id, match_id (nullable), kind (`analyze|highlights|export_audio|annotate|publish|report`), status (`queued|running|succeeded|failed|cancelled`), progress (float 0-1), celery_task_id (nullable), params_json, result_json (nullable), error (nullable text), correlation_id, retries (int, default 0), created_at, started_at, finished_at
- `player_identities`: id, club_id, match_id, track_id (int), player_id (nullable FK players), jersey_number (nullable int), confidence (float), method (`ocr|reid|manual|unresolved`)
- `match_events`: id, club_id, match_id, event_type (see §8), t_start_s (float), t_end_s (float), player_identity_id (nullable), track_id (nullable int), confidence (float), meta_json
- `player_match_stats`: id, club_id, match_id, player_identity_id, minutes_tracked (float), distance_proxy_m (float), touches, passes, tackles, shots, turnovers, scoring_events (ints), avg_confidence (float), heatmap_json (JSON: 12x8 grid of floats)
- `artifacts`: id, club_id, match_id (nullable), kind (see §9), storage_key, filename, content_type, size_bytes, created_at, meta_json
- `upload_records`: id, club_id, artifact_id, platform (`youtube`), idempotency_key (unique), status (`pending|uploading|succeeded|failed`), platform_video_id (nullable), url (nullable), title, description (text), tags_json, category_id (str, default "17" Sports), privacy (`private|unlisted|public`, default `private`), error_log_json (JSON list), attempts (int), created_at, updated_at
- `audit_logs`: id, club_id, user_id (nullable), action, entity_type, entity_id, before_json, after_json, created_at
- `club_modules`: id, club_id, module_key, enabled (bool)  — per-club feature overrides

Phase 2/3 scaffold tables live in `playsight/modules/<mod>/models.py`, imported into
metadata (schema visible, endpoints stubbed). Keep them minimal-but-sensible; mark
`# TODO(phase2)` / `# TODO(phase3)`.

## 6. Auth & RBAC

- `playsight.auth.security`: `hash_password`, `verify_password` (bcrypt),
  `create_access_token(user_id, club_id, roles) -> str`,
  `create_refresh_token(...) -> (token, jti)`, `decode_token(token) -> TokenPayload`.
  JWT HS256, claims: `sub` (user_id), `club_id`, `roles` (list[str]), `type`
  (`access|refresh`), `jti`, `exp`, `iat`.
- Roles (str enum `Role`): `admin, coach, analyst, player, guardian, registrar,
  finance_admin, shop_manager`.
- `playsight.auth.rbac.require_roles(*roles)` → FastAPI dependency factory; `admin`
  always passes. `playsight.api.deps.get_current_user` validates access token, loads
  user + roles; `get_tenant` returns `TenantContext(club_id, team_ids, user, roles)`.
- **Every core router enforces club scoping: queries always filter `club_id ==
  tenant.club_id`.** Cross-club access = 404 (not 403) to avoid leaking existence.
- Bootstrap: `POST /api/v1/auth/register-club` creates club + first admin user (open
  only when no clubs exist OR `settings.env == "dev"`, else 403).

## 7. Vision pipeline dataclasses (`playsight.core.types`)

```python
@dataclass
class FrameDetection:      # one person detection in one frame
    frame_index: int; t_s: float
    x1: float; y1: float; x2: float; y2: float   # absolute pixels
    confidence: float

@dataclass
class TrackedBox(FrameDetection):
    track_id: int

@dataclass
class IdentityResult:
    track_id: int
    jersey_number: int | None
    player_id: str | None
    confidence: float
    method: str            # "ocr" | "reid" | "manual" | "unresolved"

@dataclass
class EventSpan:
    event_type: str        # §8 taxonomy
    t_start_s: float; t_end_s: float
    track_id: int | None
    confidence: float
    meta: dict
```

Module public interfaces (each module exposes these from its `__init__.py`):

- `ingestion.probe_video(path) -> VideoInfo(duration_s, fps, width, height, frame_count)`
- `ingestion.ingest_video(path, match_id, storage, db) -> VideoAsset`
- `detection.PersonDetector(conf: float).detect(frame_bgr, frame_index, t_s) -> list[FrameDetection]`
  (`create_detector(settings) -> PersonDetector` picks YOLO if available else `StubDetector`)
- `tracking.Tracker().update(detections, frame_bgr) -> list[TrackedBox]`
  (`create_tracker(settings)` → ByteTrack via supervision, else IOU-based `SimpleTracker`)
- `identification.identify_tracks(video_path, tracks_df, settings) -> list[IdentityResult]`
- `analytics.compute_events(tracks_df, video_info, settings) -> list[EventSpan]`
- `analytics.compute_player_stats(tracks_df, identities, events, video_info) -> list[PlayerStatsRow]`
- `reporting.build_match_summary(...) -> dict`; `reporting.write_player_report_json/pdf(...)`
- `highlights.build_player_highlights(video_path, events, identity, out_path) -> Path`
- `export.render_annotated_video(video_path, tracks_df, identities, out_path) -> Path`
- `export.render_audio_summary(summary: dict, out_path) -> Path` (gTTS → pyttsx3 → tone+`.txt` transcript fallback; never crash offline)
- `pipeline.run_match_pipeline(match_id, video_path, *, db_session_factory, settings, progress_cb=None) -> PipelineResult`
  — orchestrates ingest→detect→track→identify→events→stats→reports→artifacts,
  persists rows + artifacts, returns paths dict keyed by artifact kind.

Tracks dataframe (parquet) columns:
`frame_index:int64, t_s:float64, track_id:int64, x1,y1,x2,y2:float64, confidence:float64`.

## 8. Event taxonomy (MVP, rule-based heuristics)

`playsight.core.types.EventType` str enum — exact values:
`touch`, `pass`, `tackle`, `shot_attempt`, `turnover`, `scoring_event`.

Heuristics (documented honestly as proxies): possession/touch = sustained proximity of
track to motion centroid; pass = touch handoff between tracks within 2s; tackle =
two-track convergence + overlap; shot_attempt = high-velocity displacement toward field
end zones; turnover = possession switch across team clusters; scoring_event = shot
followed by tracking discontinuity near goal region. Every event stores `confidence`
(0–1) and `[t_start_s, t_end_s]`. Never claim these are ground truth — they're MVP
heuristics, refined in M5.

## 9. Artifact kinds & filenames (per match, under `outputs/<match_id>/`)

| kind | filename |
|---|---|
| `player_tracks` | `player_tracks.parquet` |
| `player_identities` | `player_identities.csv` |
| `player_stats` | `player_stats.csv` |
| `match_summary` | `match_summary.json` |
| `annotated_video` | `annotated_video.mp4` |
| `player_report_json` | `player_report_<player_id>.json` |
| `player_report_pdf` | `player_report_<player_id>.pdf` |
| `player_highlights` | `player_highlights_<player_id>.mp4` |
| `match_audio` | `match_summary_audio.mp3` |
| `upload_status` | `upload_status.json` |

(`<player_id>` = players.id when resolved, else `track_<track_id>`.) All artifacts are
also written to object storage under key `matches/<match_id>/<filename>` and registered
in the `artifacts` table.

`match_summary.json` shape:
```json
{
  "match_id": "...", "generated_at": "ISO8601", "video": {"duration_s": 0, "fps": 0},
  "teams": {"home": "...", "away": "..."},
  "counts": {"tracks": 0, "identified": 0, "events": 0},
  "events_by_type": {"touch": 0, "pass": 0, "...": 0},
  "players": [{"player_id": "...", "track_id": 1, "jersey_number": 9,
               "minutes_tracked": 0.0, "touches": 0, "confidence": 0.0}],
  "engine": {"detector": "yolo|stub", "tracker": "bytetrack|simple", "ocr": "easyocr|stub"},
  "limitations": ["..."]
}
```

## 10. Feature flags

`settings.features` dict + per-club `club_modules` override.
`playsight.config.flags.is_enabled(key, club_id=None, db=None) -> bool`.
Keys: `video_analytics` (default **true**), `publishing_youtube` (true),
`competition` (false), `merchandise` (false), `playbook` (false), `training` (false),
`nutrition` (false), `registration` (false), `payments` (false), `commerce` (false).
Disabled module endpoints raise `FeatureDisabledError` → HTTP 403 with code
`feature_disabled`. FastAPI dependency: `require_feature("playbook")`.

## 11. Celery jobs (`playsight.jobs`)

- `playsight.jobs.app`: Celery app named `playsight`, broker/backend = redis_url. Config:
  `task_acks_late=True`, JSON serializers, `task_default_retry_delay=10`.
- Tasks (in `playsight.jobs.tasks`), each takes `job_id: str` (a `processing_jobs` row
  id), sets status running → succeeded/failed, updates `progress`, catches all
  exceptions into `error`, and applies retry w/ exponential backoff (max 3) for
  transient failures:
  `run_analysis(job_id)`, `run_highlights(job_id)`, `run_annotate(job_id)`,
  `run_export_audio(job_id)`, `run_publish_youtube(job_id)`.
- **Eager mode**: when `settings.redis_url` empty or `settings.env == "test"` or env
  var `PLAYSIGHT_EAGER_JOBS=1`, `dispatch_job()` executes synchronously in-process
  (still through the same job-state machinery). `playsight.jobs.dispatch.dispatch_job(db, job) -> None`
  is THE single entry point the API/CLI use.

## 12. REST API (`playsight.api`)

FastAPI app factory `playsight.api.main:create_app()`; module-level `app` for uvicorn.
Prefix `/api/v1`. OpenAPI tags per router. CORS: allow `http://localhost:3000`.

Auth: `POST /auth/register-club` (bootstrap, §6) · `POST /auth/login`
(email+password → `{access_token, refresh_token, token_type}`) · `POST /auth/refresh`
· `GET /auth/me`.

Core (all require auth + tenancy; roles noted):
- `GET/POST /teams`, `GET/POST /players` (write: admin|coach)
- `GET/POST /matches`, `GET /matches/{id}` (write: admin|coach|analyst)
- `POST /matches/{id}/videos` — multipart upload OR `{"source_path": "..."}` for
  server-local files (write: admin|coach|analyst)
- `POST /matches/{id}/process` → creates `analyze` job → `{job_id}` (analyst+)
- `POST /matches/{id}/highlights` body `{"player_identity_id" | "track_id"}` → job
- `POST /matches/{id}/annotate` → job · `POST /matches/{id}/export/audio` → job
- `GET /matches/{id}/summary` · `GET /matches/{id}/events?type=&player=&period=&t0=&t1=`
  · `GET /matches/{id}/stats` · `GET /matches/{id}/players/{identity_id}/report`
- `GET /jobs?status=&kind=` · `GET /jobs/{id}` →
  `{id, kind, status, progress, error, created_at, started_at, finished_at, result}`
- `GET /artifacts?match_id=&kind=` · `GET /artifacts/{id}/download` (StreamingResponse
  w/ correct content-type & filename)
- `POST /publish/youtube` body `{artifact_id, title, description?, tags?, category_id?,
  privacy?}` + header `Idempotency-Key` (optional; server generates if absent). If a
  record with that key exists → return existing record (200), don't re-upload. →
  `{upload_id, job_id}`. `GET /publish/{upload_id}` → full upload record. Requires
  role admin|coach|analyst AND explicit body field `confirm_rights: true` (else 422
  with message about copyright confirmation).
- `GET /health/live` → `{"status": "ok"}` (no auth) · `GET /health/ready` → checks DB
  (+ redis if configured), 503 on failure (no auth).

Phase 2/3 stub routers (behind `require_feature`): `/competition/fixtures|standings`,
`/shop/products`, `/playbook/plays`, `/training/plans`, `/nutrition/templates`,
`/registration/registrations`, `/payments/checkout-session`, `/commerce/cart` — CRUD
skeletons returning real DB rows where scaffolded models exist, else `501` with
`{"todo": "phase2|phase3", "docs": "docs/ROADMAP.md"}`.

Response schemas in `playsight/api/schemas/` (pydantic v2, `model_config =
ConfigDict(from_attributes=True)`).

## 13. YouTube integration (`playsight.integrations.youtube`)

- `YouTubeClient(settings)` — OAuth2 installed-app flow:
  `get_authorize_url()` / `run_local_auth()` (CLI: `playsight youtube auth`), token
  persisted to `settings.youtube.token_file` (json), auto-refresh.
- `upload_video(file_path, *, title, description, tags, category_id="17",
  privacy="private", progress_cb=None) -> UploadResult(video_id, url)` using resumable
  MediaFileUpload; retries with `tenacity` exponential backoff (max 5) on 5xx/quota;
  raises `ExternalServiceError` with structured error log entries appended to
  `upload_records.error_log_json` on final failure.
- Task `run_publish_youtube` writes `upload_status.json` artifact after terminal state.
- NEVER auto-publish: privacy defaults `private`; API requires `confirm_rights: true`.

`playsight.integrations.notifications`: `Notifier` protocol + `LogNotifier` (MVP) +
stubs `EmailNotifier`/`PushNotifier` (`# TODO(phase2)`); `notify(event_key, payload)`.

## 14. CLI (`playsight` entry point, Typer)

```
playsight init-db
playsight seed-demo                       # demo club/team/players + synthetic video
playsight process VIDEO --match-id ... [--club ...]   # single video, end-to-end
playsight process-folder DIR              # batch
playsight export report MATCH_ID --format csv|json --out DIR
playsight highlights MATCH_ID --player IDENTITY_OR_TRACK
playsight export audio MATCH_ID
playsight youtube auth
playsight youtube upload ARTIFACT_PATH --title ... [--privacy private] --confirm-rights
playsight serve api|worker               # uvicorn / celery worker helpers
```
All commands work without Docker (SQLite + local storage + eager jobs).
`seed-demo` generates a synthetic test video (moving colored rectangles w/ numbers,
~20s, via OpenCV) at `data/demo/demo_match.mp4` so the full pipeline runs with stub
or real engines.

## 15. Dashboard (`dashboard/`)

Next.js 14 App Router, TypeScript strict, Tailwind. No UI library beyond Tailwind.
API base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
JWT stored in localStorage (`ps_access`, `ps_refresh`), thin fetch wrapper
`lib/api.ts` with auto-refresh-on-401. Pages:

- `/login` — email/password; `/register` — bootstrap club.
- `/` — matches list + status chips + "process" action.
- `/matches/[id]` — tabs: **Timeline** (event list on a horizontal time axis, filter by
  type/player/period), **Players** (cards: minutes tracked, touches, movement heat
  proxy as a 12x8 CSS grid, confidence bar), **Reports** (per-player report view +
  PDF/JSON download links), **Highlights** (video preview via artifact download URL +
  generate buttons), **Export & Publish** (job list w/ live polling every 2s, retry
  button, status logs; YouTube publish form w/ title/desc/tags/privacy + rights
  confirmation checkbox).
- Components typed against API schemas in `lib/types.ts` (hand-written mirrors).
- Poll `GET /jobs` for progress. Keep it clean, dark-mode friendly, responsive.

## 16. Tests (`tests/`)

- Unit: config loading, auth (hash/verify/JWT roundtrip/RBAC deps), storage (local
  backend tmpdir), stub detector/tracker determinism, event heuristics on synthetic
  tracks, reporting JSON/CSV/PDF generation, highlights ffmpeg command building
  (mock subprocess), youtube client (mock googleapiclient), idempotency logic.
- Integration (`tests/integration/`): FastAPI TestClient + SQLite in-memory + eager
  jobs + local storage: register-club → login → create match → upload tiny synthetic
  video (generate via OpenCV fixture, ~2s, 64x64) → process → poll job → assert
  artifacts exist & downloadable → publish (mocked YouTube) → idempotent re-publish.
- Tenancy test: user from club B gets 404 on club A's match.
- Markers: `@pytest.mark.cv` for tests needing `[cv]` extra (skipped in CI via
  `-m "not cv"`).
- Fixtures in `tests/conftest.py`; aim >70% coverage on non-CV code paths.

## 17. CI (`.github/workflows/ci.yml`)

Jobs: `lint` (ruff check + black --check), `typecheck` (mypy src), `test`
(`pip install -e .[dev]`, `pytest -m "not cv"`, needs system ffmpeg via apt),
`dashboard` (npm ci, `npm run lint`, `npm run build`). Python 3.11 + 3.12 matrix
for tests. Cache pip/npm.

## 18. Legal / safety invariants (enforce in code + docs)

- No biometric face recognition anywhere. Identification = jersey OCR + appearance
  embeddings only; document as non-perfect ("estimated identity, confidence-scored").
- YouTube publishing requires explicit rights confirmation (`confirm_rights: true`).
- Competition adapters (Phase 2): rate limiting + source attribution required in
  the adapter protocol; official APIs preferred (documented in module README).
- Nutrition module outputs carry "not medical advice" disclaimer constants.
- PII: passwords bcrypt-hashed; document storage keys never contain PII; audit logs
  for sensitive mutations; retention/export/delete workflows = documented TODO(phase3)
  with stub service methods.

## 19. Coding standards

- Ruff + Black (100 cols), mypy clean on `src/playsight` (non-strict).
- No print() in library code — structlog only. CLI may use rich console.
- Docstrings on public functions. Type hints everywhere.
- Comments only for non-obvious constraints; TODOs as `# TODO(phase2): ...` /
  `# TODO(phase3): ...` and must also appear in docs/ROADMAP.md.
- Tests must not require network, GPU, Docker, or the `[cv]` extra.
