"""Pydantic v2 schemas for the merchandise module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    """Payload to create a product category."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CategoryRead(BaseModel):
    """A product category."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime


class VariantCreate(BaseModel):
    """Payload to create a size/color variant with SKU and inventory."""

    sku: str = Field(min_length=1, max_length=64)
    size: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=32)
    price_cents: int | None = Field(default=None, ge=0)
    inventory_qty: int = Field(default=0, ge=0)
    active: bool = True


class VariantUpdate(BaseModel):
    """Partial update of a variant (PATCH semantics)."""

    sku: str | None = Field(default=None, min_length=1, max_length=64)
    size: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=32)
    price_cents: int | None = Field(default=None, ge=0)
    inventory_qty: int | None = Field(default=None, ge=0)
    active: bool | None = None


class VariantRead(BaseModel):
    """A product variant."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    product_id: str
    sku: str
    size: str | None
    color: str | None
    price_cents: int | None
    inventory_qty: int
    active: bool


class ProductCreate(BaseModel):
    """Payload to create a product, optionally with initial variants."""

    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    base_price_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    category_id: str | None = None
    image_storage_key: str | None = None
    active: bool = True
    variants: list[VariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Partial update of a product (PATCH semantics)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    base_price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: str | None = None
    image_storage_key: str | None = None
    active: bool | None = None


class ProductRead(BaseModel):
    """A product with its variants."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    category_id: str | None
    name: str
    slug: str
    description: str
    base_price_cents: int
    currency: str
    active: bool
    image_storage_key: str | None
    external_ref: str | None
    created_at: datetime
    updated_at: datetime
    variants: list[VariantRead]


class InventoryAdjust(BaseModel):
    """Signed inventory adjustment for one variant."""

    delta: int
