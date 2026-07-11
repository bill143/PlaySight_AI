"""Pydantic v2 schemas for the payments module (Phase 3 scaffold)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.payments.models import InvoiceStatus, PaymentProviderName, PaymentStatus


class FeeRuleCreate(BaseModel):
    """Payload to create a fee rule (None scope fields mean "applies to all")."""

    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=32)
    age_group: str | None = Field(default=None, max_length=64)
    team_id: str | None = None
    season: str | None = Field(default=None, max_length=64)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    max_installments: int = Field(default=1, ge=1)
    active: bool = True


class FeeRuleRead(BaseModel):
    """A fee rule as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    role: str | None
    age_group: str | None
    team_id: str | None
    season: str | None
    amount_cents: int
    currency: str
    max_installments: int
    active: bool
    created_at: datetime


class CouponCreate(BaseModel):
    """Payload to create a coupon (percent and/or fixed amount off)."""

    code: str = Field(min_length=1, max_length=64)
    description: str | None = None
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off_cents: int | None = Field(default=None, ge=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    active: bool = True


class CouponRead(BaseModel):
    """A coupon as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    code: str
    description: str | None
    percent_off: int | None
    amount_off_cents: int | None
    currency: str
    valid_from: datetime | None
    valid_until: datetime | None
    max_redemptions: int | None
    redeemed_count: int
    active: bool
    created_at: datetime


class CouponPreviewRequest(BaseModel):
    """Payload to preview a coupon against an amount."""

    code: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(ge=0)


class CouponPreviewResponse(BaseModel):
    """Discount preview for a coupon applied to an amount."""

    code: str
    amount_cents: int
    discount_cents: int
    discounted_cents: int


class InvoiceCreate(BaseModel):
    """Payload to create an invoice."""

    user_id: str | None = None
    registration_id: str | None = None
    fee_rule_id: str | None = None
    coupon_id: str | None = None
    description: str = Field(default="", max_length=512)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    installments: int = Field(default=1, ge=1)
    due_at: datetime | None = None
    meta_json: dict[str, Any] = Field(default_factory=dict)


class InvoiceRead(BaseModel):
    """An invoice as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    user_id: str | None
    registration_id: str | None
    fee_rule_id: str | None
    coupon_id: str | None
    description: str
    amount_cents: int
    currency: str
    status: InvoiceStatus
    installments: int
    due_at: datetime | None
    meta_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PaymentRead(BaseModel):
    """A payment as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    invoice_id: str | None
    provider: PaymentProviderName
    provider_ref: str | None
    amount_cents: int
    currency: str
    status: PaymentStatus
    idempotency_key: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class CheckoutSessionCreate(BaseModel):
    """Payload to start a provider-hosted checkout for an invoice."""

    invoice_id: str
    success_url: str = Field(min_length=1, max_length=2048)
    cancel_url: str = Field(min_length=1, max_length=2048)
    provider: PaymentProviderName = PaymentProviderName.STRIPE
