"""Stub service for tactical playbooks in Milestone M7 (Phase 2).

This module defines the future interface for tactical playbook authoring,
including creating playbooks, adding plays, and listing playbooks. It is
currently a stub and awaits full Phase 2 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class PlaybookService:
    """Service interface stub for playbook operations."""

    def create_playbook(self, team_id: str, name: str) -> dict[str, Any]:
        """Create a tactical playbook. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_PLAYBOOK"):
            raise FeatureDisabledError(
                "Playbook authoring is disabled. Enable ENABLE_PLAYBOOK to use "
                "this feature."
            )
        raise NotImplementedError(
            "PlaybookService.create_playbook is planned for Phase 2 "
            "(M7 Tactical Playbooks)."
        )

    def add_play(self, playbook_id: str, play: dict[str, Any]) -> dict[str, Any]:
        """Add a play to a playbook. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_PLAYBOOK"):
            raise FeatureDisabledError(
                "Playbook authoring is disabled. Enable ENABLE_PLAYBOOK to use "
                "this feature."
            )
        raise NotImplementedError(
            "PlaybookService.add_play is planned for Phase 2 "
            "(M7 Tactical Playbooks)."
        )

    def list_playbooks(self, team_id: str) -> list[dict[str, Any]]:
        """List playbooks for a team. Stub for Phase 2 (M7)."""
        if not feature_flags.is_enabled("ENABLE_PLAYBOOK"):
            raise FeatureDisabledError(
                "Playbook authoring is disabled. Enable ENABLE_PLAYBOOK to use "
                "this feature."
            )
        raise NotImplementedError(
            "PlaybookService.list_playbooks is planned for Phase 2 "
            "(M7 Tactical Playbooks)."
        )
