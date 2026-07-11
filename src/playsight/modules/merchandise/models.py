"""Merchandise module tables (CONTRACTS.md sections 5, 12).

Club-scoped product catalog: categories, products, and size/color variants
with SKUs and inventory quantities. Order/checkout data belongs to the
``commerce`` module; external storefront sync uses the adapter stubs in
``adapters/`` (# TODO(phase2)).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from playsight.core.ids import new_id
from playsight.db.base import Base
from playsight.db.models import utcnow


class Category(Base):
    """A product category (e.g. jerseys, training wear, accessories)."""

    __tablename__ = "merch_categories"
    __table_args__ = (UniqueConstraint("club_id", "slug", name="uq_merch_categories_club_slug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Product(Base):
    """A sellable product; prices are stored in integer cents."""

    __tablename__ = "merch_products"
    __table_args__ = (UniqueConstraint("club_id", "slug", name="uq_merch_products_club_slug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("merch_categories.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    image_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # External storefront reference (Shopify/WooCommerce product id).
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    """A size/color variant of a product, carrying SKU and inventory."""

    __tablename__ = "merch_product_variants"
    __table_args__ = (UniqueConstraint("club_id", "sku", name="uq_merch_variants_club_sku"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("merch_products.id"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Optional price override; falls back to product.base_price_cents when NULL.
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped[Product] = relationship(back_populates="variants")
