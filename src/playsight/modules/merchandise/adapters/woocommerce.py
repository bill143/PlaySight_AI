"""WooCommerce storefront adapter (protocol stub).

# TODO(phase2): implement against the WooCommerce REST API (v3) using per-club
# consumer key/secret from the source config (never in code), with
# tenacity-based retry/backoff.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playsight.modules.merchandise.adapters.base import (
    ExternalProduct,
    register_adapter,
)


class WooCommerceAdapter:
    """WooCommerce REST adapter stub; every call raises ``NotImplementedError``."""

    key = "woocommerce"

    def fetch_products(self, config: Mapping[str, Any]) -> list[ExternalProduct]:
        """Fetch the WooCommerce catalog. Not implemented in the Phase 2 scaffold."""
        raise NotImplementedError(
            "TODO(phase2): WooCommerce catalog import is not implemented yet "
            "(see docs/ROADMAP.md)."
        )

    def push_inventory(self, config: Mapping[str, Any], sku: str, quantity: int) -> None:
        """Push inventory to WooCommerce. Not implemented in the Phase 2 scaffold."""
        raise NotImplementedError(
            "TODO(phase2): WooCommerce inventory push is not implemented yet "
            "(see docs/ROADMAP.md)."
        )


register_adapter(WooCommerceAdapter())
