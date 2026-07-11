# PlaySight_AI

Multi-sport video analytics, club operations, and athlete development — one
platform that turns raw match footage into tracked players, estimated
identities, heuristic events, per-player statistics, reports, highlight reels,
and (rights-confirmed) YouTube publishing, wrapped in a multi-tenant club
management API and dashboard.

**Honesty first:** analytics outputs are heuristic estimates with confidence
scores — not ground truth. See [Known limitations](#known-limitations).

## Architecture at a glance

Video analysis pipeline (orchestrated by `playsight.pipeline.run_match_pipeline`):

```
            ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌───────────┐   ┌────────────┐
 video ──▶ │ ingest  │──▶│ detect  │──▶│  track  │──▶│ identify  │──▶│ analytics  │
            │ (probe, │   │ (YOLO / │   │(ByteTrack│  │(jersey OCR│   │ (events +  │
            │ frames) │   │  stub)  │   │ / IOU)  │   │ + Re-ID)  │   │  stats)    │
            └─────────┘   └─────────┘   └─────────┘   └───────────┘   └─────┬──────┘
                                                                            │
             ┌──────────────────────────────┬───────────────────────────────┤
             ▼                              ▼                               ▼
      ┌────────────┐               ┌──────────────┐                ┌────────────────┐
      │ reporting  │               │  highlights  │                │     export     │
      │ (summary,  │               │ (per-player  │                │ (annotated MP4,│
      │ CSV, PDF)  │               │ reels/ffmpeg)│                │  audio MP3)    │
      └─────┬──────┘               └──────┬───────┘                └───────┬────────┘
            └──────────────────────────────┴──────────────┬────────────────┘
                                                          ▼
                                                  ┌───────────────┐
                                                  │    publish    │
                                                  │ (YouTube, OAuth,
                                                  │  rights-gated)│
                                                  └───────────────┘
```

Service topology (docker-compose):

```
   ┌───────────┐         ┌──────────────────┐          ┌──────────────┐
   │ dashboard │ ──────▶ │       api        │ ───────▶ │   postgres   │
   │ Next.js   │  HTTP   │ FastAPI :8000    │   SQL    │    :5432     │
   │  :3000    │         │  /api/v1         │          └──────────────┘
   └───────────┘         └───┬──────────┬───┘
                             │ enqueue  │ artifacts            ┌─────────┐
                             ▼          ▼                  ┌─▶ │  redis  │
                        ┌─────────┐ ┌─────────┐            │   │  :6379  │
                        │  redis  │ │  minio  │            │   └─────────┘
                        │ broker  │ │ S3 :9000│ ◀──────────┤
                        └────┬────┘ └─────────┘  artifacts │
                             │ consume                     │
                             ▼                             │
                        ┌──────────┐  SQL + storage        │
                        │  worker  │ ──────────────────────┘
                        │ (Celery) │
                        └──────────┘
```

Without Docker the whole platform runs in one process: SQLite + local-disk
storage + eager (synchronous, in-process) jobs.

## Quickstart — no Docker

Requirements: Python 3.11+, Node 20+ (dashboard only), ffmpeg recommended on
`PATH` (highlight/export steps prefer system ffmpeg, falling back to the
bundled `imageio-ffmpeg` binary).

```bash
# 1. Install
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# Optional: real CV engines (YOLO/ByteTrack/EasyOCR — heavy downloads).
# Without this extra the platform uses deterministic stub engines.
pip install -e ".[cv]"

# 2. Create tables (SQLite: ./playsight.db) and seed demo data
playsight init-db
playsight seed-demo      # writes data/demo/demo_match.mp4 + demo club/team/players

# 3. Process the demo video end-to-end (prints the match id and artifact paths)
playsight process data/demo/demo_match.mp4 --match-id <MATCH_ID_FROM_SEED>

# 4. Serve the API (http://localhost:8000, OpenAPI docs at /docs)
playsight serve api

# 5. Dashboard (http://localhost:3000)
cd dashboard
npm install
npm run dev
```

Jobs run eagerly in-process whenever redis is unreachable (or
`PLAYSIGHT_EAGER_JOBS=1` is set), so no broker is needed for local work. To
use a real worker instead: start redis, then `playsight serve worker` in a
second terminal and pass `--no-eager` to processing commands.

PowerShell users can use the wrappers in `scripts/`:
`.\scripts\seed_demo.ps1`, `.\scripts\process_video.ps1 -Video data\demo\demo_match.mp4`,
`.\scripts\run_api.ps1`, `.\scripts\run_worker.ps1`.

## Quickstart — Docker Compose

```bash
docker compose up --build -d      # api, worker, dashboard, postgres, redis, minio
# or the wrapper that also waits for health and runs init-db:
./scripts/dev_up.sh               # PowerShell: .\scripts\dev_up.ps1
```

| Service   | URL                                            |
|-----------|------------------------------------------------|
| API       | http://localhost:8000 (docs at `/docs`)        |
| Dashboard | http://localhost:3000                          |
| MinIO     | http://localhost:9001 (minioadmin/minioadmin)  |
| Postgres  | localhost:5432 (playsight/playsight)           |
| Redis     | localhost:6379                                 |

The compose stack uses Postgres + MinIO (`storage.backend=s3`) and a real
Celery worker. `./data` and `./outputs` are mounted into the api and worker
containers. Set `PLAYSIGHT_AUTH__SECRET_KEY` in your environment (or `.env`)
for anything beyond throwaway dev use.

## Configuration

Settings load in this order (highest precedence first): environment variables
(prefix `PLAYSIGHT_`, nested delimiter `__`) → `.env` → YAML file
(`PLAYSIGHT_CONFIG`, default `configs/default.yaml`) → code defaults.
See `.env.example` for the full annotated list. Highlights:

| Setting (env var) | Default | Notes |
|---|---|---|
| `PLAYSIGHT_DATABASE_URL` | `sqlite:///./playsight.db` | Postgres in docker |
| `PLAYSIGHT_REDIS_URL` | `redis://localhost:6379/0` | empty ⇒ eager jobs |
| `PLAYSIGHT_STORAGE__BACKEND` | `local` | `local` \| `s3` (MinIO = `s3` + endpoint) |
| `PLAYSIGHT_AUTH__SECRET_KEY` | dev-only default | **set in prod** (warning logged) |
| `PLAYSIGHT_PIPELINE__FRAME_STRIDE` | `2` | process every Nth frame |
| `PLAYSIGHT_PIPELINE__MAX_FRAMES` | unset | cap for smoke runs |

## CLI reference

The `playsight` console script (Typer). Every command works without Docker.

| Command | Purpose |
|---|---|
| `playsight init-db` | Create all database tables (idempotent). |
| `playsight seed-demo [--out PATH] [--force]` | Generate the ~20s synthetic demo video + demo club/team/players/match. |
| `playsight process VIDEO [--match-id ID] [--club ID_OR_SLUG] [--eager/--no-eager]` | Process one video end-to-end (creates match/club when missing). |
| `playsight process-folder DIR [--club ...] [--eager/--no-eager]` | Batch-process every `*.mp4`/`*.mov` in a folder (one match per file). |
| `playsight highlights MATCH_ID --player IDENTITY_OR_TRACK` | Build a per-player highlight reel (`--player` accepts an identity id, a numeric track id, or `track_<n>`). |
| `playsight export report MATCH_ID [--format csv\|json] [--out DIR]` | Export stats/identities CSVs or summary/report JSONs. |
| `playsight export audio MATCH_ID` | Render the spoken match-summary MP3. |
| `playsight youtube auth` | Run the Google OAuth2 consent flow; persists the token. |
| `playsight youtube upload PATH --title ... [--privacy private] --confirm-rights` | Upload a local video to YouTube (refuses without `--confirm-rights`). |
| `playsight serve api [--host] [--port] [--reload]` | Run the FastAPI app with uvicorn. |
| `playsight serve worker [--loglevel] [--concurrency] [--pool]` | Run a Celery worker (requires redis; pool defaults to `solo` on Windows). |

## Generated artifacts

Each processed match writes to `outputs/<match_id>/`, mirrors every file to
object storage under `matches/<match_id>/<filename>`, and registers it in the
`artifacts` table (downloadable via `GET /api/v1/artifacts/{id}/download`):

| Kind | Filename |
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

(`<player_id>` is `players.id` when the identity resolved to a rostered
player, else `track_<track_id>`.)

## Feature flags

Global defaults live in `settings.features`; per-club overrides in the
`club_modules` table. Disabled module endpoints answer HTTP 403 with code
`feature_disabled`.

| Flag | Default | Scope |
|---|---|---|
| `video_analytics` | **true** | Phase 1 core |
| `publishing_youtube` | **true** | Phase 1 core |
| `competition` | false | Phase 2 scaffold (fixtures/standings sync) |
| `merchandise` | false | Phase 2 scaffold (club shop catalog) |
| `playbook` | false | Phase 2 scaffold (plays, diagrams, clip links) |
| `training` | false | Phase 2 scaffold (templates, plans, attendance) |
| `nutrition` | false | Phase 2 scaffold (profiles, meal templates) |
| `registration` | false | Phase 3 scaffold (registrations, approvals) |
| `payments` | false | Phase 3 scaffold (Stripe abstraction, fee rules) |
| `commerce` | false | Phase 3 scaffold (cart/checkout/orders) |

## YouTube publishing setup (OAuth2)

1. In the [Google Cloud console](https://console.cloud.google.com/), create (or
   pick) a project and enable the **YouTube Data API v3**.
2. Configure the OAuth consent screen (External + test users is fine for dev)
   with the scope `https://www.googleapis.com/auth/youtube.upload`.
3. Create an **OAuth client ID** of type **Desktop app** and download the
   client secret JSON.
4. Save it to `configs/google_client_secret.json` (or point
   `PLAYSIGHT_YOUTUBE__CLIENT_SECRETS_FILE` at its location). Never commit it.
5. Run `playsight youtube auth` — a browser consent flow runs and the token is
   persisted to `configs/youtube_token.json` (auto-refreshed afterwards).

Publishing safety: uploads default to **private** and are never auto-published.
Both the API (`confirm_rights: true` in the body) and the CLI
(`--confirm-rights`) require an explicit confirmation that you own or have
licensed all rights to the footage; otherwise the request is rejected. The
`Idempotency-Key` header makes API publishes safely retryable — re-posting the
same key returns the existing upload record instead of re-uploading.

## Known limitations

Documented deliberately — the platform is honest about what it computes:

- **Heuristic events are proxies, not ground truth.** Touch / pass / tackle /
  shot_attempt / turnover / scoring_event come from rule-based motion
  heuristics (proximity, convergence, velocity). Every event carries a
  confidence score and time span; refinement with learned models is milestone
  M5 on the roadmap.
- **Identity is confidence-scored estimation, not perfect.** Players are
  identified by jersey-number OCR plus appearance (color-histogram) Re-ID.
  Tracks may stay `unresolved` or be attributed to the wrong player; each
  identity row records its `confidence` and `method`.
- **No face recognition anywhere.** By design and by contract
  (CONTRACTS.md §18), identification never uses biometric face recognition.
- **Stub engines without the `[cv]` extra.** When `torch`/`ultralytics`/
  `easyocr`/`supervision` are not installed (e.g. in CI), deterministic stub
  detector/tracker/OCR implementations run instead and honestly mark their
  output with `"engine": "stub"` in `match_summary.json`. Useful for testing
  the plumbing; not for real analytics.
- **Audio summaries degrade gracefully offline**: gTTS → pyttsx3 → tone +
  text transcript.
- **No committed DB migrations yet.** Alembic is scaffolded and wired to the
  metadata; Phase 1 uses `create_all`.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module map, data flow, job
  lifecycle, tenancy/RBAC, storage layout, logging conventions.
- [docs/API.md](docs/API.md) — full REST endpoint reference.
- [docs/ROADMAP.md](docs/ROADMAP.md) — milestones M1–M10 and consolidated
  Phase 2/3 extension points.
- [docs/CONTRACTS.md](docs/CONTRACTS.md) — the binding engineering contract
  (single source of truth).
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, quality gates, contract-first
  rule.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 PlaySight_AI contributors.
