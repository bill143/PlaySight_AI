"""Payments services (Phase 3 scaffold).

Implemented: fee rule / coupon / invoice CRUD, fee-rule resolution by
specificity, coupon discount previews, payment reads, and idempotent replay of
checkout requests.

Stubbed with ``NotImplementedError`` + ``# TODO(phase3)``: provider checkout
session creation, refunds, webhook verification/processing, and the
payment-required-before-activation rule.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.modules.payments.models import (
    Coupon,
    FeeRule,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    WebhookEvent,
)
from playsight.modules.payments.providers import create_provider
from playsight.modules.payments.providers.base import PaymentProvider
from playsight.modules.payments.schemas import CouponCreate, FeeRuleCreate, InvoiceCreate

log = get_logger(__name__)


def _as_utc(dt: datetime) -> datetime:
    """Return ``dt`` as timezone-aware UTC (SQLite returns naive datetimes)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


# --------------------------------------------------------------------------- fee rules


def create_fee_rule(db: Session, club_id: str, data: FeeRuleCreate) -> FeeRule:
    """Create a fee rule scoped by role / age group / team / season."""
    rule = FeeRule(
        club_id=club_id,
        name=data.name,
        role=data.role,
        age_group=data.age_group,
        team_id=data.team_id,
        season=data.season,
        amount_cents=data.amount_cents,
        currency=data.currency.upper(),
        max_installments=data.max_installments,
        active=data.active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log.info("fee_rule_created", fee_rule_id=rule.id, club_id=club_id)
    return rule


def list_fee_rules(
    db: Session,
    club_id: str,
    *,
    role: str | None = None,
    age_group: str | None = None,
    team_id: str | None = None,
    season: str | None = None,
    include_inactive: bool = False,
) -> list[FeeRule]:
    """List a club's fee rules with optional exact-match filters."""
    stmt = select(FeeRule).where(FeeRule.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(FeeRule.active.is_(True))
    if role is not None:
        stmt = stmt.where(FeeRule.role == role)
    if age_group is not None:
        stmt = stmt.where(FeeRule.age_group == age_group)
    if team_id is not None:
        stmt = stmt.where(FeeRule.team_id == team_id)
    if season is not None:
        stmt = stmt.where(FeeRule.season == season)
    stmt = stmt.order_by(FeeRule.created_at)
    return list(db.execute(stmt).scalars().all())


def get_fee_rule(db: Session, club_id: str, fee_rule_id: str) -> FeeRule:
    """Return one club-scoped fee rule; 404 outside the tenant."""
    rule = db.get(FeeRule, fee_rule_id)
    if rule is None or rule.club_id != club_id:
        raise NotFoundError(f"Fee rule {fee_rule_id} not found.")
    return rule


def resolve_fee_rule(
    db: Session,
    club_id: str,
    *,
    role: str | None = None,
    age_group: str | None = None,
    team_id: str | None = None,
    season: str | None = None,
) -> FeeRule | None:
    """Return the most specific active fee rule matching the given scope.

    A rule matches when each of its non-null scoping columns equals the given
    value; ``None`` columns match anything. Among matches, the rule with the
    most non-null scoping columns wins; ties break on earliest ``created_at``
    then id (deterministic).
    """
    given = {"role": role, "age_group": age_group, "team_id": team_id, "season": season}
    rules = list_fee_rules(db, club_id)
    matches: list[tuple[int, datetime, str, FeeRule]] = []
    for rule in rules:
        scope = {
            "role": rule.role,
            "age_group": rule.age_group,
            "team_id": rule.team_id,
            "season": rule.season,
        }
        if all(value is None or value == given[key] for key, value in scope.items()):
            specificity = sum(1 for value in scope.values() if value is not None)
            matches.append((specificity, _as_utc(rule.created_at), rule.id, rule))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1], item[2]))
    return matches[0][3]


# ------------------------------------------------------------------------------ coupons


