"""Commerce API router (Phase 3 scaffold; CONTRACTS.md sections 10, 12).

All endpoints are guarded by ``require_feature("commerce")``. Shop
configuration writes and fulfillment transitions require the ``shop_manager``
role (``admin`` always passes); cart operations are open to any authenticated
club user.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from playsight.api.deps import TenantContext, get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.core.logging import get_logger
from playsight.db.session import get_db
from playsight.modules.commerce import service
from playsight.modules.commerce.models import Cart, OrderStatus
from playsight.modules.commerce.schemas import (
    CartItemCreate,
    CartItemQuantityUpdate,
    CartRead,
    CheckoutRequest,
    OrderRead,
    OrderStatusUpdate,
    PromotionCreate,
    PromotionRead,
    ShippingConfigCreate,
    ShippingConfigRead,
    TaxConfigCreate,
    TaxConfigRead,
)

log = get_logger(__name__)

router = APIRouter(
    prefix="/commerce",
    tags=["commerce"],
    dependencies=[Depends(require_feature("commerce"))],
)

_PHASE3_TODO = {"todo": "phase3", "docs": "docs/ROADMAP.md"}


def _not_implemented() -> JSONResponse:
    """Return the contracted 501 body for not-yet-implemented Phase 3 flows."""
    return JSONResponse(status_code=501, content=_PHASE3_TODO)


def _cart_response(cart: Cart) -> CartRead:
    """Serialize a cart including its computed subtotal."""
    read = CartRead.model_validate(cart)
    read.subtotal_cents = service.cart_subtotal_cents(cart)
    return read


def _current_user_id(tenant: TenantContext) -> str | None:
    """Extract the acting user's id from the tenant context."""
    return getattr(getattr(tenant, "user", None), "id", None)


@router.get("/cart", response_model=CartRead)
def get_cart(
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> CartRead:
    """Return the caller's active cart, creating one when absent."""
    cart = service.get_or_create_active_cart(db, tenant.club_id, user_id=_current_user_id(tenant))
    return _cart_response(cart)


@router.post("/cart/items", response_model=CartRead, status_code=201)
def add_cart_item(
    payload: CartItemCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> CartRead:
    """Add a line to the caller's active cart (same product merges quantity)."""
    cart = service.get_or_create_active_cart(db, tenant.club_id, user_id=_current_user_id(tenant))
    cart = service.add_cart_item(db, tenant.club_id, cart.id, payload)
    return _cart_response(cart)


@router.patch("/cart/items/{item_id}", response_model=CartRead)
def update_cart_item(
    item_id: str,
    payload: CartItemQuantityUpdate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> CartRead:
    """Set a cart line's quantity (0 removes the line)."""
    cart = service.get_or_create_active_cart(db, tenant.club_id, user_id=_current_user_id(tenant))
    cart = service.update_cart_item_quantity(
        db,
        tenant.club_id,
        cart.id,
        item_id,
        payload.quantity,
    )
    return _cart_response(cart)


@router.delete("/cart/items/{item_id}", response_model=CartRead)
def remove_cart_item(
    item_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> CartRead:
    """Remove a line from the caller's active cart."""
    cart = service.get_or_create_active_cart(db, tenant.club_id, user_id=_current_user_id(tenant))
    cart = service.remove_cart_item(db, tenant.club_id, cart.id, item_id)
    return _cart_response(cart)


@router.post("/checkout", response_model=None)
def checkout(
    payload: CheckoutRequest,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Convert the active cart into an order + payment. Stub: 501 until Phase 3."""
    user_id = _current_user_id(tenant)
    cart = service.get_or_create_active_cart(db, tenant.club_id, user_id=user_id)
    try:
        service.checkout(
            db,
            tenant.club_id,
            cart.id,
            user_id=user_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            shipping_address=payload.shipping_address,
            promotion_code=payload.promotion_code,
        )
    except NotImplementedError:
        log.info("commerce_checkout_stub", cart_id=cart.id, club_id=tenant.club_id)
        return _not_implemented()
    return _not_implemented()  # pragma: no cover - unreachable until phase3


@router.get("/orders", response_model=list[OrderRead])
def list_orders(
    status: OrderStatus | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's orders with an optional status filter."""
    return service.list_orders(db, tenant.club_id, status=status)


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(
    order_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Fetch one order (404 outside the caller's club)."""
    return service.get_order(db, tenant.club_id, order_id)


@router.post("/orders/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    shop_manager: Any = Depends(require_roles(Role.SHOP_MANAGER)),
) -> Any:
    """Apply a fulfillment transition (shop_manager/admin only)."""
    return service.update_order_status(
        db,
        tenant.club_id,
        order_id,
        payload.status,
        acting_user_id=getattr(shop_manager, "id", None),
    )


@router.get("/shipping-configs", response_model=list[ShippingConfigRead])
def list_shipping_configs(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's shipping configurations."""
    return service.list_shipping_configs(db, tenant.club_id, include_inactive=include_inactive)


@router.post("/shipping-configs", response_model=ShippingConfigRead, status_code=201)
def create_shipping_config(
    payload: ShippingConfigCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _shop: Any = Depends(require_roles(Role.SHOP_MANAGER)),
) -> Any:
    """Create a shipping configuration (shop_manager/admin only)."""
    return service.create_shipping_config(db, tenant.club_id, payload)


@router.get("/tax-configs", response_model=list[TaxConfigRead])
def list_tax_configs(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's tax configurations."""
    return service.list_tax_configs(db, tenant.club_id, include_inactive=include_inactive)


@router.post("/tax-configs", response_model=TaxConfigRead, status_code=201)
def create_tax_config(
    payload: TaxConfigCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _shop: Any = Depends(require_roles(Role.SHOP_MANAGER)),
) -> Any:
    """Create a tax configuration (shop_manager/admin only)."""
    return service.create_tax_config(db, tenant.club_id, payload)


@router.get("/promotions", response_model=list[PromotionRead])
def list_promotions(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _shop: Any = Depends(require_roles(Role.SHOP_MANAGER)),
) -> Any:
    """List the club's promotions (shop_manager/admin only)."""
    return service.list_promotions(db, tenant.club_id, include_inactive=include_inactive)


@router.post("/promotions", response_model=PromotionRead, status_code=201)
def create_promotion(
    payload: PromotionCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _shop: Any = Depends(require_roles(Role.SHOP_MANAGER)),
) -> Any:
    """Create a promotion (shop_manager/admin only)."""
    return service.create_promotion(db, tenant.club_id, payload)
