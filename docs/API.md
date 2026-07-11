# PlaySight_AI — REST API Reference

Base URL: `http://localhost:8000/api/v1` (FastAPI; interactive docs at
`/docs`, OpenAPI JSON at `/openapi.json`). CORS allows
`http://localhost:3000` (the dashboard).

## Conventions

### Authentication

All endpoints except `POST /auth/register-club`, `POST /auth/login`,
`POST /auth/refresh`, and the health probes require a bearer access token:

```
Authorization: Bearer <access_token>
```

Tokens are JWT HS256 with claims `sub` (user id), `club_id`, `roles`,
`type` (`access`|`refresh`), `jti`, `exp`, `iat`. Access tokens live 30
minutes (default); refresh tokens 14 days and rotate on every use.

### Tenancy

Every query is scoped to the caller's club. A resource belonging to another
club answers **404** (not 403) so existence is never leaked.

### Roles

`admin, coach, analyst, player, guardian, registrar, finance_admin,
shop_manager`. Role-restricted endpoints list their roles below; **`admin`
always passes**. Insufficient role → 403 `permission_denied`.

### Error envelope

Every application error uses one body shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Match not found: abc123",
    "correlation_id": "6f1c9a2b4d5e6f708192a3b4c5d6e7f8"
  }
}
```

| HTTP | code | Meaning |
|---|---|---|
| 401 | `auth_error` | Missing/invalid/expired token or credentials |
| 403 | `permission_denied` | Authenticated but role not allowed |
| 403 | `feature_disabled` | Module feature flag off (globally or for this club) |
| 404 | `not_found` | Missing entity or cross-club access |
| 422 | `validation_failed` | Domain validation failure (request-schema errors also answer 422, in FastAPI's default `{"detail": [...]}` shape) |
| 502 | `external_service_error` | Upstream failure (YouTube, storage, ...) |
| 500 | `internal_error` | Unhandled error (no internals leaked) |

### Correlation IDs

Send `X-Correlation-ID` to trace a request; the API generates one otherwise.
The id is echoed on every response header, included in error bodies, and
propagated onto any job the request creates.

### Pagination

List endpoints accept `limit` (1–500, default 50) and `offset` (default 0).

---

## Auth — `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register-club` | none (bootstrap) | Create club + first admin. Open only while **no clubs exist** or `env == "dev"`; else 403. |
| POST | `/auth/login` | none | Exchange email + password for a token pair. |
| POST | `/auth/refresh` | none (refresh token in body) | Rotate: revokes the presented refresh token, issues a fresh pair. |
| GET | `/auth/me` | any user | The authenticated user with role names. |

`POST /auth/register-club` — request/response:

```json
// request
{"club_name": "Rovers FC", "slug": "rovers", "email": "admin@rovers.example",
 "password": "s3cret-pass", "full_name": "Ada Admin"}

// 201 response
{"club": {"id": "…", "name": "Rovers FC", "slug": "rovers", "created_at": "…"},
 "user": {"id": "…", "club_id": "…", "email": "admin@rovers.example",
          "full_name": "Ada Admin", "is_active": true, "created_at": "…",
          "roles": ["admin"]},
 "access_token": "…", "refresh_token": "…", "token_type": "bearer"}
```

`POST /auth/login` — `{"email", "password"}` →
`{"access_token", "refresh_token", "token_type": "bearer"}`.
`POST /auth/refresh` — `{"refresh_token"}` → same token-pair shape.

## Teams — `/teams`

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/teams` | any user | List the club's teams (paginated). |
| POST | `/teams` | admin, coach | Create a team. Body: `{"name", "sport", "age_group"?}` → 201 `TeamRead`. |

