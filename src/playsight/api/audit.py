"""Audit-log helper for sensitive mutations (CONTRACTS.md sections 5, 18).

Routers call :func:`write_audit` inside the same transaction as the mutation;
the caller commits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from playsight.core.logging import get_logger
from playsight.db.models import AuditLog

log = get_logger(__name__)


def write_audit(
    db: Session,
    *,
    club_id: str,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an ``audit_logs`` row to the session (caller commits).

    Args:
        db: Active database session.
        club_id: Tenant the action happened in.
        user_id: Acting user (None for system actions).
        action: Dotted action key, e.g. ``"match.create"``.
        entity_type: Entity table/kind, e.g. ``"match"``.
        entity_id: Primary key of the affected entity.
        before: Snapshot of relevant fields before the mutation.
        after: Snapshot of relevant fields after the mutation.

    Returns:
        The (uncommitted) AuditLog row.
    """
    entry = AuditLog(
        club_id=club_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
    )
    db.add(entry)
    log.info("audit_logged", action=action, entity_type=entity_type, entity_id=entity_id)
    return entry
