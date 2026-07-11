# Playbook module (Phase 2 scaffold)

Feature flag: `playbook` (default **off**; per-club override via `club_modules`).
API prefix: `/api/v1/playbook` (mounted by `playsight.api`).

## Scope

Tactical plays with diagrams, per-player assignments, tags, version history,
and links from plays to detected match events (video clips).

- `plays` — one row **per version**; `category` is
  `set_piece|defense|attack|transition`; `diagram_storage_key` points at an
  uploaded diagram in object storage; `tags_json` is a list of strings.
- `play_assignments` — role + instructions, optionally bound to a `players` row.
- `play_clip_links` — FK to `match_events`, so a play can be illustrated by
  real (heuristic, confidence-scored) footage spans.

## Versioning model

Plays are immutable. `POST /plays/{id}/revisions` creates a new row with
`version + 1` and `parent_play_id` set to the revised row; unset fields are
inherited. `GET /plays/{id}/versions` walks the chain (oldest first).
`GET /plays?latest_only=true` (default) hides superseded versions.

## Implemented

- Play CRUD + revisions + version history.
- Search-by-tag (`GET /plays?tag=...`, case-insensitive) and category/team
  filters.
- Assignments and clip links CRUD (clip targets validated club-scoped).

## Stubs (raise `NotImplementedError`)

- `PlaybookService.suggest_clips` — rank match events as clip candidates.

## Endpoints

- `GET|POST /plays`, `GET|DELETE /plays/{id}`
- `POST /plays/{id}/revisions`, `GET /plays/{id}/versions`
- `GET|POST /plays/{id}/assignments`, `DELETE /assignments/{id}`
- `GET|POST /plays/{id}/clips`, `DELETE /clips/{id}`

Writes require role `admin` or `coach`.

## Extension points

- Diagram uploads: store via `playsight.storage`, then set
  `diagram_storage_key` on a revision.
- Clip suggestions: implement `suggest_clips` against `match_events`.

## TODO

- `TODO(phase2)`: clip suggestions ranked by event-type affinity + confidence.
- `TODO(phase2)`: indexed JSON tag search (Postgres GIN) instead of the
  in-Python filter.
- `TODO(phase3)`: diagram editor asset pipeline (SVG canvas -> storage).
