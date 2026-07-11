"""Auth endpoints: register-club bootstrap, login, refresh rotation, me.

Bootstrap rule (CONTRACTS.md section 6): ``POST /auth/register-club`` is open
only while no clubs exist OR when ``settings.env == "dev"``; otherwise 403.

Refresh-token rotation: every refresh token's ``jti`` is persisted in the
``refresh_tokens`` table. ``POST /auth/refresh`` revokes the presented token
and issues a fresh pair; presenting a revoked/unknown/expired token fails 401.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from playsight.api.audit import write_audit
from playsight.api.deps import get_current_user, get_db
from playsight.api.schemas.auth import (
    ClubRead,
    LoginRequest,
    RefreshRequest,
    RegisterClubRequest,
    RegisterClubResponse,
    TokenResponse,
    UserRead,
)
from playsight.auth.rbac import Role
from playsight.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from playsight.config.settings import get_settings
from playsight.core.errors import AuthError, PermissionDeniedError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.db.models import Club, RefreshToken, User, UserRole

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    """Derive a URL-safe slug from a club name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "club"


def _role_names(db: Session, user: User) -> list[str]:
    """Return the user's role names within their club (fresh from the DB)."""
    rows = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.club_id == user.club_id)
        .all()
    )
    return sorted({row.role for row in rows})


def _issue_tokens(db: Session, user: User, roles: list[str]) -> TokenResponse:
    """Create an access/refresh pair and persist the refresh ``jti``."""
    settings = get_settings()
    access = create_access_token(user.id, user.club_id, roles)
    refresh, jti = create_refresh_token(user.id, user.club_id, roles)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=datetime.now(UTC) + timedelta(days=settings.auth.refresh_ttl_days),
        )
    )
    return TokenResponse(access_token=access, refresh_token=refresh, token_type="bearer")


@router.post("/register-club", response_model=RegisterClubResponse, status_code=201)
def register_club(
    payload: RegisterClubRequest,
    db: Session = Depends(get_db),
) -> RegisterClubResponse:
    """Bootstrap a club with its first admin user and return a token pair."""
    settings = get_settings()
    if db.query(Club).count() > 0 and settings.env != "dev":
        raise PermissionDeniedError(
            "Club bootstrap registration is closed; ask an administrator to invite you."
        )

    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise ValidationFailed(f"Email already registered: {payload.email}")

    slug = payload.slug or _slugify(payload.club_name)
    if db.query(Club).filter(Club.slug == slug).first() is not None:
        raise ValidationFailed(f"Club slug already taken: {slug}")

    club = Club(name=payload.club_name, slug=slug, settings_json={})
    db.add(club)
    db.flush()

    user = User(
        club_id=club.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role=Role.ADMIN.value, club_id=club.id))

    write_audit(
        db,
        club_id=club.id,
        user_id=user.id,
        action="auth.register_club",
        entity_type="club",
        entity_id=club.id,
        after={"name": club.name, "slug": club.slug, "admin_email": user.email},
    )

    tokens = _issue_tokens(db, user, [Role.ADMIN.value])
    db.commit()
    db.refresh(club)
    db.refresh(user)
    log.info("club_registered", club_id=club.id, user_id=user.id)
    return RegisterClubResponse(
        club=ClubRead.model_validate(club),
        user=UserRead.model_validate(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange email + password for an access/refresh token pair."""
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthError("Invalid email or password.")
    if not user.is_active:
        raise AuthError("User account is inactive.")
    tokens = _issue_tokens(db, user, _role_names(db, user))
    db.commit()
    log.info("user_logged_in", user_id=user.id, club_id=user.club_id)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Rotate a refresh token: revoke the presented one, issue a fresh pair."""
    claims = decode_token(payload.refresh_token)
    if claims.type != "refresh":
        raise AuthError("A refresh token is required.")

    row = db.query(RefreshToken).filter(RefreshToken.jti == claims.jti).one_or_none()
    if row is None or row.revoked:
        raise AuthError("Refresh token is no longer valid.")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite returns naive datetimes
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise AuthError("Refresh token has expired.")

    user = db.get(User, claims.sub)
    if user is None or not user.is_active:
        raise AuthError("Unknown or inactive user.")

    row.revoked = True
    tokens = _issue_tokens(db, user, _role_names(db, user))
    db.commit()
    log.info("token_refreshed", user_id=user.id)
    return tokens


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user with their role names."""
    return user
