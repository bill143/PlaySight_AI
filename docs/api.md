# PlaySight AI REST API

Base URL: `/api/v1`

Authentication uses bearer tokens obtained from `POST /api/v1/auth/login` and refreshed via `POST /api/v1/auth/refresh`.

Interactive API documentation is available at:

- `/docs` — Swagger UI
- `/redoc` — ReDoc

## Authentication

Send the access token in the `Authorization` header:

```http
Authorization: ******
```

---

## Auth

### `POST /api/v1/auth/login`

Authenticate a user and return access and refresh tokens.

**Request body**

```json
{
  "email": "analyst@example.com",
  "password": "your-password"
}
```

**Response schema**

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "analyst@example.com",
    "role": "admin"
  }
}
```

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@example.com","password":"secret"}'
```

### `POST /api/v1/auth/refresh`

Issue a new access token from a valid refresh token.

**Request body**

```json
{
  "refresh_token": "string"
}
```

**Response schema**

```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

---

## Matches

### `POST /api/v1/matches/ingest`

Create a processing job for a new match upload or external video reference.

**Request body**

```json
{
  "title": "Matchday 12 - Home vs Away",
  "sport": "football",
  "video_path": "s3://playsight/uploads/matchday12.mp4",
  "played_at": "2026-07-10T18:30:00Z",
  "competition": "Regional League"
}
```

**Response schema**

```json
{
  "match_id": "uuid",
  "job_id": "uuid",
  "status": "queued",
  "message": "Match ingestion scheduled"
}
```

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/matches/ingest \
  -H "Authorization: ******" \
  -H "Content-Type: application/json" \
  -d '{"title":"Matchday 12 - Home vs Away","sport":"football","video_path":"s3://playsight/uploads/matchday12.mp4"}'
```

### `GET /api/v1/matches/{id}`

Fetch a single match with status, linked artifacts, and summary metadata.

**Path params**

- `id` — match UUID

**Response schema**

```json
{
  "id": "uuid",
  "title": "Matchday 12 - Home vs Away",
  "sport": "football",
  "status": "processed",
  "played_at": "2026-07-10T18:30:00Z",
  "artifacts": [
    {
      "id": "uuid",
      "type": "annotated_video",
      "url": "https://example.local/artifacts/uuid"
    }
  ],
  "summary": {
    "players_identified": 22,
    "events_detected": 148
  }
}
```

**Example**

```bash
curl http://localhost:8000/api/v1/matches/<match-id> \
  -H "Authorization: ******"
```

### `GET /api/v1/matches`

List matches with optional pagination and filtering.

**Query params**

- `page` — page number
- `page_size` — results per page
- `status` — optional processing state filter
- `sport` — optional sport filter

**Response schema**

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Matchday 12 - Home vs Away",
      "sport": "football",
      "status": "processed",
      "played_at": "2026-07-10T18:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

**Example**

```bash
curl "http://localhost:8000/api/v1/matches?page=1&page_size=20&status=processed" \
  -H "Authorization: ******"
```

---

## Jobs

### `GET /api/v1/jobs/{id}/status`

Inspect the status and progress of an asynchronous pipeline job.

**Path params**

- `id` — job UUID

**Response schema**

```json
{
  "job_id": "uuid",
  "status": "running",
  "progress": 64,
  "stage": "analytics",
  "message": "Generating player reports"
}
```

**Example**

```bash
curl http://localhost:8000/api/v1/jobs/<job-id>/status \
  -H "Authorization: ******"
```

---

## Players

### `GET /api/v1/players/{id}/report`

Return a player report for a match or reporting window.

**Path params**

- `id` — player UUID

**Query params**

- `match_id` — optional match UUID

**Response schema**

```json
{
  "player_id": "uuid",
  "name": "Alex Morgan",
  "match_id": "uuid",
  "stats": {
    "distance_meters": 10432,
    "top_speed_kph": 29.8,
    "shots": 4,
    "passes": 36
  },
  "heatmap_artifact_id": "uuid",
  "report_artifact_id": "uuid"
}
```

**Example**

```bash
curl "http://localhost:8000/api/v1/players/<player-id>/report?match_id=<match-id>" \
  -H "Authorization: ******"
```

### `GET /api/v1/players/{id}/highlights`

Return highlight metadata for a specific player.

**Path params**

- `id` — player UUID

**Query params**

- `match_id` — optional match UUID
- `limit` — optional clip count limit

**Response schema**

```json
{
  "player_id": "uuid",
  "match_id": "uuid",
  "highlights": [
    {
      "artifact_id": "uuid",
      "start_seconds": 512,
      "end_seconds": 526,
      "event_type": "shot"
    }
  ]
}
```

**Example**

```bash
curl "http://localhost:8000/api/v1/players/<player-id>/highlights?match_id=<match-id>&limit=10" \
  -H "Authorization: ******"
```

---

## Artifacts

### `GET /api/v1/artifacts/{id}/download`

Download or redirect to a generated artifact such as a report, clip, or annotated video.

**Path params**

- `id` — artifact UUID

**Response schema**

Binary response or a signed URL redirect, typically accompanied by metadata such as content type and filename headers.

**Example**

```bash
curl -L http://localhost:8000/api/v1/artifacts/<artifact-id>/download \
  -H "Authorization: ******" \
  -o artifact.bin
```

---

## Publishing

### `POST /api/v1/publish/youtube`

Publish a processed asset to YouTube.

**Request body**

```json
{
  "artifact_id": "uuid",
  "title": "Matchday 12 Highlights",
  "description": "Automated highlight package generated by PlaySight AI",
  "privacy_status": "unlisted"
}
```

**Response schema**

```json
{
  "publish_job_id": "uuid",
  "status": "queued",
  "platform": "youtube",
  "video_id": null
}
```

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/publish/youtube \
  -H "Authorization: ******" \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"<artifact-id>","title":"Matchday 12 Highlights","description":"Automated highlight package generated by PlaySight AI","privacy_status":"unlisted"}'
```

---

## Health

### `GET /api/v1/health`

Simple availability probe for load balancers, dashboards, and smoke tests.

**Response schema**

```json
{
  "status": "ok",
  "service": "PlaySight AI",
  "environment": "development"
}
```

**Example**

```bash
curl http://localhost:8000/api/v1/health
```
