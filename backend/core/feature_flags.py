"""Feature flag management.

Flags default from `Settings` (env-driven) but can be overridden at runtime
(e.g. via an admin endpoint or Redis) for gradual rollout. Phase 2/3 flags
gate unfinished modules so they can be merged early without being reachable.
"""

from __future__ import annotations

from backend.core.config import settings


class FeatureFlags:
    """Runtime-overridable feature flag registry, seeded from Settings."""

    def __init__(self) -> None:
        self._overrides: dict[str, bool] = {}
        self._defaults: dict[str, bool] = {
            "ENABLE_YOUTUBE_UPLOAD": settings.ENABLE_YOUTUBE_UPLOAD,
            "ENABLE_COMPETITION_DATA": settings.ENABLE_COMPETITION_DATA,
            "ENABLE_MERCHANDISE": settings.ENABLE_MERCHANDISE,
            "ENABLE_PLAYBOOK": settings.ENABLE_PLAYBOOK,
            "ENABLE_TRAINING": settings.ENABLE_TRAINING,
            "ENABLE_NUTRITION": settings.ENABLE_NUTRITION,
            "ENABLE_REGISTRATION": settings.ENABLE_REGISTRATION,
        }

    def is_enabled(self, flag: str) -> bool:
        """Return whether `flag` is enabled, checking overrides first."""
        if flag in self._overrides:
            return self._overrides[flag]
        return self._defaults.get(flag, False)

    def set_override(self, flag: str, enabled: bool) -> None:
        """Set an in-memory override for a flag (does not persist across restarts)."""
        self._overrides[flag] = enabled

    def clear_override(self, flag: str) -> None:
        """Remove an override, reverting to the default value."""
        self._overrides.pop(flag, None)

    def all_flags(self) -> dict[str, bool]:
        """Return the effective value of every known flag."""
        return {name: self.is_enabled(name) for name in self._defaults}


feature_flags = FeatureFlags()

# Static reference of all known flags and the milestone/phase that introduces them.
FEATURE_FLAGS: dict[str, dict[str, str | bool]] = {
    "ENABLE_YOUTUBE_UPLOAD": {"phase": "1", "description": "Publish highlight videos to YouTube"},
    "ENABLE_COMPETITION_DATA": {"phase": "2", "description": "League/competition data integration"},
    "ENABLE_MERCHANDISE": {"phase": "2", "description": "Merchandise store integration"},
    "ENABLE_PLAYBOOK": {"phase": "2", "description": "Tactical playbook authoring"},
    "ENABLE_TRAINING": {"phase": "2", "description": "Training plan management"},
    "ENABLE_NUTRITION": {"phase": "3", "description": "Nutrition tracking for players"},
    "ENABLE_REGISTRATION": {"phase": "3", "description": "Club/member registration workflows"},
}
