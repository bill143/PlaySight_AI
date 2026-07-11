"""Authentication endpoints: login, token refresh."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.core.exceptions import AuthenticationError
from backend.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from backend.models.user import User
from backend.schemas.user import LoginRequest, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    """Authenticate a user with email/password and issue an access + refresh token pair."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return TokenPair(
        access_token=create_access_token(str(user.id), extra_claims={"role": user.role}),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    raw_user_id = decoded.get("sub")
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

    return TokenPair(
        access_token=create_access_token(str(user.id), extra_claims={"role": user.role}),
        refresh_token=create_refresh_token(str(user.id)),
    )
