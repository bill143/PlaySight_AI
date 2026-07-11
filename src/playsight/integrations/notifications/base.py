"""Notifier protocol and the ``notify`` convenience helper (CONTRACTS.md section 13)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from playsight.core.logging import get_logger

log = get_logger(__name__)


@runtime_checkable
class Notifier(Protocol):
    """Interface implemented by every notification backend."""

    def send(self, event_key: str, payload: dict[str, Any]) -> None:
        """Deliver one notification event.

        Args:
            event_key: Machine-readable event key, e.g. ``"match.processed"``.
            payload: JSON-serializable event payload.
        """
        ...


def notify(db: Session, club_id: str, event_key: str, payload: dict[str, Any]) -> None:
    """Send a club-scoped notification through the configured backend.

    Best effort: delivery failures are logged, never raised, so notification
    problems can never break the calling pipeline, job, or API request.

    Args:
        db: Database session. Reserved for per-club notification preference
            lookups; unused by the Phase 1 log backend.
        club_id: Tenant club id, merged into the payload as ``club_id``.
        event_key: Machine-readable event key, e.g. ``"publish.succeeded"``.
        payload: JSON-serializable event payload.
    """
    # Local import: factory imports Notifier from this module.
    from playsight.integrations.notifications.factory import get_notifier

    _ = db  # Reserved for Phase 2 per-club notification preferences.
    notifier = get_notifier()
    enriched = {**payload, "club_id": club_id}
    try:
        notifier.send(event_key, enriched)
    except NotImplementedError:
        log.warning(
            "notifier_backend_not_implemented",
            event_key=event_key,
            backend=type(notifier).__name__,
        )
    except Exception as exc:
        log.warning("notification_failed", event_key=event_key, error=str(exc))
