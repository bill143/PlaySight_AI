# Registration module (Phase 3 scaffold)

Feature flag: `registration` (default **off**; per-club override via `club_modules`).
Disabled requests return HTTP 403 with code `feature_disabled`.

## Tables

| Table | Purpose |
|---|---|
| `registration_forms` | Club-configurable forms (`fields_json`: list of field definitions) |
| `registrations` | One registrant moving through the approval workflow |
| `registration_documents` | Supporting documents (opaque, PII-free storage keys) |

All tables carry `club_id` tenancy (FK `clubs.id`, indexed). Cross-club access is 404.

`registrations` highlights:

- `registrant_type`: `player | member | official`
- `status`: `draft | submitted | approved | rejected | waitlisted`
- `family_group_id`: groups sibling registrations
- `consent_json`: terms acceptance + guardian consent fields for minors
  (`terms_accepted`, `terms_version`, `accepted_at`, `is_minor`, `guardian_name`,
  `guardian_relationship`, `guardian_accepted`)
- `medical_flags_json`: allergies/conditions/notes (PII — handle with care)

## Workflow (implemented)

```
draft -> submitted -> approved | rejected | waitlisted
                      waitlisted -> approved | rejected
```

`service.transition_status` enforces the transition map, validates consent on
submission (terms accepted; guardian name + acceptance for minors), stamps
`submitted_at` / `decided_at` / `decided_by`, and writes an `audit_logs` row for
every transition.

## Endpoints (prefix `/api/v1/registration`)

| Method & path | Status | Roles |
|---|---|---|
| `GET /forms` | implemented | any authenticated |
| `POST /forms` | implemented | registrar (admin passes) |
| `GET /registrations` | implemented (filters: status, registrant_type, family_group_id) | any authenticated |
| `POST /registrations` | implemented | any authenticated |
| `GET /registrations/{id}` | implemented | any authenticated |
| `POST /registrations/{id}/submit` | implemented | any authenticated |
| `POST /registrations/{id}/status` | implemented | registrar (admin passes) |
| `POST /registrations/{id}/documents` | **501 stub** | any authenticated |

## TODO(phase3)

These items must also be mirrored in `docs/ROADMAP.md`:

- Document upload to object storage (`service.upload_document`) + audit log + scanning.
- PII retention/export/delete workflows (`service.export_registrant_data`,
  `service.delete_registrant_data`) per CONTRACTS.md section 18.
- Enforce payment-required-before-activation on approval via
  `playsight.modules.payments.service.assert_paid_before_activation`.
