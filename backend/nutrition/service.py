"""Stub service for nutrition tracking in Milestone M8 (Phase 3).

This module defines the future interface for player nutrition tracking,
including meal logging and summary retrieval. It is currently a stub and
awaits full Phase 3 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class NutritionService:
    """Service interface stub for nutrition operations."""

    def log_meal(self, player_id: str, meal: dict[str, Any]) -> dict[str, Any]:
        """Log a player's meal. Stub for Phase 3 (M8)."""
        if not feature_flags.is_enabled("ENABLE_NUTRITION"):
            raise FeatureDisabledError(
                "Nutrition tracking is disabled. Enable ENABLE_NUTRITION to use "
                "this feature."
            )
        raise NotImplementedError(
            "NutritionService.log_meal is planned for Phase 3 "
            "(M8 Nutrition Tracking)."
        )

    def get_nutrition_summary(
        self, player_id: str, date_range: tuple[str, str]
    ) -> dict[str, Any]:
        """Fetch a player's nutrition summary. Stub for Phase 3 (M8)."""
        if not feature_flags.is_enabled("ENABLE_NUTRITION"):
            raise FeatureDisabledError(
                "Nutrition tracking is disabled. Enable ENABLE_NUTRITION to use "
                "this feature."
            )
        raise NotImplementedError(
            "NutritionService.get_nutrition_summary is planned for Phase 3 "
            "(M8 Nutrition Tracking)."
        )
