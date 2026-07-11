"""Email notifier stub.

# TODO(phase2): implement provider-backed email delivery (SMTP / SES / ...)
# with per-club recipient preferences and templated messages.
"""

from __future__ import annotations

from typing import Any

from playsight.config.settings import Settings


class EmailNotifier:
    """Email notification backend (Phase 2 stub, not yet implemented)."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Store settings for the future email transport configuration."""
        self._settings = settings

    def send(self, event_key: str, payload: dict[str, Any]) -> None:
        """Raise: email delivery is not implemented in Phase 1.

        Raises:
            NotImplementedError: Always.
        """
        # TODO(phase2): send a templated email via the configured provider.
        raise NotImplementedError("EmailNotifier is not implemented yet (TODO(phase2)).")
