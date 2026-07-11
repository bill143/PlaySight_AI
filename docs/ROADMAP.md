# PlaySight_AI — Roadmap

Milestones M1–M10 per the project brief. **M1–M4 are delivered in MVP form**
(Phase 1); M5+ are planned, with Phase 2/3 modules already scaffolded behind
feature flags (schema + CRUD + `501`/`NotImplementedError` stubs marked
`TODO(phase2)` / `TODO(phase3)` in code).

## Milestones

| Milestone | Scope | Status |
|---|---|---|
| **M1 — Detection & tracking** | Video ingest/probing, YOLO person detection with deterministic stub fallback, ByteTrack (via `supervision`) with IOU fallback, `player_tracks.parquet` | **Delivered (MVP)** |
| **M2 — Player identification** | Jersey-number OCR (EasyOCR, stub fallback) + appearance (HSV histogram) Re-ID, roster mapping by jersey number, confidence-scored `player_identities` (no face recognition, by design) | **Delivered (MVP)** |
| **M3 — Analytics: events & stats** | Rule-based event segmentation (touch/pass/tackle/shot_attempt/turnover/scoring_event) with confidence + time spans, per-player stats (minutes, distance proxy, event counts, 12x8 heatmap) | **Delivered (MVP, heuristic proxies)** |
| **M4 — Reporting, highlights, export & publishing platform** | Match summary JSON, player reports (JSON/PDF), CSVs, per-player highlight reels, annotated video, audio summaries, YouTube publishing (OAuth2, idempotent, rights-gated) — plus the platform itself: multi-tenant API + RBAC, jobs (Celery/eager), object storage, CLI, dashboard, docker-compose | **Delivered (MVP)** |
| **M5 — Learned event detection** | Replace M3 heuristics with trained event models (per-sport), calibrated confidences, evaluation harness expansion (`playsight.evaluation`), ball tracking | Planned |
| **M6 — Competition operations** | Fixtures/standings sync adapters (official APIs preferred, rate-limited, source-attributed), scheduled sync, external-team mapping | Scaffolded behind `competition` flag |
| **M7 — Coaching suite** | Playbook (plays, versioned revisions, assignments, event-clip links, clip suggestions) + training (templates, periodized plans, attendance, workload recommendations) | Scaffolded behind `playbook`/`training` flags |
| **M8 — Athlete development & communications** | Nutrition (profiles, meal templates, macro targets — never medical advice) + notification delivery (email/push) | Scaffolded behind `nutrition` flag; notifier stubs in place |
| **M9 — Club operations & commerce** | Registration + approval workflow with documents, payments (Stripe abstraction, fee rules, webhooks), merchandise catalog with Shopify/Woo adapters, cart/checkout/orders; PII retention/export/delete workflows | Scaffolded behind `registration`/`payments`/`merchandise`/`commerce` flags |
| **M10 — Advanced tactical assistant + personalization** | Tactical pattern mining over events/tracks, formation and phase-of-play analysis, personalized development plans and per-player insight feeds built on M5–M8 data | Planned |

## Consolidated extension points in the codebase

Every deferred behavior is marked in code as `# TODO(phase2): ...` or
`# TODO(phase3): ...` (CONTRACTS.md §19 requires each marker to appear here).

### TODO(phase2)

Competition (`src/playsight/modules/competition/`):

- Scheduled sync — register a Celery beat task in `playsight.jobs` (`sync.py`).
- Enforce `rate_limit_per_minute` throttling with a shared token bucket before
  adapter fetches (`sync.py`; the adapter protocol already carries the field).
- External-team mapping: fuzzy-match adapter team names against `teams.name`
  (`service.py::map_external_teams`).
- Incremental row diffing using per-row `content_hash` (module README).

Merchandise (`src/playsight/modules/merchandise/`):

- Shopify Admin GraphQL adapter (per-club token) (`adapters/shopify.py`).
- WooCommerce REST v3 adapter (`adapters/woocommerce.py`).
- Sales analytics aggregated over commerce order lines (`service.py`;
  endpoint answers 501 until the commerce order tables land).
- External catalog import/upsert by `external_ref`/SKU (`service.py`).

Playbook (`src/playsight/modules/playbook/`):

- Clip suggestions: rank `match_events` by play-category affinity
  (`service.py`; endpoint answers 501).
- Replace the in-Python tag filter with an indexed JSON (Postgres GIN) query
  (`service.py`).

Training (`src/playsight/modules/training/`):

- Workload recommendations aggregated from recent `player_match_stats`
  (`service.py`; endpoint answers 501).
- Per-session calendar scheduling instead of bare plan date ranges (README).

Nutrition (`src/playsight/modules/nutrition/`):

- Macro-target recommendations derived from profile + training load — always
  carrying the "not medical advice" disclaimer (`service.py`; endpoint
  answers 501).
- Reminder delivery through the notifications integration (README).

Notifications (`src/playsight/integrations/notifications/`):

- `EmailNotifier`: provider-backed delivery (SMTP / SES) (`email.py`).
- `PushNotifier`: mobile/web push (FCM / APNs / web push) (`push.py`).

Also: M5 event-model refinement replaces the M3 heuristics (tracked at the
milestone level; `analytics/events.py` documents each heuristic as a proxy).

### TODO(phase3)

Registration (`src/playsight/modules/registration/`):

- Document upload to object storage (`playsight.storage.put_bytes`) with
  audit logging and virus scanning (`service.py`; endpoint answers 501).
- Enforce payment-required-before-activation when approving (`service.py`).
- Registrant data export workflow (PII) (`service.py`).
- Registrant data deletion/anonymization workflow with tombstone audit rows
  (`service.py`; models documented in `models.py`).

Payments (`src/playsight/modules/payments/`):

- Stripe checkout-session creation (lazy `stripe` SDK import)
  (`providers/stripe.py`, `service.py`; endpoint answers 501).
- Stripe refunds (`providers/stripe.py`).
- Stripe webhook signature verification + event processing, including
  resolving `club_id` during processing (`providers/stripe.py`,
  `service.py`, `models.py`; endpoint answers 501).
- Persist provider checkout sessions on `Payment` rows (`service.py`).
- Increment coupon `redeemed_count` on payment success (`service.py`).
- Payment-required-before-activation enforcement shared with registration
  (`service.py`).

Commerce (`src/playsight/modules/commerce/`):

- Checkout: snapshot the cart into an `Order` and start a payments-provider
  checkout (`service.py`; endpoint answers 501).
- Trigger `payments.service.refund_payment` on order refunds (`service.py`).
- Low-stock alerts (requires the Phase 2 merchandise inventory tables)
  (`service.py`).

Cross-cutting:

- Playbook diagram editor asset pipeline (SVG canvas → storage)
  (playbook README).
- Training: player-visible plan sharing and acknowledgement flow
  (training README).
- Nutrition: athlete data retention/export/delete workflow (PII)
  (nutrition README).
- Platform-wide PII retention/export/delete workflows (CONTRACTS.md §18) —
  stub service methods live in the registration module; generalization is
  Phase 3.

## Related documents

- [CONTRACTS.md](CONTRACTS.md) — binding spec (change it before changing code).
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the delivered platform is built.
- [API.md](API.md) — endpoint reference, including the feature-flagged
  Phase 2/3 scaffold endpoints.
