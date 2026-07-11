"""Payment provider adapters (Phase 3 scaffold).

``base`` defines the :class:`~playsight.modules.payments.providers.base.PaymentProvider`
protocol; ``stripe`` holds the Stripe adapter stub.
"""

from __future__ import annotations

from playsight.core.errors import ValidationFailed
from playsight.modules.payments.providers.base import (
    CheckoutSession,
    PaymentProvider,
    Refund,
    VerifiedWebhook,
)

__all__ = [
    "CheckoutSession",
    "PaymentProvider",
    "Refund",
    "VerifiedWebhook",
    "create_provider",
]


def create_provider(name: str = "stripe") -> PaymentProvider:
    """Return the payment provider adapter registered under ``name``.

    Args:
        name: Provider key; only ``"stripe"`` is supported.

    Raises:
        ValidationFailed: For unknown provider names.
    """
    if name == "stripe":
        # Local import keeps provider modules independent of each other.
        from playsight.modules.payments.providers.stripe import StripeProvider

        return StripeProvider()
    raise ValidationFailed(f"Unknown payment provider: {name!r}.")
