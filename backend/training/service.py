"""Stub service for training plans in Milestone M7 (Phase 2).

This module defines the future interface for training plan management,
including creating plans, retrieving plans, and listing team plans. It is
currently a stub and awaits full Phase 2 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class TrainingService:
    """Service interface stub for training plan operations."""

    def create_training_plan(
        self, team_id: str, name: str, sessions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a training plan. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_TRAINING"):
            raise FeatureDisabledError(
                "Training plan management is disabled. Enable ENABLE_TRAINING "
                "to use this feature."
            )
        raise NotImplementedError(
            "TrainingService.create_training_plan is planned for Phase 2 "
            "(M7 Training Plan Management)."
        )

    def get_training_plan(self, plan_id: str) -> dict[str, Any]:
        """Fetch a training plan by ID. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_TRAINING"):
            raise FeatureDisabledError(
                "Training plan management is disabled. Enable ENABLE_TRAINING "
                "to use this feature."
            )
        raise NotImplementedError(
            "TrainingService.get_training_plan is planned for Phase 2 "
            "(M7 Training Plan Management)."
        )

    def list_training_plans(self, team_id: str) -> list[dict[str, Any]]:
        """List training plans for a team. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_TRAINING"):
            raise FeatureDisabledError(
                "Training plan management is disabled. Enable ENABLE_TRAINING "
                "to use this feature."
            )
        raise NotImplementedError(
            "TrainingService.list_training_plans is planned for Phase 2 "
            "(M7 Training Plan Management)."
        )
