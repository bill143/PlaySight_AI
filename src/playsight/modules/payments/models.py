"""Payments module tables (Phase 3 scaffold; CONTRACTS.md sections 5, 10, 18).

Money is stored as integer cents (``amount_cents``) with an ISO-4217 currency
code. Every table carries the tenancy column ``club_id`` except ``webhook_events``
where it is nullable: webhooks arrive unauthenticated and the club is resolved
during processing.  # TODO(phase3): resolve club_id while processing webhooks.
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


class PaymentProviderName(StrEnum):
    """Supported payment providers (Stripe only for now)."""

    STRIPE = "stripe"


class InvoiceStatus(StrEnum):
    """Invoice lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class PaymentStatus(StrEnum):
    """Payment lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class FeeRule(Base):
    """A club fee scoped by role / age group / team / season.

    ``None`` in a scoping column means "applies to all"; the most specific
    matching rule wins (see ``service.resolve_fee_rule``).
    """

    __tablename__ = "fee_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # 1 = pay in full; N > 1 allows splitting into up to N installments.
    max_installments: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Coupon(Base):
    """A discount code (percent and/or fixed amount off), unique per club."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("club_id", "code", name="uq_coupons_club_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    percent_off: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..100
    amount_off_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Invoice(Base):
    """An amount owed to the club (registration fees, shop orders, ...)."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    # Soft reference to registrations.id (no FK: modules can be enabled independently).
    registration_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    fee_rule_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("fee_rules.id"), nullable=True
    )
    coupon_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("coupons.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # draft | open | paid | void (InvoiceStatus)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=InvoiceStatus.OPEN.value, index=True
    )
    installments: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    payments: Mapped[list[Payment]] = relationship(back_populates="invoice")


class Payment(Base):
    """One payment attempt against an invoice via an external provider."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("invoices.id"), nullable=True, index=True
    )
    # stripe (PaymentProviderName)
    provider: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PaymentProviderName.STRIPE.value
    )
    # Provider-side reference (checkout session / payment intent id).
    provider_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # pending | processing | succeeded | failed | refunded | cancelled (PaymentStatus)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PaymentStatus.PENDING.value, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    invoice: Mapped[Invoice | None] = relationship(back_populates="payments")


class WebhookEvent(Base):
    """A raw provider webhook event, deduplicated on ``provider_event_id``."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # Nullable: webhooks arrive unauthenticated; club resolved during processing.
    club_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PaymentProviderName.STRIPE.value
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
