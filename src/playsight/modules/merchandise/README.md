# Merchandise module (Phase 2 scaffold)

Feature flag: `merchandise` (default **off**; per-club override via `club_modules`).
API prefix: `/api/v1/shop` (mounted by `playsight.api`).

## Scope

Club merchandise catalog management: categories, products, and size/color
variants with SKUs and inventory quantities. Prices are integer cents.
Checkout/orders belong to the `commerce` module; this module owns the catalog.

- `merch_categories` — categories, slug unique per club.
- `merch_products` — products, slug unique per club, optional
  `image_storage_key` (object storage) and `external_ref` (storefront id).
- `merch_product_variants` — size/color variants; SKU unique per club;
  `price_cents` overrides `base_price_cents` when set; `inventory_qty` >= 0.

## Implemented

- Catalog CRUD (categories, products incl. nested variant creation, variants).
- Signed inventory adjustments that can never drive stock negative.
- Storefront adapter protocol + registry (`adapters/base.py`).

## Stubs (raise `NotImplementedError`)

- `MerchandiseService.sales_summary` — waits on commerce order tables.
- `MerchandiseService.import_external_catalog` — upsert from storefront.
- `adapters/shopify.py` / `adapters/woocommerce.py` — protocol stubs; keys
  `shopify` / `woocommerce` are registered so config validation works today.

## Endpoints

- `GET|POST /categories`, `DELETE /categories/{id}`
- `GET|POST /products`, `GET|PATCH|DELETE /products/{id}`
- `POST /products/{id}/variants`, `PATCH|DELETE /variants/{id}`
- `POST /variants/{id}/inventory` — body `{"delta": n}`
- `GET /analytics/sales` — 501 `{"todo": "phase2"}` until implemented

Writes require role `admin` or `shop_manager` (analytics also allows
`finance_admin`).

## Extension points

- New storefront adapters: implement `MerchandiseAdapter`, call
  `register_adapter(MyAdapter())` at import time.
- `import_external_catalog` is the single entry point for catalog sync.

## TODO

- `TODO(phase2)`: Shopify Admin GraphQL integration (auth via per-club token).
- `TODO(phase2)`: WooCommerce REST v3 integration.
- `TODO(phase2)`: sales analytics over commerce order lines.
- `TODO(phase2)`: catalog import/upsert by `external_ref`/SKU.
