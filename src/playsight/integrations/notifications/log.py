"""Structured-log notifier: the Phase 1 (MVP) notification backend."""

from __future__ import annotations

from typing import Any

from playsight.core.logging import get_logger

log = get_logger(__name__)


class LogNotifier:
    """Notifier that emits each event as a structured log line."""

    def send(self, event_key: str, payload: dict[str, Any]) -> None:
        """Log the notification event and payload via structlog."""
        log.info("notification", event_key=event_key, payload=payload)
