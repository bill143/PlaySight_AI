"""Commerce services (Phase 3 scaffold).

Implemented: cart CRUD (get-or-create, add/update/remove/clear lines, subtotal),
order reads, audited order fulfillment transitions, and shipping/tax/promotion
CRUD.

Stubbed with ``NotImplementedError`` + ``# TODO(phase3)``: checkout (wires to
the payments module's ``PaymentProvider`` protocol) and low-stock alerts (uses
the notifications framework once merchandise inventory lands).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.db.models import AuditLog
from playsight.modules.commerce.models import (
    Cart,
    CartItem,
    CartStatus,
    Order,
    OrderStatus,
    Promotion,
    ShippingConfig,
    TaxConfig,
)
from playsight.modules.commerce.schemas import (
    CartItemCreate,
    PromotionCreate,
    ShippingConfigCreate,
    TaxConfigCreate,
)
from playsight.modules.payments.providers.base import PaymentProvider

log = get_logger(__name__)

#: Legal fulfillment transitions (current status -> allowed next statuses).
ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.PLACED.value: frozenset({OrderStatus.PAID.value, OrderStatus.CANCELLED.value}),
    OrderStatus.PAID.value: frozenset({OrderStatus.PACKED.value, OrderStatus.REFUNDED.value}),
    OrderStatus.PACKED.value: frozenset({OrderStatus.SHIPPED.value, OrderStatus.REFUNDED.value}),
    OrderStatus.SHIPPED.value: frozenset({OrderStatus.REFUNDED.value}),
    OrderStatus.CANCELLED.value: frozenset(),
    OrderStatus.REFUNDED.value: frozenset(),
}


# -------------------------------------------------------------------------------- carts


def get_or_create_active_cart(db: Session, club_id: str, *, user_id: str | None = None) -> Cart:
    """Return the user's active cart for this club, creating one when absent."""
    stmt = (
        select(Cart)
        .where(
            Cart.club_id == club_id,
            Cart.user_id == user_id,
            Cart.status == CartStatus.ACTIVE.value,
        )
        .order_by(Cart.created_at)
    )
    cart = db.execute(stmt).scalars().first()
    if cart is not None:
        return cart
    cart = Cart(club_id=club_id, user_id=user_id, status=CartStatus.ACTIVE.value)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    log.info("cart_created", cart_id=cart.id, club_id=club_id, user_id=user_id)
    return cart


def get_cart(db: Session, club_id: str, cart_id: str) -> Cart:
    """Return one club-scoped cart; 404 outside the tenant."""
    cart = db.get(Cart, cart_id)
    if cart is None or cart.club_id != club_id:
        raise NotFoundError(f"Cart {cart_id} not found.")
    return cart


def _get_active_cart(db: Session, club_id: str, cart_id: str) -> Cart:
    """Return a club-scoped cart that is still active (422 otherwise)."""
    cart = get_cart(db, club_id, cart_id)
    if cart.status != CartStatus.ACTIVE.value:
        raise ValidationFailed(f"Cart {cart_id} is not active (status={cart.status!r}).")
    return cart


def add_cart_item(db: Session, club_id: str, cart_id: str, data: CartItemCreate) -> Cart:
    """Add a line to an active cart, merging quantities on the same product."""
    cart = _get_active_cart(db, club_id, cart_id)
    existing = next((i for i in cart.items if i.product_ref == data.product_ref), None)
    if existing is not None:
        existing.quantity += data.quantity
        existing.name = data.name
        existing.unit_price_cents = data.unit_price_cents
    else:
        cart.items.append(
            CartItem(
                club_id=club_id,
                product_ref=data.product_ref,
                name=data.name,
                unit_price_cents=data.unit_price_cents,
                quantity=data.quantity,
                meta_json=data.meta_json,
            )
        )
    db.commit()
    db.refresh(cart)
    log.info("cart_item_added", cart_id=cart.id, club_id=club_id, product_ref=data.product_ref)
    return cart


