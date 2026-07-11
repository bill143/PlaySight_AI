"""Notifier factory."""

from __future__ import annotations

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import ValidationFailed
from playsight.integrations.notifications.base import Notifier
from playsight.integrations.notifications.email import EmailNotifier
from playsight.integrations.notifications.log import LogNotifier
from playsight.integrations.notifications.push import PushNotifier


def get_notifier(settings: Settings | None = None) -> Notifier:
    """Return the configured notification backend.

    Reads ``settings.notifications_backend`` when the settings object defines
    it (``"log"`` | ``"email"`` | ``"push"``); defaults to the structured-log
    backend, the only Phase 1 implementation. ``email``/``push`` construct but
    raise ``NotImplementedError`` on send until Phase 2.

    Args:
        settings: Optional explicit settings; defaults to the cached
            process-wide settings.

    Raises:
        ValidationFailed: For an unknown backend value.
    """
    settings = settings or get_settings()
    backend = str(getattr(settings, "notifications_backend", "log") or "log").lower()
    if backend == "log":
        return LogNotifier()
    if backend == "email":
        return EmailNotifier(settings)
    if backend == "push":
        return PushNotifier(settings)
    raise ValidationFailed(f"Unknown notifications backend: {backend!r}")
