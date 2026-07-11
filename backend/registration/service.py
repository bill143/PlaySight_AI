"""Stub service for registration workflows in Milestone M10 (Phase 3).

This module defines the future interface for club and member registration and
membership management, including registration, status retrieval, and renewal.
It is currently a stub and awaits full Phase 3 implementation.
"""

from __future__ import annotations

from typing import Any

from backend.core.exceptions import FeatureDisabledError
from backend.core.feature_flags import feature_flags


class RegistrationService:
    """Service interface stub for registration operations."""

    def register_member(
        self, club_id: str, member_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Register a club member. Stub for Phase 3 (M10)."""
        if not feature_flags.is_enabled("ENABLE_REGISTRATION"):
            raise FeatureDisabledError(
                "Registration workflows are disabled. Enable "
                "ENABLE_REGISTRATION to use this feature."
            )
        raise NotImplementedError(
            "RegistrationService.register_member is planned for Phase 3 "
            "(M10 Registration and Membership)."
        )

    def get_membership_status(self, member_id: str) -> dict[str, Any]:
        """Fetch membership status for a member. Stub for Phase 3 (M10)."""
        if not feature_flags.is_enabled("ENABLE_REGISTRATION"):
            raise FeatureDisabledError(
                "Registration workflows are disabled. Enable "
                "ENABLE_REGISTRATION to use this feature."
            )
        raise NotImplementedError(
            "RegistrationService.get_membership_status is planned for Phase 3 "
            "(M10 Registration and Membership)."
        )

    def renew_membership(self, member_id: str, tier: str) -> dict[str, Any]:
        """Renew a member's membership tier. Stub for Phase 3 (M10)."""
        if not feature_flags.is_enabled("ENABLE_REGISTRATION"):
            raise FeatureDisabledError(
                "Registration workflows are disabled. Enable "
                "ENABLE_REGISTRATION to use this feature."
            )
        raise NotImplementedError(
            "RegistrationService.renew_membership is planned for Phase 3 "
            "(M10 Registration and Membership)."
        )
