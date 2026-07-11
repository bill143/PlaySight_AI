# Training module (Phase 2 scaffold)

Feature flag: `training` (default **off**; per-club override via `club_modules`).
API prefix: `/api/v1/training` (mounted by `playsight.api`).

## Scope

Role-based session templates, multi-week periodized plans, per-session
attendance tracking, and coach notes.

- `training_templates` — reusable session templates targeting a player
  role/position (`role`, ordered `drills_json`, `duration_minutes`).
- `training_plans` — multi-week plans; `periodization_json` shape:
  `{"weeks": [{"week": 1, "focus": "conditioning", "load": 0.8}, ...]}`;
  status `draft|active|archived`.
- `training_attendance` — one row per player per session
  (`present|absent|excused|injured`, optional note).
- `coach_notes` — free-text notes per player, optional plan link, `visibility`
  `coaches` (default) or `player`.

## Implemented

- Templates/plans CRUD (plan PATCH included), attendance recording/listing,
  coach notes (author = current user), all club-scoped with 404 on
  cross-club access.

## Stubs (raise `NotImplementedError`)

- `TrainingService.recommend_workload(club_id, player_id)` — will aggregate
  recent `player_match_stats` rows (minutes_tracked, distance_proxy_m,
  touches) plus attendance history into a next-week load recommendation.
  Exposed as `GET /players/{id}/workload`, currently 501 `{"todo": "phase2"}`.

## Endpoints

- `GET|POST /templates`, `DELETE /templates/{id}`
- `GET|POST /plans`, `GET|PATCH|DELETE /plans/{id}`
- `GET|POST /plans/{id}/attendance`
- `GET|POST /notes`, `DELETE /notes/{id}` (staff-only reads)
- `GET /players/{id}/workload` — 501 until Phase 2

Writes require role `admin` or `coach`.

## Extension points

- Periodization JSON is intentionally schemaless in Phase 2; firm it up once
  the dashboard editor lands.
- `recommend_workload` is the single hook for load analytics.

## TODO

- `TODO(phase2)`: workload recommendation from `player_match_stats`
  (acute:chronic proxy, honest confidence — stats are heuristic proxies).
- `TODO(phase2)`: per-session scheduling (calendar) instead of bare
  `session_at` timestamps.
- `TODO(phase3)`: player-visible plan sharing and acknowledgement flow.
