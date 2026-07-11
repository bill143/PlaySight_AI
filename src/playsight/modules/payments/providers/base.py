"""Payment provider protocol (Phase 3 scaffold).

Adapters (Stripe today, others later) implement :class:`PaymentProvider`.
Amounts are integer cents; currencies are ISO-4217 codes. Adapters must never
log secrets or full card data — PlaySight never touches raw card numbers, only
provider-hosted checkout flows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class CheckoutSession:
    """A provider-hosted checkout session the payer is redirected to."""

    session_id: str
    url: str
    provider: str
    expires_at: str | None = None  # ISO-8601, provider-dependent


@dataclass
class Refund:
    """The result of a refund request."""

    refund_id: str
    status: str
    amount_cents: int | None = None


@dataclass
class VerifiedWebhook:
    """A webhook event whose signature has been verified."""

    event_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PaymentProvider(Protocol):
    """Interface every payment provider adapter must implement."""

    name: str

    def create_checkout_session(
        self,
        *,
        amount_cents: int,
        currency: str,
        description: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSession:
        """Create a hosted checkout session for the given amount.

        ``idempotency_key`` must be forwarded to the provider so retries never
        double-charge. ``metadata`` carries PlaySight references (invoice id,
        club id) for webhook correlation.
        """
        ...

    def refund(
        self,
        *,
        provider_ref: str,
        amount_cents: int | None = None,
        reason: str | None = None,
    ) -> Refund:
        """Refund a settled payment (full refund when ``amount_cents`` is None)."""
        ...

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedWebhook:
        """Verify a webhook signature and parse the event.

        Raises:
            playsight.core.errors.AuthError: When the signature is invalid.
        """
        ...
