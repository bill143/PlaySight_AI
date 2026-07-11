# Payments module (Phase 3 scaffold)

Feature flag: `payments` (default **off**; per-club override via `club_modules`).
Disabled requests return HTTP 403 with code `feature_disabled`.

Money is integer cents (`amount_cents`) with an ISO-4217 `currency` code.
PlaySight never touches raw card data — checkout is provider-hosted (Stripe).

## Tables

| Table | Purpose |
|---|---|
| `fee_rules` | Fees scoped by role / age group / team / season, with installments |
| `coupons` | Discount codes (percent and/or fixed amount), unique per club |
| `invoices` | Amounts owed (soft-references `registrations.id`, no FK) |
| `payments` | Provider payment attempts (`idempotency_key` unique, provider `stripe`) |
| `webhook_events` | Raw provider webhooks, deduplicated on `provider_event_id` |

All tables carry `club_id` tenancy except `webhook_events` where it is nullable
(webhooks arrive unauthenticated; the club is resolved during processing).

## Provider abstraction

- `providers/base.py` — `PaymentProvider` protocol: `create_checkout_session`,
  `refund`, `verify_webhook`, plus `CheckoutSession` / `Refund` / `VerifiedWebhook`
  dataclasses.
- `providers/stripe.py` — `StripeProvider` stub. All methods raise
  `NotImplementedError` with `# TODO(phase3)`. Environment variables:
  - `PLAYSIGHT_STRIPE_API_KEY` — secret API key (`sk_...`)
  - `PLAYSIGHT_STRIPE_WEBHOOK_SECRET` — webhook signing secret (`whsec_...`)
  - `PLAYSIGHT_STRIPE_PUBLISHABLE_KEY` — publishable key for client-side flows
- `providers/__init__.py` — `create_provider("stripe")` factory.

## Endpoints (prefix `/api/v1/payments`)

| Method & path | Status | Roles |
|---|---|---|
| `GET /fee-rules` | implemented | any authenticated |
| `POST /fee-rules` | implemented | finance_admin (admin passes) |
| `GET /coupons` | implemented | finance_admin |
| `POST /coupons` | implemented | finance_admin |
| `POST /coupons/preview` | implemented | any authenticated |
| `GET /invoices`, `GET /invoices/{id}` | implemented | any authenticated |
| `POST /invoices` | implemented | finance_admin |
| `GET /payments` | implemented | finance_admin |
| `POST /checkout-session` | **501 stub** (idempotent replay implemented) | any authenticated |
| `POST /webhooks/stripe` | **501 stub** | none (signature-verified in Phase 3) |

`POST /checkout-session` honors an optional `Idempotency-Key` header: a replayed
key returns the existing payment record instead of re-charging.

## Implemented service logic

- Fee-rule resolution by specificity (`service.resolve_fee_rule`): the matching
  rule with the most non-null scope columns wins; deterministic tie-breaks.
- Coupon preview (`service.preview_coupon`): active/window/redemption checks,
  percent-then-amount discount, clamped to the amount.

## TODO(phase3)

These items must also be mirrored in `docs/ROADMAP.md`:

- Stripe checkout session creation, refunds, and webhook signature verification
  (`providers/stripe.py`).
- Webhook processing pipeline: dedupe, persist, resolve club/payment, and
  transition Payment/Invoice status (`service.handle_webhook_event`).
- Payment-required-before-activation rule
  (`service.assert_paid_before_activation`), called by the registration module
  on approval.
- Coupon redemption counting on payment success; installment scheduling.
