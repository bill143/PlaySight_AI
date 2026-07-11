"""Shared FastAPI dependencies (CONTRACTS.md section 6).

Exports:

- ``get_db`` -- database session (re-exported from ``playsight.db.session``).
- ``get_current_user`` -- validates the bearer access token, loads the user.
- ``get_tenant`` -- builds a :class:`TenantContext`; every core router filters
  its queries by ``tenant.club_id`` (cross-club access answers 404).
- ``require_roles`` -- RBAC dependency factory (re-exported from
  ``playsight.auth.rbac``).
- ``pagination_params`` -- common ``limit``/``offset`` query parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from playsight.auth.rbac import require_roles
from playsight.auth.security import decode_token
from playsight.core.errors import AuthError
from playsight.db.models import User, UserRole
from playsight.db.session import get_db

__all__ = [
    "Pagination",
    "TenantContext",
    "get_current_user",
    "get_db",
    "get_tenant",
    "pagination_params",
    "require_roles",
]

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    """Per-request tenancy context (CONTRACTS.md section 6).

    ``team_ids`` lists the teams the user's roles are explicitly scoped to;
    an empty list means the roles apply club-wide.
    """

    club_id: str
    team_ids: list[str] = field(default_factory=list)
    user: User | None = None
    roles: list[str] = field(default_factory=list)


@dataclass
class Pagination:
    """Validated ``limit``/``offset`` pagination window."""

    limit: int = 50
    offset: int = 0


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header.

    Raises:
        AuthError: Missing/invalid/expired token, wrong token type, unknown or
            inactive user, or token/club mismatch (all -> HTTP 401).
    """
    if credentials is None or not credentials.credentials:
        raise AuthError("Missing bearer token.")
    payload = decode_token(credentials.credentials)
    if payload.type != "access":
        raise AuthError("An access token is required (got a refresh token).")
    user = db.get(User, payload.sub)
    if user is None or not user.is_active:
        raise AuthError("Unknown or inactive user.")
    if user.club_id != payload.club_id:
        raise AuthError("Token does not match the user's club.")
    request.state.user = user
    return user


def get_tenant(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Build the tenancy context for the authenticated user.

    Also stored on ``request.state.tenant`` so downstream dependencies
    (e.g. ``playsight.config.flags.require_feature``) can apply per-club
    feature overrides.
    """
    role_rows = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.club_id == user.club_id)
        .all()
    )
    roles = sorted({row.role for row in role_rows})
    team_ids = sorted({row.team_id for row in role_rows if row.team_id})
    tenant = TenantContext(club_id=user.club_id, team_ids=team_ids, user=user, roles=roles)
    request.state.tenant = tenant
    return tenant


def pagination_params(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum rows to return."),
    offset: int = Query(default=0, ge=0, description="Rows to skip before returning results."),
) -> Pagination:
    """Common pagination query parameters for list endpoints."""
    return Pagination(limit=limit, offset=offset)
