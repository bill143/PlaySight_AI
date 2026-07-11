"""Shopify storefront adapter (protocol stub).

# TODO(phase2): implement against the Shopify Admin GraphQL API using a
# per-club access token stored in the source config (never in code), with
# tenacity-based retry/backoff and webhook-driven inventory sync.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playsight.modules.merchandise.adapters.base import (
    ExternalProduct,
    register_adapter,
)


class ShopifyAdapter:
    """Shopify Admin API adapter stub; every call raises ``NotImplementedError``."""

    key = "shopify"

    def fetch_products(self, config: Mapping[str, Any]) -> list[ExternalProduct]:
        """Fetch the Shopify catalog. Not implemented in the Phase 2 scaffold."""
        raise NotImplementedError(
            "TODO(phase2): Shopify catalog import is not implemented yet (see docs/ROADMAP.md)."
        )

    def push_inventory(self, config: Mapping[str, Any], sku: str, quantity: int) -> None:
        """Push inventory to Shopify. Not implemented in the Phase 2 scaffold."""
        raise NotImplementedError(
            "TODO(phase2): Shopify inventory push is not implemented yet (see docs/ROADMAP.md)."
        )


register_adapter(ShopifyAdapter())
