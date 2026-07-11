# PlaySight AI

> Multi-sport video analytics platform

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-lightgrey)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-MVP%20in%20progress-blue)](#)

PlaySight AI ingests match footage, detects and tracks players and the ball, identifies athletes through jersey OCR and re-identification signals, and turns raw video into analytics, reports, highlight packages, exportable datasets, and YouTube-ready publishing workflows.

## What PlaySight AI does

The platform is designed for clubs, analysts, coaches, and operators who need a repeatable workflow from video ingestion through post-match delivery:

1. Ingest full-match or training video
2. Detect players and the ball
3. Track entities across frames with persistent IDs
4. Identify players with jersey OCR and Re-ID pipelines
5. Generate analytics, summaries, and player reports
6. Extract highlights and annotated exports
7. Publish assets and clips to YouTube

## Architecture

```text
                            +------------------------------+
                            |      Dashboard (Next.js)     |
                            |  login / matches / reports   |
                            +---------------+--------------+
                                            |
                                            v
+--------------------+        +-------------+-------------+        +----------------------+
|  PostgreSQL        |<------>|      FastAPI Backend      |<------>|      MinIO / S3      |
|  metadata, auth,   |        |   REST API + orchestration|        | video, reports, clips|
|  jobs, reports     |        +-------------+-------------+        +----------------------+
+--------------------+                      |
                                            |
                                            v
                                    +-------+-------+
                                    |     Redis      |
                                    | queues / cache |
                                    +-------+-------+
                                            |
                      +---------------------+----------------------+
                      |                     |                      |
                      v                     v                      v
             +----------------+   +----------------+     +----------------+
             | Celery Worker  |   | Celery Beat    |     | Flower Monitor |
             | async jobs     |   | scheduled jobs |     | queue insights |
             +--------+-------+   +----------------+     +----------------+
                      |
                      v
        +---------------------------------------------------------------+
        |                           ML Pipeline                          |
        | Detection -> Tracking -> Identification -> Analytics           |
        | -> Reporting -> Highlights -> Export -> YouTube Publish       |
        +---------------------------------------------------------------+
```

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Service URLs:

- API: http://localhost:8000
- API docs (Swagger UI): http://localhost:8000/docs
- API docs (ReDoc): http://localhost:8000/redoc
- Dashboard: http://localhost:3000
- Flower: http://localhost:5555
- MinIO API: http://localhost:9000
- MinIO Console: http://localhost:9001

## Development setup

### Backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cp .env.example .env
alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload
```

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### Makefile shortcuts

```bash
make dev
make lint
make test
make migrate
```

## CLI usage examples

```bash
python backend/cli.py process-video /path/to/match.mp4
python backend/cli.py process-folder /path/to/folder
python backend/cli.py export-reports --match-id 123
python backend/cli.py generate-highlights --match-id 123
python backend/cli.py export-audio --match-id 123
python backend/cli.py upload-youtube --match-id 123
```

## API overview

| Area | Method | Endpoint | Purpose |
| --- | --- | --- | --- |
| Auth | POST | `/api/v1/auth/login` | Exchange credentials for access and refresh tokens |
| Auth | POST | `/api/v1/auth/refresh` | Rotate an access token using a refresh token |
| Matches | POST | `/api/v1/matches/ingest` | Submit a new video ingestion and processing job |
| Matches | GET | `/api/v1/matches` | List matches and processing state |
| Matches | GET | `/api/v1/matches/{id}` | Retrieve match metadata and derived assets |
| Jobs | GET | `/api/v1/jobs/{id}/status` | Monitor pipeline progress |
| Players | GET | `/api/v1/players/{id}/report` | Fetch player analytics and summaries |
| Highlights | GET | `/api/v1/players/{id}/highlights` | Fetch player-specific highlight artifacts |
| Publishing | POST | `/api/v1/publish/youtube` | Publish a processed asset to YouTube |
| Health | GET | `/api/v1/health` | Basic application health check |

See [docs/api.md](docs/api.md) for detailed request and response examples.

## Dashboard overview

The Next.js dashboard includes the primary operator workflows:

- Login
- Dashboard overview
- Matches list and match detail pages
- Player report views
- Publish panel for downstream distribution

## Testing

```bash
python -m pytest tests/ -v
make test
```

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [API reference](docs/api.md)

## License

Distributed under the [MIT License](LICENSE).