def create_coupon(db: Session, club_id: str, data: CouponCreate) -> Coupon:
    """Create a coupon; the code is unique per club (case-preserving)."""
    if data.percent_off is None and data.amount_off_cents is None:
        raise ValidationFailed("A coupon needs percent_off and/or amount_off_cents.")
    code = data.code.strip()
    existing = db.execute(
        select(Coupon).where(Coupon.club_id == club_id, Coupon.code == code)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationFailed(f"Coupon code {code!r} already exists for this club.")
    coupon = Coupon(
        club_id=club_id,
        code=code,
        description=data.description,
        percent_off=data.percent_off,
        amount_off_cents=data.amount_off_cents,
        currency=data.currency.upper(),
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        max_redemptions=data.max_redemptions,
        active=data.active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    log.info("coupon_created", coupon_id=coupon.id, club_id=club_id)
    return coupon


def list_coupons(db: Session, club_id: str, *, include_inactive: bool = False) -> list[Coupon]:
    """List a club's coupons (active only unless ``include_inactive``)."""
    stmt = select(Coupon).where(Coupon.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(Coupon.active.is_(True))
    stmt = stmt.order_by(Coupon.created_at)
    return list(db.execute(stmt).scalars().all())


def get_coupon_by_code(db: Session, club_id: str, code: str) -> Coupon:
    """Return one club-scoped coupon by code; 404 when unknown."""
    coupon = db.execute(
        select(Coupon).where(Coupon.club_id == club_id, Coupon.code == code.strip())
    ).scalar_one_or_none()
    if coupon is None:
        raise NotFoundError(f"Coupon {code!r} not found.")
    return coupon


def preview_coupon(
    db: Session, club_id: str, code: str, amount_cents: int, *, at: datetime | None = None
) -> tuple[Coupon, int]:
    """Validate a coupon and compute the discount for ``amount_cents``.

    Percent discount applies first, then any fixed amount, clamped to the
    amount itself. Redemption counting happens at payment time
    (# TODO(phase3): increment ``redeemed_count`` on payment success).

    Returns:
        The coupon and the discount in cents.

    Raises:
        NotFoundError: Unknown code for this club.
        ValidationFailed: Inactive, outside its validity window, or fully redeemed.
    """
    coupon = get_coupon_by_code(db, club_id, code)
    now = at or datetime.now(UTC)
    if not coupon.active:
        raise ValidationFailed(f"Coupon {coupon.code!r} is inactive.")
    if coupon.valid_from is not None and now < _as_utc(coupon.valid_from):
        raise ValidationFailed(f"Coupon {coupon.code!r} is not valid yet.")
    if coupon.valid_until is not None and now > _as_utc(coupon.valid_until):
        raise ValidationFailed(f"Coupon {coupon.code!r} has expired.")
    if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
        raise ValidationFailed(f"Coupon {coupon.code!r} is fully redeemed.")

    discount = 0
    if coupon.percent_off is not None:
        discount += amount_cents * coupon.percent_off // 100
    if coupon.amount_off_cents is not None:
        discount += coupon.amount_off_cents
    discount = max(0, min(discount, amount_cents))
    return coupon, discount


# ----------------------------------------------------------------------------- invoices


def create_invoice(db: Session, club_id: str, data: InvoiceCreate) -> Invoice:
    """Create an invoice in ``open`` status."""
    if data.fee_rule_id is not None:
        get_fee_rule(db, club_id, data.fee_rule_id)  # 404 outside the tenant
    invoice = Invoice(
        club_id=club_id,
        user_id=data.user_id,
        registration_id=data.registration_id,
        fee_rule_id=data.fee_rule_id,
        coupon_id=data.coupon_id,
        description=data.description,
        amount_cents=data.amount_cents,
        currency=data.currency.upper(),
        status=InvoiceStatus.OPEN.value,
        installments=data.installments,
        due_at=data.due_at,
        meta_json=data.meta_json,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    log.info("invoice_created", invoice_id=invoice.id, club_id=club_id)
    return invoice


def list_invoices(
    db: Session,
    club_id: str,
    *,
    status: InvoiceStatus | str | None = None,
    registration_id: str | None = None,
) -> list[Invoice]:
    """List a club's invoices with optional filters."""
    stmt = select(Invoice).where(Invoice.club_id == club_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == InvoiceStatus(status).value)
    if registration_id is not None:
        stmt = stmt.where(Invoice.registration_id == registration_id)
    stmt = stmt.order_by(Invoice.created_at)
    return list(db.execute(stmt).scalars().all())


def get_invoice(db: Session, club_id: str, invoice_id: str) -> Invoice:
    """Return one club-scoped invoice; 404 outside the tenant."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.club_id != club_id:
        raise NotFoundError(f"Invoice {invoice_id} not found.")
    return invoice


# ----------------------------------------------------------------------------- payments


def list_payments(
    db: Session,
    club_id: str,
    *,
    status: PaymentStatus | str | None = None,
    invoice_id: str | None = None,
) -> list[Payment]:
    """List a club's payments with optional filters."""
    stmt = select(Payment).where(Payment.club_id == club_id)
    if status is not None:
        stmt = stmt.where(Payment.status == PaymentStatus(status).value)
    if invoice_id is not None:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    stmt = stmt.order_by(Payment.created_at)
    return list(db.execute(stmt).scalars().all())


def get_payment(db: Session, club_id: str, payment_id: str) -> Payment:
    """Return one club-scoped payment; 404 outside the tenant."""
    payment = db.get(Payment, payment_id)
    if payment is None or payment.club_id != club_id:
        raise NotFoundError(f"Payment {payment_id} not found.")
    return payment


def create_checkout_session(
    db: Session,
    club_id: str,
    *,
    invoice_id: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str | None = None,
    provider: PaymentProvider | None = None,
) -> Payment:
    """Start a provider-hosted checkout for an invoice. Stub past idempotency.

    Implemented: idempotent replay - when a payment with ``idempotency_key``
    already exists for this club, it is returned unchanged (no re-charge).

    Planned flow (# TODO(phase3)): create a ``pending`` Payment row, call
    ``provider.create_checkout_session`` (Stripe) forwarding the idempotency
    key and metadata, persist ``provider_ref``, and return the payment with
    the redirect URL. The payment transitions on webhook events.
    """
    if idempotency_key:
        existing = db.execute(
            select(Payment).where(
                Payment.club_id == club_id, Payment.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            log.info("checkout_idempotent_replay", payment_id=existing.id, club_id=club_id)
            return existing

    invoice = get_invoice(db, club_id, invoice_id)
    if invoice.status != InvoiceStatus.OPEN.value:
        raise ValidationFailed(f"Invoice {invoice_id} is not open (status={invoice.status!r}).")
    provider = provider or create_provider()
    # The Stripe adapter raises NotImplementedError until Phase 3.
    provider.create_checkout_session(
        amount_cents=invoice.amount_cents,
        currency=invoice.currency,
        description=invoice.description or f"Invoice {invoice.id}",
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=idempotency_key or invoice.id,
        metadata={"invoice_id": invoice.id, "club_id": club_id},
    )
    raise NotImplementedError(
        "TODO(phase3): persist the provider checkout session on a Payment row."
    )  # pragma: no cover - unreachable until the provider stub is implemented


def refund_payment(
    db: Session,
    club_id: str,
    payment_id: str,
    *,
    amount_cents: int | None = None,
    reason: str | None = None,
    provider: PaymentProvider | None = None,
) -> Payment:
    """Refund a succeeded payment through its provider. Stub.

    Planned flow (# TODO(phase3)): validate the payment is ``succeeded``, call
    ``provider.refund`` with ``provider_ref``, update the payment status to
    ``refunded``, and write an ``audit_logs`` row.
    """
    payment = get_payment(db, club_id, payment_id)
    provider = provider or create_provider(payment.provider)
    provider.refund(
        provider_ref=payment.provider_ref or "", amount_cents=amount_cents, reason=reason
    )
    raise NotImplementedError(
        "TODO(phase3): persist refund state transitions."
    )  # pragma: no cover - unreachable until the provider stub is implemented


def handle_webhook_event(
    db: Session,
    *,
    provider_name: str,
    payload: bytes,
    signature: str,
    provider: PaymentProvider | None = None,
) -> WebhookEvent:
    """Verify, deduplicate, persist, and process a provider webhook. Stub.

    Planned flow (# TODO(phase3)): ``provider.verify_webhook`` (reject invalid
    signatures with 401), dedupe on ``provider_event_id`` (return the existing
    row unchanged), persist the ``WebhookEvent``, resolve the club/payment from
    event metadata, and transition Payment/Invoice status accordingly.
    """
    provider = provider or create_provider(provider_name)
    provider.verify_webhook(payload=payload, signature=signature)
    raise NotImplementedError(
        "TODO(phase3): persist and process verified webhook events."
    )  # pragma: no cover - unreachable until the provider stub is implemented


def assert_paid_before_activation(db: Session, club_id: str, registration_id: str) -> None:
    """Enforce the payment-required-before-activation rule. Stub.

    Planned rule (# TODO(phase3)): a registration may only be activated
    (approved registration taking effect: roster placement, member access)
    once every open invoice referencing it is ``paid``. Raises
    ``ValidationFailed`` when unpaid invoices exist. Called by the registration
    module on approval when the ``payments`` feature is enabled.
    """
    raise NotImplementedError(
        "TODO(phase3): payment-required-before-activation enforcement is not implemented yet."
    )
