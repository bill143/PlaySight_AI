"""Push notifier stub.

# TODO(phase2): implement mobile/web push delivery (FCM / APNs / web push)
# with per-user device registration and per-club opt-in preferences.
"""

from __future__ import annotations

from typing import Any

from playsight.config.settings import Settings


class PushNotifier:
    """Push notification backend (Phase 2 stub, not yet implemented)."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Store settings for the future push transport configuration."""
        self._settings = settings

    def send(self, event_key: str, payload: dict[str, Any]) -> None:
        """Raise: push delivery is not implemented in Phase 1.

        Raises:
            NotImplementedError: Always.
        """
        # TODO(phase2): deliver a push notification via the configured provider.
        raise NotImplementedError("PushNotifier is not implemented yet (TODO(phase2)).")
