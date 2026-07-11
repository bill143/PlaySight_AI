"""Payments API router (Phase 3 scaffold; CONTRACTS.md sections 10, 12).

All endpoints are guarded by ``require_feature("payments")``. Financial writes
require the ``finance_admin`` role (``admin`` always passes). The Stripe
webhook endpoint is unauthenticated by design (signature-verified in Phase 3)
and currently answers 501.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from playsight.api.deps import TenantContext, get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.core.logging import get_logger
from playsight.db.session import get_db
from playsight.modules.payments import service
from playsight.modules.payments.models import InvoiceStatus, PaymentStatus
from playsight.modules.payments.schemas import (
    CheckoutSessionCreate,
    CouponCreate,
    CouponPreviewRequest,
    CouponPreviewResponse,
    CouponRead,
    FeeRuleCreate,
    FeeRuleRead,
    InvoiceCreate,
    InvoiceRead,
    PaymentRead,
)

log = get_logger(__name__)

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(require_feature("payments"))],
)

_PHASE3_TODO = {"todo": "phase3", "docs": "docs/ROADMAP.md"}


def _not_implemented() -> JSONResponse:
    """Return the contracted 501 body for not-yet-implemented Phase 3 flows."""
    return JSONResponse(status_code=501, content=_PHASE3_TODO)


@router.get("/fee-rules", response_model=list[FeeRuleRead])
def list_fee_rules(
    role: str | None = Query(default=None),
    age_group: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    season: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's fee rules with optional scope filters."""
    return service.list_fee_rules(
        db,
        tenant.club_id,
        role=role,
        age_group=age_group,
        team_id=team_id,
        season=season,
        include_inactive=include_inactive,
    )


@router.post("/fee-rules", response_model=FeeRuleRead, status_code=201)
def create_fee_rule(
    payload: FeeRuleCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _finance: Any = Depends(require_roles(Role.FINANCE_ADMIN)),
) -> Any:
    """Create a fee rule (finance_admin/admin only)."""
    return service.create_fee_rule(db, tenant.club_id, payload)


@router.get("/coupons", response_model=list[CouponRead])
def list_coupons(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _finance: Any = Depends(require_roles(Role.FINANCE_ADMIN)),
) -> Any:
    """List the club's coupons (finance_admin/admin only)."""
    return service.list_coupons(db, tenant.club_id, include_inactive=include_inactive)


@router.post("/coupons", response_model=CouponRead, status_code=201)
def create_coupon(
    payload: CouponCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _finance: Any = Depends(require_roles(Role.FINANCE_ADMIN)),
) -> Any:
    """Create a coupon (finance_admin/admin only)."""
    return service.create_coupon(db, tenant.club_id, payload)


@router.post("/coupons/preview", response_model=CouponPreviewResponse)
def preview_coupon(
    payload: CouponPreviewRequest,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Preview the discount a coupon code yields for an amount."""
    coupon, discount = service.preview_coupon(
        db, tenant.club_id, payload.code, payload.amount_cents
    )
    return CouponPreviewResponse(
        code=coupon.code,
        amount_cents=payload.amount_cents,
        discount_cents=discount,
        discounted_cents=payload.amount_cents - discount,
    )


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(
    status: InvoiceStatus | None = Query(default=None),
    registration_id: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's invoices with optional filters."""
    return service.list_invoices(
        db,
        tenant.club_id,
        status=status,
        registration_id=registration_id,
    )


@router.post("/invoices", response_model=InvoiceRead, status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _finance: Any = Depends(require_roles(Role.FINANCE_ADMIN)),
) -> Any:
    """Create an invoice (finance_admin/admin only)."""
    return service.create_invoice(db, tenant.club_id, payload)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Fetch one invoice (404 outside the caller's club)."""
    return service.get_invoice(db, tenant.club_id, invoice_id)


@router.get("/payments", response_model=list[PaymentRead])
def list_payments(
    status: PaymentStatus | None = Query(default=None),
    invoice_id: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _finance: Any = Depends(require_roles(Role.FINANCE_ADMIN)),
) -> Any:
    """List the club's payments (finance_admin/admin only)."""
    return service.list_payments(db, tenant.club_id, status=status, invoice_id=invoice_id)


@router.post("/checkout-session", response_model=None)
def create_checkout_session(
    payload: CheckoutSessionCreate,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Start a provider-hosted checkout for an invoice. Stub: 501 until Phase 3.

    Honors an optional ``Idempotency-Key`` header: a replayed key returns the
    existing payment record instead of re-charging.
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    try:
        payment = service.create_checkout_session(
            db,
            tenant.club_id,
            invoice_id=payload.invoice_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            idempotency_key=idempotency_key,
            provider=None,
        )
    except NotImplementedError:
        log.info("checkout_session_stub", invoice_id=payload.invoice_id, club_id=tenant.club_id)
        return _not_implemented()
    content = PaymentRead.model_validate(payment).model_dump(mode="json")
    return JSONResponse(status_code=200, content=content)


@router.post("/webhooks/stripe", response_model=None)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """Receive a Stripe webhook. Stub: 501 until Phase 3.

    Unauthenticated by design; Phase 3 verifies the ``Stripe-Signature`` header
    against ``PLAYSIGHT_STRIPE_WEBHOOK_SECRET`` before trusting the payload.
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    try:
        service.handle_webhook_event(
            db, provider_name="stripe", payload=payload, signature=signature
        )
    except NotImplementedError:
        log.info("stripe_webhook_stub", payload_bytes=len(payload))
        return _not_implemented()
    return _not_implemented()  # pragma: no cover - unreachable until phase3
