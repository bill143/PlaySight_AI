"""Role-based access control (CONTRACTS.md section 6).

``require_roles(*roles)`` is a FastAPI dependency factory; ``admin`` always
passes. The current user is resolved by ``playsight.api.deps.get_current_user``
(imported lazily to avoid a package cycle).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import Any

from playsight.core.errors import PermissionDeniedError


class Role(StrEnum):
    """Platform roles."""

    ADMIN = "admin"
    COACH = "coach"
    ANALYST = "analyst"
    PLAYER = "player"
    GUARDIAN = "guardian"
    REGISTRAR = "registrar"
    FINANCE_ADMIN = "finance_admin"
    SHOP_MANAGER = "shop_manager"


def extract_roles(subject: Any) -> set[str]:
    """Extract role name strings from a user-like object.

    Supports: a ``TokenPayload`` / any object with ``roles`` as ``list[str]``,
    an ORM ``User`` whose ``roles`` are ``UserRole`` rows (``.role`` attribute),
    a plain dict with a ``"roles"`` key, or a bare iterable of strings.
    """
    if subject is None:
        return set()
    raw = subject.get("roles", []) if isinstance(subject, dict) else subject
    if not isinstance(subject, dict) and hasattr(subject, "roles"):
        raw = subject.roles
    names: set[str] = set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Iterable):
        for item in raw:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, Role):
                names.add(item.value)
            elif hasattr(item, "role"):
                names.add(str(item.role))
    return names


def check_roles(user_roles: Iterable[str], required: Iterable[str]) -> bool:
    """Return True when ``user_roles`` satisfies ``required`` (admin always passes)."""
    have = set(user_roles)
    if Role.ADMIN.value in have:
        return True
    return bool(have.intersection(set(required)))


def require_roles(*roles: str | Role) -> Callable[..., Any]:
    """Return a FastAPI dependency enforcing that the caller holds one of ``roles``.

    ``admin`` always passes. Raises ``PermissionDeniedError`` (HTTP 403) otherwise.
    The dependency resolves the current user through
    ``playsight.api.deps.get_current_user`` and returns it, so routes may write::

        user = Depends(require_roles(Role.COACH, Role.ANALYST))
    """
    required = {r.value if isinstance(r, Role) else str(r) for r in roles}

    # Lazy imports: playsight.api imports playsight.auth, so importing api.deps
    # at module import time would create a cycle.
    from fastapi import Depends

    from playsight.api.deps import get_current_user

    def dependency(user: Any = Depends(get_current_user)) -> Any:
        user_roles = extract_roles(user)
        if not check_roles(user_roles, required):
            raise PermissionDeniedError(f"Requires one of roles: {', '.join(sorted(required))}.")
        return user

    dependency.__name__ = f"require_roles_{'_'.join(sorted(required)) or 'any'}"
    return dependency
