"""Stub service for merchandise integration in Milestone M8 (Phase 2).

This module defines the future interface for merchandise store integration,
including product listing, order creation, and order status retrieval. It is
currently a stub and awaits full Phase 2 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class MerchandiseService:
    """Service interface stub for merchandise operations."""

    def list_products(self, club_id: str) -> list[dict[str, Any]]:
        """List merchandise products for a club. Stub for Phase 2 (M8)."""
        if not feature_flags.is_enabled("ENABLE_MERCHANDISE"):
            raise FeatureDisabledError(
                "Merchandise integration is disabled. Enable "
                "ENABLE_MERCHANDISE to use this feature."
            )
        raise NotImplementedError(
            "MerchandiseService.list_products is planned for Phase 2 "
            "(M8 Merchandise Integration)."
        )

    def create_order(
        self, club_id: str, items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a merchandise order. Stub for Phase 2 (M8)."""
        if not feature_flags.is_enabled("ENABLE_MERCHANDISE"):
            raise FeatureDisabledError(
                "Merchandise integration is disabled. Enable "
                "ENABLE_MERCHANDISE to use this feature."
            )
        raise NotImplementedError(
            "MerchandiseService.create_order is planned for Phase 2 "
            "(M8 Merchandise Integration)."
        )

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Fetch merchandise order status. Stub for Phase 2 (M8)."""
        if not feature_flags.is_enabled("ENABLE_MERCHANDISE"):
            raise FeatureDisabledError(
                "Merchandise integration is disabled. Enable "
                "ENABLE_MERCHANDISE to use this feature."
            )
        raise NotImplementedError(
            "MerchandiseService.get_order_status is planned for Phase 2 "
            "(M8 Merchandise Integration)."
        )
