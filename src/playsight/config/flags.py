"""Feature flags (CONTRACTS.md section 10).

Global defaults come from ``settings.features``; per-club overrides live in the
``club_modules`` table (``module_key`` == flag key). Disabled features raise
``FeatureDisabledError`` which the API maps to HTTP 403 with code
``feature_disabled``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request

from playsight.config.settings import get_settings
from playsight.core.errors import FeatureDisabledError
from playsight.core.logging import get_logger

log = get_logger(__name__)


def is_enabled(key: str, club_id: str | None = None, db: Any = None) -> bool:
    """Return whether the feature ``key`` is enabled.

    Args:
        key: Feature flag key (e.g. ``"video_analytics"``, ``"playbook"``).
        club_id: Optional club id; when given together with ``db``, a row in
            ``club_modules`` for this club overrides the global flag.
        db: Optional SQLAlchemy session used to look up the club override.

    Returns:
        True when the feature is enabled (unknown keys default to False).
    """
    settings = get_settings()
    enabled = bool(settings.features.get(key, False))

    if club_id is not None and db is not None:
        from playsight.db.models import ClubModule  # local import avoids import cycles

        override = (
            db.query(ClubModule)
            .filter(ClubModule.club_id == club_id, ClubModule.module_key == key)
            .one_or_none()
        )
        if override is not None:
            enabled = bool(override.enabled)

    return enabled


def require_feature(key: str) -> Callable[..., None]:
    """Return a FastAPI dependency that rejects requests when ``key`` is disabled.

    Applies the per-club override when the request carries a tenant context
    (``request.state.tenant`` with a ``club_id`` attribute, set by
    ``playsight.api.deps.get_tenant``); otherwise checks the global flag.

    Usage::

        router = APIRouter(dependencies=[Depends(require_feature("playbook"))])
    """
    from playsight.db.session import get_db  # local import avoids import cycles

    def dependency(request: Request, db: Any = Depends(get_db)) -> None:
        tenant = getattr(request.state, "tenant", None)
        club_id = getattr(tenant, "club_id", None)
        if not is_enabled(key, club_id=club_id, db=db):
            log.info("feature_disabled", feature=key, club_id=club_id)
            raise FeatureDisabledError(f"Feature '{key}' is disabled.")

    dependency.__name__ = f"require_feature_{key}"
    return dependency
