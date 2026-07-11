"""Stripe payment provider adapter (Phase 3 stub).

Environment variables (read at construction, never logged):

- ``PLAYSIGHT_STRIPE_API_KEY``          - Stripe secret API key (``sk_...``).
- ``PLAYSIGHT_STRIPE_WEBHOOK_SECRET``   - Webhook signing secret (``whsec_...``).
- ``PLAYSIGHT_STRIPE_PUBLISHABLE_KEY``  - Publishable key for client-side flows.

Every operation currently raises ``NotImplementedError``; the planned Phase 3
implementation is documented on each method.  # TODO(phase3)
"""

from __future__ import annotations

import os
from typing import Any

from playsight.core.logging import get_logger
from playsight.modules.payments.providers.base import CheckoutSession, Refund, VerifiedWebhook

log = get_logger(__name__)

ENV_API_KEY = "PLAYSIGHT_STRIPE_API_KEY"
ENV_WEBHOOK_SECRET = "PLAYSIGHT_STRIPE_WEBHOOK_SECRET"
ENV_PUBLISHABLE_KEY = "PLAYSIGHT_STRIPE_PUBLISHABLE_KEY"


class StripeProvider:
    """Stripe implementation of the ``PaymentProvider`` protocol (stub).

    Credentials come from the environment variables documented in the module
    docstring; explicit constructor arguments win (tests). Secrets are stored
    on the instance but never logged.
    """

    name = "stripe"

    def __init__(
        self,
        api_key: str | None = None,
        webhook_secret: str | None = None,
        publishable_key: str | None = None,
    ) -> None:
        """Read credentials from arguments, falling back to the environment."""
        self.api_key = api_key or os.environ.get(ENV_API_KEY)
        self.webhook_secret = webhook_secret or os.environ.get(ENV_WEBHOOK_SECRET)
        self.publishable_key = publishable_key or os.environ.get(ENV_PUBLISHABLE_KEY)

    @property
    def is_configured(self) -> bool:
        """Return whether an API key is available (does not validate it)."""
        return bool(self.api_key)

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
        """Create a Stripe Checkout session. Stub.

        Planned flow (# TODO(phase3)): lazy-import the ``stripe`` SDK, call
        ``stripe.checkout.Session.create`` with a single line item
        (``amount_cents``/``currency``/``description``), ``success_url`` /
        ``cancel_url``, PlaySight ``metadata`` (invoice id, club id), and the
        ``Idempotency-Key`` request header so retries never double-charge.
        Requires ``PLAYSIGHT_STRIPE_API_KEY``.
        """
        raise NotImplementedError(
            "TODO(phase3): Stripe checkout session creation is not implemented yet; "
            f"set {ENV_API_KEY} and implement StripeProvider.create_checkout_session."
        )

    def refund(
        self,
        *,
        provider_ref: str,
        amount_cents: int | None = None,
        reason: str | None = None,
    ) -> Refund:
        """Refund a Stripe payment. Stub.

        Planned flow (# TODO(phase3)): call ``stripe.Refund.create`` with the
        payment intent from ``provider_ref`` (full refund when ``amount_cents``
        is None) and map the result to :class:`Refund`. Requires
        ``PLAYSIGHT_STRIPE_API_KEY``.
        """
        raise NotImplementedError(
            "TODO(phase3): Stripe refunds are not implemented yet; "
            f"set {ENV_API_KEY} and implement StripeProvider.refund."
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedWebhook:
        """Verify a Stripe webhook signature and parse the event. Stub.

        Planned flow (# TODO(phase3)): verify the ``Stripe-Signature`` header
        against ``PLAYSIGHT_STRIPE_WEBHOOK_SECRET`` using
        ``stripe.Webhook.construct_event`` (raise
        ``playsight.core.errors.AuthError`` on an invalid signature) and return
        the event id/type/payload as :class:`VerifiedWebhook`.
        """
        raise NotImplementedError(
            "TODO(phase3): Stripe webhook signature verification is not implemented yet; "
            f"set {ENV_WEBHOOK_SECRET} and implement StripeProvider.verify_webhook."
        )
