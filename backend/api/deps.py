"""Shared FastAPI dependencies: DB session, current user, RBAC enforcement."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.exceptions import AuthenticationError, AuthorizationError
from backend.core.rbac import Permission, role_has_permission
from backend.core.security import TokenError, decode_token
from backend.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the current authenticated user from a bearer access token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    raw_user_id = payload.get("sub")
    if not raw_user_id:
        raise AuthenticationError("Token missing subject claim")

    try:
        user_id = uuid.UUID(str(raw_user_id))
    except ValueError as exc:
        raise AuthenticationError("Token subject claim is not a valid user id") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: Permission):
    """Build a FastAPI dependency enforcing `permission` for the current user's role."""

    async def _dependency(user: CurrentUser) -> User:
        if not role_has_permission(user.role, permission):
            raise AuthorizationError(f"Role '{user.role}' lacks permission '{permission.value}'")
        return user

    return _dependency