## Players — `/players`

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/players?team_id=` | any user | List rostered players. |
| POST | `/players` | admin, coach | Body: `{"team_id", "full_name", "jersey_number"?, "position"?, "external_ref"?}` → 201. |

## Matches — `/matches`

Write endpoints require **admin, coach, or analyst**.

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/matches?status=&team_id=` | any user | List matches, newest first. |
| POST | `/matches` | admin, coach, analyst | Create a match (audit-logged) → 201. |
| GET | `/matches/{id}` | any user | Fetch one match. |
| DELETE | `/matches/{id}` | admin, coach, analyst | Delete the match and all derived rows → 204. |
| POST | `/matches/{id}/videos` | admin, coach, analyst | Register a video: multipart `file` upload **or** JSON `{"source_path": "..."}` for server-local files → 201 `VideoAssetRead`. |
| POST | `/matches/{id}/process` | admin, coach, analyst | Full analysis pipeline for the match's ready video → 202 `{"job_id"}`. 422 when no ready video is registered. |
| POST | `/matches/{id}/highlights` | admin, coach, analyst | Body: `{"player_identity_id"}` or `{"track_id"}` (at least one) → 202 `{"job_id"}`. |
| POST | `/matches/{id}/annotate` | admin, coach, analyst | Render the annotated (boxes + track ids) video → 202 `{"job_id"}`. |
| POST | `/matches/{id}/export/audio` | admin, coach, analyst | Render the spoken match-summary MP3 → 202 `{"job_id"}`. |
| GET | `/matches/{id}/summary` | any user | The `match_summary.json` payload (404 until processed). |
| GET | `/matches/{id}/events?type=&player=&period=&t0=&t1=` | any user | Heuristic events with filters (type, `player`=identity id, 1-based period from the match's period config, `[t0, t1]` seconds window). |
| GET | `/matches/{id}/stats` | any user | Per-player stats rows, each embedding its estimated identity. |
| GET | `/matches/{id}/players/{identity_id}/report` | any user | Per-player JSON report for one identity. |

`POST /matches` request:

```json
{"team_id": "…", "opponent": "City Rivals", "sport": "football",
 "kickoff_at": "2026-07-12T14:00:00Z", "venue": "Home Ground",
 "period_config": {"periods": 2, "period_minutes": 45}}
```

`MatchEventRead` example (events are heuristic proxies with confidence — not
ground truth):

```json
{"id": "…", "match_id": "…", "event_type": "pass", "t_start_s": 63.2,
 "t_end_s": 65.1, "player_identity_id": "…", "track_id": 4,
 "confidence": 0.62, "meta": {}}
```

## Jobs — `/jobs`

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/jobs?status=&kind=&match_id=` | any user | List the club's processing jobs, newest first. |
| GET | `/jobs/{id}` | any user | One job with progress/result. |

`JobRead`:

```json
{"id": "…", "kind": "analyze", "status": "succeeded", "progress": 1.0,
 "error": null, "created_at": "…", "started_at": "…", "finished_at": "…",
 "result": {"counts": {"tracks": 6, "events": 42}, "artifact_paths": {"…": "…"}},
 "match_id": "…", "correlation_id": "…"}
```

Statuses: `queued → running → succeeded | failed | cancelled`. Kinds:
`analyze`, `highlights`, `annotate`, `export_audio`, `publish`. The dashboard
polls `GET /jobs` every 2 seconds for live progress.

## Artifacts — `/artifacts`

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/artifacts?match_id=&kind=` | any user | List generated artifacts (see CONTRACTS §9 for kinds/filenames). |
| GET | `/artifacts/{id}/download` | any user | Streams the file with its stored `Content-Type` and a `Content-Disposition` filename. |

## Publish — `/publish` (feature flag: `publishing_youtube`)

Requires role **admin, coach, or analyst**.

| Method | Path | Description |
|---|---|---|
| POST | `/publish/youtube` | Create an upload record + publish job for an artifact → 201 `{"upload_id", "job_id", "status"}`. |
| GET | `/publish/{upload_id}` | Full upload record: status, `platform_video_id`, `url`, structured `error_log`, attempts. |

Request body:

```json
{"artifact_id": "…", "title": "U15 vs Rivals — highlights",
 "description": "", "tags": ["football", "u15"], "category_id": "17",
 "privacy": "private", "confirm_rights": true}
```

**Rights confirmation (legal invariant):** `confirm_rights` must be `true` —
the caller confirms they own or have licensed all rights to the footage —
otherwise the request fails 422. `privacy` defaults to `private`; the
platform never auto-publishes.

**Idempotency:** send an `Idempotency-Key` header (the server generates one
when absent). Re-posting the same key returns the **existing** record with
HTTP **200** (instead of 201) and does not re-upload — safe to retry.
Concurrent posts racing on the same key resolve to the winner's record.

Terminal upload states also write an `upload_status.json` artifact for the
match.

## Health — `/health` (no auth)

| Method | Path | Description |
|---|---|---|
| GET | `/health/live` | `{"status": "ok"}` — process is up. |
| GET | `/health/ready` | Checks database (+ redis when configured). 200 with `{"status", "checks": {...}}`, or **503** when any dependency fails. |

---

## Phase 2/3 module endpoints (feature-flagged scaffolds)

Each module router is guarded by `require_feature(<flag>)` — with the flag
disabled (the default) every endpoint answers **403 `feature_disabled`**.
Simple CRUD returns real DB rows; flows that are not implemented yet answer
**501** with `{"todo": "phase2"|"phase3", "docs": "docs/ROADMAP.md"}`. All
endpoints require auth + tenancy like the core API.

### Competition — `/competition` (flag `competition`, Phase 2)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/competition/adapters` | any user | Available sync adapters (demo adapter in MVP). |
| GET/POST | `/competition/sources` | write: admin, coach | Configured competition sources. |
| DELETE | `/competition/sources/{id}` | admin, coach | |
| POST | `/competition/sync` · `/competition/sources/{id}/sync` | admin, coach, analyst | Pull fixtures/standings via the adapter (rate limiting + attribution required by the adapter protocol). |
| GET/POST | `/competition/fixtures` | write: admin, coach | |
| GET | `/competition/standings` | any user | |

### Shop / merchandise — `/shop` (flag `merchandise`, Phase 2)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST/DELETE | `/shop/categories[/{id}]` | write: admin, shop_manager | |
| GET/POST | `/shop/products` · GET/PATCH/DELETE `/shop/products/{id}` | write: admin, shop_manager | |
| POST | `/shop/products/{id}/variants` · PATCH/DELETE `/shop/variants/{id}` | admin, shop_manager | |
| POST | `/shop/variants/{id}/inventory` | admin, shop_manager | Inventory adjustment. |
| GET | `/shop/analytics/sales` | admin, shop_manager, finance_admin | **501** until the commerce order tables land. |

### Playbook — `/playbook` (flag `playbook`, Phase 2)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST | `/playbook/plays` · GET/DELETE `/playbook/plays/{id}` | write: admin, coach | |
| POST | `/playbook/plays/{id}/revisions` · GET `/playbook/plays/{id}/versions` | admin, coach | Versioned play revisions. |
| POST/GET | `/playbook/plays/{id}/assignments` · DELETE `/playbook/assignments/{id}` | admin, coach | |
| POST/GET | `/playbook/plays/{id}/clips` · DELETE `/playbook/clips/{id}` | admin, coach | Links plays to match-event clips. |

### Training — `/training` (flag `training`, Phase 2)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST/DELETE | `/training/templates[/{id}]` | write: admin, coach | |
| GET/POST | `/training/plans` · GET/PATCH/DELETE `/training/plans/{id}` | write: admin, coach | |
| POST/GET | `/training/plans/{id}/attendance` | admin, coach, analyst | |
| POST/GET/DELETE | `/training/notes[/{id}]` | admin, coach | Coach notes. |
| GET | `/training/players/{id}/workload` | staff | **501** — workload recommendations from `player_match_stats` are Phase 2. |

### Nutrition — `/nutrition` (flag `nutrition`, Phase 2)

Outputs carry a "not medical advice" disclaimer.

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST | `/nutrition/templates` · GET/DELETE `/nutrition/templates/{id}` | write: admin, coach | Meal templates. |
| GET/POST | `/nutrition/profiles` · GET/PATCH/DELETE `/nutrition/profiles/{id}` | write: admin, coach | |
| GET/POST/PATCH/DELETE | `/nutrition/reminders[/{id}]` | admin, coach | Hydration reminders. |
| GET | `/nutrition/players/{id}/macro-targets` | any user | **501** — macro-target recommendations are Phase 2. |

### Registration — `/registration` (flag `registration`, Phase 3)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST | `/registration/forms` | write: registrar | |
| GET/POST | `/registration/registrations` · GET `/registration/registrations/{id}` | any user | |
| POST | `/registration/registrations/{id}/submit` | any user | Submit for approval. |
| POST | `/registration/registrations/{id}/status` | registrar | Approval workflow transition. |
| POST | `/registration/registrations/{id}/documents` | any user | **501** — document upload to object storage is Phase 3. |

### Payments — `/payments` (flag `payments`, Phase 3)

Financial writes require **finance_admin**.

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST | `/payments/fee-rules` | write: finance_admin | |
| GET/POST | `/payments/coupons` | finance_admin | |
| POST | `/payments/coupons/preview` | any user | Preview a coupon against an amount. |
| GET/POST | `/payments/invoices` · GET `/payments/invoices/{id}` | write: finance_admin | |
| GET | `/payments/payments` | finance_admin | |
| POST | `/payments/checkout-session` | any user | **501** — Stripe checkout is Phase 3. |
| POST | `/payments/webhooks/stripe` | none (webhook) | **501** — signature verification + processing is Phase 3. |

### Commerce — `/commerce` (flag `commerce`, Phase 3)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/commerce/cart` | any user | The caller's active cart. |
| POST | `/commerce/cart/items` · PATCH/DELETE `/commerce/cart/items/{id}` | any user | |
| POST | `/commerce/checkout` | any user | **501** — checkout wires to the payments provider in Phase 3. |
| GET | `/commerce/orders` · GET `/commerce/orders/{id}` | any user | |
| POST | `/commerce/orders/{id}/status` | shop_manager | Order state transition. |
| GET/POST | `/commerce/shipping-configs` · `/commerce/tax-configs` · `/commerce/promotions` | write: shop_manager | |

---

## End-to-end example

```bash
API=http://localhost:8000/api/v1

# 1. Bootstrap + login
curl -s $API/auth/register-club -H 'Content-Type: application/json' -d '{
  "club_name": "Rovers FC", "email": "admin@rovers.example",
  "password": "s3cret-pass", "full_name": "Ada Admin"}'
TOKEN=<access_token from the response>
AUTH="Authorization: Bearer $TOKEN"

# 2. Team + match
TEAM=$(curl -s $API/teams -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name": "First XI", "sport": "football"}' | jq -r .id)
MATCH=$(curl -s $API/matches -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"team_id\": \"$TEAM\", \"opponent\": \"City\", \"sport\": \"football\"}" | jq -r .id)

# 3. Upload video (multipart) and process
curl -s $API/matches/$MATCH/videos -H "$AUTH" -F "file=@data/demo/demo_match.mp4"
JOB=$(curl -s -X POST $API/matches/$MATCH/process -H "$AUTH" | jq -r .job_id)

# 4. Poll the job, then read results
curl -s $API/jobs/$JOB -H "$AUTH" | jq .status
curl -s $API/matches/$MATCH/summary -H "$AUTH"
curl -s "$API/artifacts?match_id=$MATCH" -H "$AUTH"

# 5. Publish a highlight artifact to YouTube (idempotent, rights-confirmed)
curl -s $API/publish/youtube -H "$AUTH" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: my-unique-key-1" -d '{
    "artifact_id": "<artifact id>", "title": "Match highlights",
    "privacy": "private", "confirm_rights": true}'
```
