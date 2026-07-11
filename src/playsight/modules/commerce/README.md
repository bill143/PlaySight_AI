# Commerce module (Phase 3 scaffold)

Feature flag: `commerce` (default **off**; per-club override via `club_modules`).
Disabled requests return HTTP 403 with code `feature_disabled`.

Money is integer cents with an ISO-4217 `currency` code. Products live in the
merchandise module (Phase 2); cart/order lines keep a soft `product_ref` string
plus a name/price snapshot so orders stay immutable when the catalog changes.

## Tables

| Table | Purpose |
|---|---|
| `carts` / `cart_items` | One `active` cart per user; lines snapshot name + unit price |
| `orders` / `order_items` | Immutable price breakdown (subtotal/discount/shipping/tax/total) |
| `shipping_configs` | Flat rate + optional free-shipping threshold, region scoped |
| `tax_configs` | Rate in basis points, optional region, inclusive flag |
| `promotions` | Shop discount codes (percent and/or amount), unique per club |

All tables carry `club_id` tenancy (FK `clubs.id`, indexed). Cross-club access is 404.
`orders.payment_id` soft-references `payments.payments.id` (no FK: modules are
enabled independently). `shipping_address_json` is PII — handle with care.

## Order lifecycle (implemented, audited)

```
placed -> paid | cancelled
paid   -> packed | refunded
packed -> shipped | refunded
shipped -> refunded
```

`service.update_order_status` enforces the map and writes an `audit_logs` row.
Refund money movement itself belongs to the payments module.

## Endpoints (prefix `/api/v1/commerce`)

| Method & path | Status | Roles |
|---|---|---|
| `GET /cart` | implemented (get-or-create active cart) | any authenticated |
| `POST /cart/items` | implemented (merges same `product_ref`) | any authenticated |
| `PATCH /cart/items/{item_id}` | implemented (quantity 0 removes) | any authenticated |
| `DELETE /cart/items/{item_id}` | implemented | any authenticated |
| `POST /checkout` | **501 stub** | any authenticated |
| `GET /orders`, `GET /orders/{id}` | implemented | any authenticated |
| `POST /orders/{id}/status` | implemented | shop_manager (admin passes) |
| `GET/POST /shipping-configs` | implemented | write: shop_manager |
| `GET/POST /tax-configs` | implemented | write: shop_manager |
| `GET/POST /promotions` | implemented | shop_manager |

## TODO(phase3)

These items must also be mirrored in `docs/ROADMAP.md`:

- Checkout (`service.checkout`): snapshot cart into an order, apply
  promotion/shipping/tax, create a payment session through
  `playsight.modules.payments.providers` (`PaymentProvider` protocol), mark the
  cart `checked_out`, and transition the order to `paid` on the payment webhook.
- Low-stock alerts (`service.check_low_stock_and_notify`): read merchandise
  inventory (Phase 2) and dispatch
  `playsight.integrations.notifications.notify("commerce.low_stock", payload)`.
- Trigger `payments.service.refund_payment` on `refunded` transitions.
- Promotion redemption counting at payment time.
