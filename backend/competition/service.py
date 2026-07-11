"""Stub service for competition data integration in Milestone M6 (Phase 2).

This module defines the future interface for league and competition data
integration, including standings, fixtures, and competition metadata syncing.
It is currently a stub and awaits full Phase 2 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class CompetitionService:
    """Service interface stub for competition data operations."""

    def get_standings(self, competition_id: str) -> dict[str, Any]:
        """Fetch league standings for a competition. Stub for Phase 2 (M6)."""
        if not feature_flags.is_enabled("ENABLE_COMPETITION_DATA"):
            raise FeatureDisabledError(
                "Competition data integration is disabled. Enable "
                "ENABLE_COMPETITION_DATA to use this feature."
            )
        raise NotImplementedError(
            "CompetitionService.get_standings is planned for Phase 2 "
            "(M6 Competition Integration)."
        )

    def sync_fixtures(self, competition_id: str) -> list[dict[str, Any]]:
        """Sync fixtures for a competition. Stub for Phase 2 (M6)."""
        if not feature_flags.is_enabled("ENABLE_COMPETITION_DATA"):
            raise FeatureDisabledError(
                "Competition data integration is disabled. Enable "
                "ENABLE_COMPETITION_DATA to use this feature."
            )
        raise NotImplementedError(
            "CompetitionService.sync_fixtures is planned for Phase 2 "
            "(M6 Competition Integration)."
        )

    def get_competition_metadata(self, competition_id: str) -> dict[str, Any]:
        """Fetch competition metadata. Stub for Phase 2 (M6)."""
        if not feature_flags.is_enabled("ENABLE_COMPETITION_DATA"):
            raise FeatureDisabledError(
                "Competition data integration is disabled. Enable "
                "ENABLE_COMPETITION_DATA to use this feature."
            )
        raise NotImplementedError(
            "CompetitionService.get_competition_metadata is planned for Phase 2 "
            "(M6 Competition Integration)."
        )
