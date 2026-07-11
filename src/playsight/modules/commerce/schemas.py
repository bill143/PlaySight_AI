"""Pydantic v2 schemas for the commerce module (Phase 3 scaffold)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.commerce.models import CartStatus, OrderStatus


class CartItemCreate(BaseModel):
    """Payload to add a line to the cart (name/price snapshot the catalog)."""

    product_ref: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    unit_price_cents: int = Field(ge=0)
    quantity: int = Field(default=1, ge=1)
    meta_json: dict[str, Any] = Field(default_factory=dict)


class CartItemQuantityUpdate(BaseModel):
    """Payload to change a cart line's quantity (0 removes the line)."""

    quantity: int = Field(ge=0)


class CartItemRead(BaseModel):
    """A cart line as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_ref: str
    name: str
    unit_price_cents: int
    quantity: int
    meta_json: dict[str, Any]
    created_at: datetime


class CartRead(BaseModel):
    """A cart (with lines and computed subtotal) as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    user_id: str | None
    status: CartStatus
    currency: str
    items: list[CartItemRead] = Field(default_factory=list)
    subtotal_cents: int = 0
    created_at: datetime
    updated_at: datetime


class CheckoutRequest(BaseModel):
    """Payload to convert the active cart into an order + payment session."""

    success_url: str = Field(min_length=1, max_length=2048)
    cancel_url: str = Field(min_length=1, max_length=2048)
    shipping_address: dict[str, Any] = Field(default_factory=dict)
    promotion_code: str | None = Field(default=None, max_length=64)


class OrderItemRead(BaseModel):
    """An order line as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_ref: str
    name: str
    unit_price_cents: int
    quantity: int
    meta_json: dict[str, Any]


class OrderRead(BaseModel):
    """An order as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    user_id: str | None
    cart_id: str | None
    status: OrderStatus
    currency: str
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    promotion_id: str | None
    payment_id: str | None
    items: list[OrderItemRead] = Field(default_factory=list)
    placed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderStatusUpdate(BaseModel):
    """Payload for a fulfillment status transition."""

    status: OrderStatus


class ShippingConfigCreate(BaseModel):
    """Payload to create a shipping configuration."""

    name: str = Field(min_length=1, max_length=255)
    flat_rate_cents: int = Field(default=0, ge=0)
    free_over_cents: int | None = Field(default=None, ge=0)
    regions_json: list[str] = Field(default_factory=list)
    active: bool = True


class ShippingConfigRead(BaseModel):
    """A shipping configuration as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    flat_rate_cents: int
    free_over_cents: int | None
    regions_json: list[str]
    active: bool
    created_at: datetime


class TaxConfigCreate(BaseModel):
    """Payload to create a tax configuration (rate in basis points)."""

    name: str = Field(min_length=1, max_length=255)
    rate_bps: int = Field(default=0, ge=0, le=10000)
    region: str | None = Field(default=None, max_length=64)
    inclusive: bool = False
    active: bool = True


class TaxConfigRead(BaseModel):
    """A tax configuration as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    rate_bps: int
    region: str | None
    inclusive: bool
    active: bool
    created_at: datetime


class PromotionCreate(BaseModel):
    """Payload to create a shop promotion code."""

    code: str = Field(min_length=1, max_length=64)
    description: str | None = None
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off_cents: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    active: bool = True


class PromotionRead(BaseModel):
    """A promotion as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    code: str
    description: str | None
    percent_off: int | None
    amount_off_cents: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    max_redemptions: int | None
    redeemed_count: int
    active: bool
    created_at: datetime
