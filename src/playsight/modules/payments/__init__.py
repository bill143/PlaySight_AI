"""Payments module (Phase 3 scaffold, feature flag ``payments``).

Fee rules, coupons, invoices, payments, and webhook events, plus a
``PaymentProvider`` protocol with a Stripe adapter stub.
"""

from playsight.modules.payments import models

__all__ = ["models"]
