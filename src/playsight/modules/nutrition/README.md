# Nutrition module (Phase 2 scaffold)

Feature flag: `nutrition` (default **off**; per-club override via `club_modules`).
API prefix: `/api/v1/nutrition` (mounted by `playsight.api`).

## Not medical advice

Per CONTRACTS.md §18, **every** response schema of this module carries a
`disclaimer` field set to `NOT_MEDICAL_ADVICE_DISCLAIMER`
(`playsight.modules.nutrition.schemas`). Nothing in this module is medical,
dietetic, or health advice; it is general club-operations guidance only.

## Scope

- `athlete_profiles` — one per player per club; `units` preference
  (`metric|imperial`), optional height/weight, free-form dietary flags.
  Profile data is athlete-sensitive: reads and writes are restricted to
  `admin|coach`.
- `meal_templates` — reusable templates keyed by `day_type`
  (`training|recovery`) with a `macros_json` target
  (`{"kcal", "protein_g", "carbs_g", "fat_g"}`).
- `hydration_reminders` — "HH:MM" first reminder plus optional repeat
  interval; club-wide or per player.

## Implemented

- Full CRUD for profiles (incl. PATCH), meal templates, and reminders;
  club-scoped with 404 on cross-club access; player references validated.

## Stubs (raise `NotImplementedError`)

- `NutritionService.recommend_macro_targets(club_id, player_id)` — will derive
  targets from the profile and training/match load. Exposed as
  `GET /players/{id}/macro-targets`, currently 501 `{"todo": "phase2"}` (the
  501 body carries the disclaimer too).

## Endpoints

- `GET|POST /templates`, `GET|DELETE /templates/{id}`
- `GET|POST /profiles`, `GET|PATCH|DELETE /profiles/{id}` (admin|coach only)
- `GET|POST /reminders`, `PATCH|DELETE /reminders/{id}`
- `GET /players/{id}/macro-targets` — 501 until Phase 2

Writes require role `admin` or `coach`.

## Extension points

- `recommend_macro_targets` is the single hook for recommendation logic.
- Reminder delivery: integrate with `playsight.integrations.notifications`
  once push/email notifiers land.

## TODO

- `TODO(phase2)`: macro-target recommendations (profile + load; disclaimer
  always attached).
- `TODO(phase2)`: reminder delivery via the notifications integration.
- `TODO(phase3)`: athlete data retention/export/delete workflow (PII).