def update_cart_item_quantity(
    db: Session, club_id: str, cart_id: str, item_id: str, quantity: int
) -> Cart:
    """Set a cart line's quantity; ``0`` removes the line."""
    cart = _get_active_cart(db, club_id, cart_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError(f"Cart item {item_id} not found.")
    if quantity < 0:
        raise ValidationFailed("Quantity must be >= 0.")
    if quantity == 0:
        cart.items.remove(item)
    else:
        item.quantity = quantity
    db.commit()
    db.refresh(cart)
    log.info("cart_item_updated", cart_id=cart.id, item_id=item_id, quantity=quantity)
    return cart


def remove_cart_item(db: Session, club_id: str, cart_id: str, item_id: str) -> Cart:
    """Remove a line from an active cart."""
    return update_cart_item_quantity(db, club_id, cart_id, item_id, 0)


def clear_cart(db: Session, club_id: str, cart_id: str) -> Cart:
    """Remove every line from an active cart."""
    cart = _get_active_cart(db, club_id, cart_id)
    cart.items.clear()
    db.commit()
    db.refresh(cart)
    log.info("cart_cleared", cart_id=cart.id, club_id=club_id)
    return cart


def cart_subtotal_cents(cart: Cart) -> int:
    """Return the cart subtotal in cents (sum of unit price x quantity)."""
    return sum(item.unit_price_cents * item.quantity for item in cart.items)


# ----------------------------------------------------------------------------- checkout


def checkout(
    db: Session,
    club_id: str,
    cart_id: str,
    *,
    user_id: str | None = None,
    success_url: str,
    cancel_url: str,
    shipping_address: dict[str, Any] | None = None,
    promotion_code: str | None = None,
    provider: PaymentProvider | None = None,
) -> Order:
    """Convert an active cart into a placed order and start payment. Stub.

    Planned flow (# TODO(phase3)): snapshot the cart into an ``Order``
    (status ``placed``) with promotion/shipping/tax applied from the active
    configs, create a checkout session through the payments module's
    ``PaymentProvider`` protocol (``create_provider("stripe")``), store the
    resulting payment id on the order, mark the cart ``checked_out``, and
    transition the order to ``paid`` on the payment webhook.
    """
    cart = _get_active_cart(db, club_id, cart_id)
    if not cart.items:
        raise ValidationFailed("Cannot check out an empty cart.")
    raise NotImplementedError(
        "TODO(phase3): commerce checkout wiring to the payments provider protocol "
        "is not implemented yet."
    )


# ------------------------------------------------------------------------------- orders


def list_orders(
    db: Session,
    club_id: str,
    *,
    status: OrderStatus | str | None = None,
    user_id: str | None = None,
) -> list[Order]:
    """List a club's orders with optional filters."""
    stmt = select(Order).where(Order.club_id == club_id)
    if status is not None:
        stmt = stmt.where(Order.status == OrderStatus(status).value)
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    stmt = stmt.order_by(Order.created_at)
    return list(db.execute(stmt).scalars().all())


def get_order(db: Session, club_id: str, order_id: str) -> Order:
    """Return one club-scoped order; 404 outside the tenant."""
    order = db.get(Order, order_id)
    if order is None or order.club_id != club_id:
        raise NotFoundError(f"Order {order_id} not found.")
    return order


def update_order_status(
    db: Session,
    club_id: str,
    order_id: str,
    new_status: OrderStatus | str,
    *,
    acting_user_id: str | None = None,
) -> Order:
    """Apply a fulfillment transition, writing an ``audit_logs`` row.

    Allowed transitions are defined in ``ORDER_TRANSITIONS``. Refund money
    movement itself is a payments-module concern
    (# TODO(phase3): trigger ``payments.service.refund_payment`` on refund).
    """
    try:
        target = OrderStatus(new_status).value
    except ValueError as exc:
        raise ValidationFailed(f"Unknown order status: {new_status!r}.") from exc

    order = get_order(db, club_id, order_id)
    current = order.status
    if target not in ORDER_TRANSITIONS.get(current, frozenset()):
        raise ValidationFailed(f"Illegal order status transition: {current!r} -> {target!r}.")

    order.status = target
    db.add(
        AuditLog(
            club_id=club_id,
            user_id=acting_user_id,
            action="commerce.order_status_change",
            entity_type="order",
            entity_id=order.id,
            before_json={"status": current},
            after_json={"status": target},
        )
    )
    db.commit()
    db.refresh(order)
    log.info(
        "order_status_changed",
        order_id=order.id,
        club_id=club_id,
        from_status=current,
        to_status=target,
        acting_user_id=acting_user_id,
    )
    return order


# ------------------------------------------------------------------------ configuration


def create_shipping_config(
    db: Session,
    club_id: str,
    data: ShippingConfigCreate,
) -> ShippingConfig:
    """Create a shipping configuration."""
    config = ShippingConfig(
        club_id=club_id,
        name=data.name,
        flat_rate_cents=data.flat_rate_cents,
        free_over_cents=data.free_over_cents,
        regions_json=data.regions_json,
        active=data.active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    log.info("shipping_config_created", shipping_config_id=config.id, club_id=club_id)
    return config


def list_shipping_configs(
    db: Session, club_id: str, *, include_inactive: bool = False
) -> list[ShippingConfig]:
    """List a club's shipping configurations."""
    stmt = select(ShippingConfig).where(ShippingConfig.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(ShippingConfig.active.is_(True))
    stmt = stmt.order_by(ShippingConfig.created_at)
    return list(db.execute(stmt).scalars().all())


def create_tax_config(db: Session, club_id: str, data: TaxConfigCreate) -> TaxConfig:
    """Create a tax configuration."""
    config = TaxConfig(
        club_id=club_id,
        name=data.name,
        rate_bps=data.rate_bps,
        region=data.region,
        inclusive=data.inclusive,
        active=data.active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    log.info("tax_config_created", tax_config_id=config.id, club_id=club_id)
    return config


def list_tax_configs(
    db: Session, club_id: str, *, include_inactive: bool = False
) -> list[TaxConfig]:
    """List a club's tax configurations."""
    stmt = select(TaxConfig).where(TaxConfig.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(TaxConfig.active.is_(True))
    stmt = stmt.order_by(TaxConfig.created_at)
    return list(db.execute(stmt).scalars().all())


def create_promotion(db: Session, club_id: str, data: PromotionCreate) -> Promotion:
    """Create a promotion; the code is unique per club."""
    if data.percent_off is None and data.amount_off_cents is None:
        raise ValidationFailed("A promotion needs percent_off and/or amount_off_cents.")
    code = data.code.strip()
    existing = db.execute(
        select(Promotion).where(Promotion.club_id == club_id, Promotion.code == code)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationFailed(f"Promotion code {code!r} already exists for this club.")
    promotion = Promotion(
        club_id=club_id,
        code=code,
        description=data.description,
        percent_off=data.percent_off,
        amount_off_cents=data.amount_off_cents,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        max_redemptions=data.max_redemptions,
        active=data.active,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    log.info("promotion_created", promotion_id=promotion.id, club_id=club_id)
    return promotion


def list_promotions(
    db: Session, club_id: str, *, include_inactive: bool = False
) -> list[Promotion]:
    """List a club's promotions."""
    stmt = select(Promotion).where(Promotion.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(Promotion.active.is_(True))
    stmt = stmt.order_by(Promotion.created_at)
    return list(db.execute(stmt).scalars().all())


# --------------------------------------------------------------------------- inventory


def check_low_stock_and_notify(
    db: Session, club_id: str, *, threshold: int = 5
) -> list[dict[str, Any]]:
    """Scan inventory and alert shop managers about low stock. Stub.

    Planned flow (# TODO(phase3)): read stock levels from the merchandise
    module's inventory tables (Phase 2), collect products at/below
    ``threshold``, and dispatch
    ``playsight.integrations.notifications.notify("commerce.low_stock", payload)``
    for each, returning the alert payloads.
    """
    raise NotImplementedError(
        "TODO(phase3): low-stock alerts need the merchandise inventory tables (Phase 2) "
        "and the notifications framework."
    )
