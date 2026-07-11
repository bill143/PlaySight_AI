# Competition module (Phase 2 scaffold)

Feature flag: `competition` (default **off**; per-club override via `club_modules`).
API prefix: `/api/v1/competition` (mounted by `playsight.api`).

## Scope

Sync fixtures and standings from external competition data sources into
club-scoped tables, plus manual fixture entry.

- `competition_sources` — configured sources; each references a registered
  adapter (`adapter_key`), stores adapter `attribution`, and keeps the
  change-detection hash of the last sync (`last_sync_hash`).
- `competition_fixtures` — synced or manually entered fixtures (per-row
  `content_hash` for future incremental diffing).
- `competition_standings` — league-table rows.

## Adapters

`adapters/base.py` defines the `CompetitionAdapter` protocol and the registry.
Per CONTRACTS.md §18, every adapter **must** declare:

- `rate_limit_per_minute` — maximum upstream request rate (enforced by sync
  orchestration; throttling itself is `TODO(phase2)`).
- `attribution` — human-readable source attribution, surfaced on every synced
  record and in the UI.

Official / licensed APIs are the preferred sources; scraping is out of scope.
`adapters/demo.py` ships a deterministic, network-free `demo` adapter used by
tests and demos.

To add an adapter: implement the protocol, then
`register_adapter(MyAdapter())` (importing your module must perform the
registration, mirroring `demo.py`).

## Sync

`sync.py::sync_competition(club_id, db, source_id=None)`:

1. fetch fixtures + standings via the source's adapter,
2. hash the canonical-JSON payload (`compute_change_hash`),
3. no-op when the hash equals `last_sync_hash`, otherwise replace the
   source's rows and store the new hash.

## Endpoints

- `GET /adapters` — registered adapters (key, rate limit, attribution)
- `GET|POST /sources`, `DELETE /sources/{id}` (write: admin|coach)
- `POST /sync`, `POST /sources/{id}/sync` (admin|coach|analyst)
- `GET|POST /fixtures` (write: admin|coach), `GET /standings`

## Extension points

- New adapters via the registry (see above).
- `CompetitionService.map_external_teams` — hook for attaching
  `Fixture.team_id` from external team names.

## TODO

- `TODO(phase2)`: scheduled sync — Celery beat task in `playsight.jobs`
  calling `sync_competition` per enabled source (deliberately not written into
  `playsight/jobs/` yet).
- `TODO(phase2)`: enforce `rate_limit_per_minute` with a shared token bucket.
- `TODO(phase2)`: external-team mapping (`map_external_teams`).
- `TODO(phase2)`: incremental row diffing using per-row `content_hash`.
