"""Merchandise service: implemented catalog CRUD + stubbed analytics/sync."""

from __future__ import annotations

import re
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.modules.merchandise.models import Category, Product, ProductVariant
from playsight.modules.merchandise.schemas import (
    CategoryCreate,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Return a URL-safe slug for ``value`` (lowercase, dash-separated)."""
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-") or "item"


def _apply_updates(entity: object, data: dict) -> None:
    """Assign ``data`` fields onto an ORM entity, unwrapping ``Enum`` values."""
    for field_name, value in data.items():
        setattr(entity, field_name, value.value if isinstance(value, Enum) else value)


class MerchandiseService:
    """Club-scoped catalog CRUD (categories, products, variants, inventory).

    Cross-club access surfaces as ``NotFoundError`` (HTTP 404) per
    CONTRACTS.md section 6. Sales analytics and external storefront sync are
    Phase 2 stubs.
    """

    def __init__(self, db: Session) -> None:
        """Bind the service to an open database session."""
        self.db = db

    # -- categories --------------------------------------------------------

    def create_category(self, club_id: str, payload: CategoryCreate) -> Category:
        """Create a category; slug is derived from the name and must be unique."""
        slug = slugify(payload.name)
        if self._category_by_slug(club_id, slug) is not None:
            raise ValidationFailed(f"A category with slug '{slug}' already exists.")
        category = Category(
            club_id=club_id, name=payload.name, slug=slug, description=payload.description
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def list_categories(self, club_id: str) -> list[Category]:
        """Return the club's categories ordered by name."""
        stmt = select(Category).where(Category.club_id == club_id).order_by(Category.name)
        return list(self.db.scalars(stmt))

    def get_category(self, club_id: str, category_id: str) -> Category:
        """Return one category, raising ``NotFoundError`` outside the club scope."""
        category = self.db.get(Category, category_id)
        if category is None or category.club_id != club_id:
            raise NotFoundError(f"Category {category_id} not found.")
        return category

    def delete_category(self, club_id: str, category_id: str) -> None:
        """Delete a category; products keep existing with ``category_id`` nulled."""
        category = self.get_category(club_id, category_id)
        self.db.execute(
            update(Product)
            .where(Product.club_id == club_id, Product.category_id == category.id)
            .values(category_id=None)
        )
        self.db.delete(category)
        self.db.commit()

    def _category_by_slug(self, club_id: str, slug: str) -> Category | None:
        stmt = select(Category).where(Category.club_id == club_id, Category.slug == slug)
        return self.db.scalars(stmt).first()

    # -- products ----------------------------------------------------------

    def create_product(self, club_id: str, payload: ProductCreate) -> Product:
        """Create a product (optionally with initial variants).

        Raises:
            ValidationFailed: On duplicate product slug or variant SKU, or an
                unknown ``category_id``.
        """
        if payload.category_id is not None:
            self.get_category(club_id, payload.category_id)
        slug = slugify(payload.name)
        if self._product_by_slug(club_id, slug) is not None:
            raise ValidationFailed(f"A product with slug '{slug}' already exists.")
        product = Product(
            club_id=club_id,
            category_id=payload.category_id,
            name=payload.name,
            slug=slug,
            description=payload.description,
            base_price_cents=payload.base_price_cents,
            currency=payload.currency.upper(),
            active=payload.active,
            image_storage_key=payload.image_storage_key,
        )
        self.db.add(product)
        self.db.flush()
        for variant in payload.variants:
            self._build_variant(club_id, product.id, variant)
        self.db.commit()
        self.db.refresh(product)
        return product

    def list_products(
        self,
        club_id: str,
        *,
        category_id: str | None = None,
        active_only: bool = False,
    ) -> list[Product]:
        """Return the club's products, optionally filtered."""
        stmt = select(Product).where(Product.club_id == club_id)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if active_only:
            stmt = stmt.where(Product.active.is_(True))
        stmt = stmt.order_by(Product.name)
        return list(self.db.scalars(stmt))

    def get_product(self, club_id: str, product_id: str) -> Product:
        """Return one product, raising ``NotFoundError`` outside the club scope."""
        product = self.db.get(Product, product_id)
        if product is None or product.club_id != club_id:
            raise NotFoundError(f"Product {product_id} not found.")
        return product

    def update_product(self, club_id: str, product_id: str, payload: ProductUpdate) -> Product:
        """Apply a partial update to a product (slug follows a name change)."""
        product = self.get_product(club_id, product_id)
        data = payload.model_dump(exclude_unset=True)
        if "category_id" in data and data["category_id"] is not None:
            self.get_category(club_id, data["category_id"])
        if "name" in data:
            slug = slugify(data["name"])
            existing = self._product_by_slug(club_id, slug)
            if existing is not None and existing.id != product.id:
                raise ValidationFailed(f"A product with slug '{slug}' already exists.")
            data["slug"] = slug
        if "currency" in data and data["currency"] is not None:
            data["currency"] = data["currency"].upper()
        _apply_updates(product, data)
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete_product(self, club_id: str, product_id: str) -> None:
        """Delete a product and its variants."""
        product = self.get_product(club_id, product_id)
        self.db.delete(product)  # variants cascade via relationship
        self.db.commit()

    def _product_by_slug(self, club_id: str, slug: str) -> Product | None:
        stmt = select(Product).where(Product.club_id == club_id, Product.slug == slug)
        return self.db.scalars(stmt).first()

    # -- variants / inventory ----------------------------------------------

    def add_variant(self, club_id: str, product_id: str, payload: VariantCreate) -> ProductVariant:
        """Add a size/color variant to a product."""
        self.get_product(club_id, product_id)
        variant = self._build_variant(club_id, product_id, payload)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def get_variant(self, club_id: str, variant_id: str) -> ProductVariant:
        """Return one variant, raising ``NotFoundError`` outside the club scope."""
        variant = self.db.get(ProductVariant, variant_id)
        if variant is None or variant.club_id != club_id:
            raise NotFoundError(f"Product variant {variant_id} not found.")
        return variant

    def update_variant(
        self, club_id: str, variant_id: str, payload: VariantUpdate
    ) -> ProductVariant:
        """Apply a partial update to a variant (SKU uniqueness enforced)."""
        variant = self.get_variant(club_id, variant_id)
        data = payload.model_dump(exclude_unset=True)
        new_sku = data.get("sku")
        if new_sku is not None and new_sku != variant.sku:
            self._ensure_sku_free(club_id, new_sku)
        _apply_updates(variant, data)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def delete_variant(self, club_id: str, variant_id: str) -> None:
        """Delete a variant."""
        variant = self.get_variant(club_id, variant_id)
        self.db.delete(variant)
        self.db.commit()

    def adjust_inventory(self, club_id: str, variant_id: str, delta: int) -> ProductVariant:
        """Apply a signed inventory adjustment; the result must stay >= 0.

        Raises:
            ValidationFailed: If the adjustment would drive inventory negative.
        """
        variant = self.get_variant(club_id, variant_id)
        new_qty = variant.inventory_qty + delta
        if new_qty < 0:
            raise ValidationFailed(
                f"Inventory for SKU '{variant.sku}' cannot go below zero "
                f"(current {variant.inventory_qty}, delta {delta})."
            )
        variant.inventory_qty = new_qty
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def _build_variant(
        self, club_id: str, product_id: str, payload: VariantCreate
    ) -> ProductVariant:
        self._ensure_sku_free(club_id, payload.sku)
        variant = ProductVariant(
            club_id=club_id,
            product_id=product_id,
            sku=payload.sku,
            size=payload.size,
            color=payload.color,
            price_cents=payload.price_cents,
            inventory_qty=payload.inventory_qty,
            active=payload.active,
        )
        self.db.add(variant)
        self.db.flush()
        return variant

    def _ensure_sku_free(self, club_id: str, sku: str) -> None:
        stmt = select(ProductVariant).where(
            ProductVariant.club_id == club_id, ProductVariant.sku == sku
        )
        if self.db.scalars(stmt).first() is not None:
            raise ValidationFailed(f"SKU '{sku}' is already in use.")

    # -- Phase 2 stubs -------------------------------------------------------

    def sales_summary(self, club_id: str, *, since_days: int = 30) -> dict:
        """Basic sales analytics (revenue, units, top products).

        # TODO(phase2): aggregate over ``commerce`` order lines once the
        # commerce module lands its order tables; group by product/variant.
        """
        raise NotImplementedError(
            "TODO(phase2): sales analytics requires the commerce order tables "
            "(see docs/ROADMAP.md)."
        )

    def import_external_catalog(self, club_id: str, adapter_key: str, config: dict) -> dict:
        """Import products/variants from an external storefront adapter.

        # TODO(phase2): call ``adapters.get_adapter(adapter_key).fetch_products``
        # and upsert by ``external_ref``/SKU with conflict reporting.
        """
        raise NotImplementedError(
            "TODO(phase2): external catalog import is not implemented yet " "(see docs/ROADMAP.md)."
        )
