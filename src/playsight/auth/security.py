"""Password hashing (bcrypt) and JWT creation/validation (PyJWT, HS256).

Token claims (CONTRACTS.md section 6): ``sub`` (user_id), ``club_id``,
``roles`` (list[str]), ``type`` (``access`` | ``refresh``), ``jti``,
``exp``, ``iat``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from pydantic import BaseModel

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import AuthError
from playsight.core.ids import new_id

_BCRYPT_MAX_BYTES = 72  # bcrypt only considers the first 72 bytes of input


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str
    club_id: str
    roles: list[str]
    type: str  # "access" | "refresh"
    jti: str
    exp: int
    iat: int


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (random salt).

    Args:
        password: Plaintext password (truncated to bcrypt's 72-byte limit).

    Returns:
        The bcrypt hash as a UTF-8 string, safe to store in ``users.hashed_password``.
    """
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash.

    Returns False (never raises) for malformed hashes or mismatches.
    """
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(raw, hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(
    *,
    user_id: str,
    club_id: str,
    roles: list[str],
    token_type: str,
    ttl: timedelta,
    jti: str,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "club_id": club_id,
        "roles": list(roles),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def create_access_token(
    user_id: str,
    club_id: str,
    roles: list[str],
    settings: Settings | None = None,
) -> str:
    """Create a signed access token (TTL = ``auth.access_ttl_minutes``)."""
    settings = settings or get_settings()
    return _encode(
        user_id=user_id,
        club_id=club_id,
        roles=roles,
        token_type="access",
        ttl=timedelta(minutes=settings.auth.access_ttl_minutes),
        jti=new_id(),
        settings=settings,
    )


def create_refresh_token(
    user_id: str,
    club_id: str,
    roles: list[str],
    settings: Settings | None = None,
) -> tuple[str, str]:
    """Create a signed refresh token (TTL = ``auth.refresh_ttl_days``).

    Returns:
        ``(token, jti)`` - the ``jti`` must be persisted in ``refresh_tokens``
        so the token can be revoked and single-use rotation enforced.
    """
    settings = settings or get_settings()
    jti = new_id()
    token = _encode(
        user_id=user_id,
        club_id=club_id,
        roles=roles,
        token_type="refresh",
        ttl=timedelta(days=settings.auth.refresh_ttl_days),
        jti=jti,
        settings=settings,
    )
    return token, jti


def decode_token(token: str, settings: Settings | None = None) -> TokenPayload:
    """Decode and validate a JWT, returning its claims.

    Raises:
        AuthError: When the token is expired, malformed, has a bad signature,
            or is missing required claims.
    """
    settings = settings or get_settings()
    try:
        data = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid token.") from exc

    try:
        return TokenPayload(**data)
    except Exception as exc:  # pydantic ValidationError -> uniform auth failure
        raise AuthError("Token payload is malformed.") from exc
