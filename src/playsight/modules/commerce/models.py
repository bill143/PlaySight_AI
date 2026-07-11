"""Commerce module tables (Phase 3 scaffold; CONTRACTS.md sections 5, 10, 18).

Money is stored as integer cents with an ISO-4217 currency code. Products live
in the merchandise module (Phase 2); cart/order lines keep a soft
``product_ref`` string plus a name/price snapshot so orders stay immutable when
the catalog changes. Every table carries the tenancy column ``club_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from playsight.core.ids import new_id
from playsight.db.base import Base


def utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class CartStatus(StrEnum):
    """Cart lifecycle states."""

    ACTIVE = "active"
    CHECKED_OUT = "checked_out"
    ABANDONED = "abandoned"


class OrderStatus(StrEnum):
    """Order lifecycle states."""

    PLACED = "placed"
    PAID = "paid"
    PACKED = "packed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Cart(Base):
    """A shopping cart; one ``active`` cart per user at a time."""

    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True, index=True
    )
    # active | checked_out | abandoned (CartStatus)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CartStatus.ACTIVE.value, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    """A line in a cart, snapshotting the product name and unit price."""

    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    cart_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("carts.id"), nullable=False, index=True
    )
    # Soft reference to a merchandise product/SKU (Phase 2 module; no FK).
    product_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    cart: Mapped[Cart] = relationship(back_populates="items")


class Order(Base):
    """A placed order with an immutable price breakdown."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True, index=True
    )
    cart_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("carts.id"), nullable=True)
    # placed | paid | packed | shipped | cancelled | refunded (OrderStatus)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OrderStatus.PLACED.value, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promotion_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("promotions.id"), nullable=True
    )
    # Soft reference to payments.payments.id (no FK: modules enabled independently).
    payment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Shipping/contact details - PII, handle with care (CONTRACTS.md section 18).
    shipping_address_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    """A line in an order, snapshotting the product name and unit price."""

    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("orders.id"), nullable=False, index=True
    )
    product_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    order: Mapped[Order] = relationship(back_populates="items")


class ShippingConfig(Base):
    """Flat-rate shipping configuration with an optional free-shipping threshold."""

    __tablename__ = "shipping_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    flat_rate_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Orders at/above this subtotal ship free (None disables the threshold).
    free_over_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # List of region codes this config applies to (empty = everywhere).
    regions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class TaxConfig(Base):
    """A tax rate in basis points, optionally scoped to a region."""

    __tablename__ = "tax_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Basis points: 825 = 8.25%.
    rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # True when listed prices already include this tax.
    inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Promotion(Base):
    """A shop promotion code (percent and/or fixed amount off), unique per club."""

    __tablename__ = "promotions"
    __table_args__ = (UniqueConstraint("club_id", "code", name="uq_promotions_club_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    percent_off: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..100
    amount_off_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
