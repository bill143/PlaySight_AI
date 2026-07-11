"""Commerce module (Phase 3 scaffold, feature flag ``commerce``).

Carts, orders, shipping/tax configuration, and promotions for the club shop.
Checkout wires into the payments module's ``PaymentProvider`` protocol.
"""

from playsight.modules.commerce import models

__all__ = ["models"]
