"""Auth unit tests: bcrypt round trip, JWT claims/expiry/type, RBAC (section 6)."""

from __future__ import annotations

from types import SimpleNamespace

import jwt as pyjwt
import pytest

from playsight.auth.rbac import Role, check_roles, extract_roles, require_roles
from playsight.auth.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from playsight.config.settings import Settings
from playsight.core.errors import AuthError, PermissionDeniedError


class TestPasswordHashing:
    def test_round_trip(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$2")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_wrong_password_rejected(self) -> None:
        hashed = hash_password("right-password")
        assert verify_password("wrong-password", hashed) is False

    def test_unique_salts(self) -> None:
        assert hash_password("same input") != hash_password("same input")

    def test_malformed_hash_returns_false(self) -> None:
        assert verify_password("anything", "not-a-bcrypt-hash") is False

    def test_long_password_truncated_at_72_bytes(self) -> None:
        long_password = "x" * 200
        hashed = hash_password(long_password)
        assert verify_password("x" * 72, hashed) is True


class TestJwt:
    def test_access_token_claims(self) -> None:
        token = create_access_token("user-1", "club-1", ["admin", "coach"])
        payload = decode_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.sub == "user-1"
        assert payload.club_id == "club-1"
        assert payload.roles == ["admin", "coach"]
        assert payload.type == "access"
        assert len(payload.jti) == 32
        assert payload.exp > payload.iat

    def test_refresh_token_claims_and_jti(self) -> None:
        token, jti = create_refresh_token("user-2", "club-2", ["analyst"])
        payload = decode_token(token)
        assert payload.type == "refresh"
        assert payload.jti == jti
        assert payload.sub == "user-2"

    def test_expired_token_rejected(self) -> None:
        expired = Settings(_env_file=None, auth={"access_ttl_minutes": -5})
        token = create_access_token("user-3", "club-3", [], settings=expired)
        with pytest.raises(AuthError):
            decode_token(token, settings=expired)

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token("user-4", "club-4", [])
        with pytest.raises(AuthError):
            decode_token(token[:-4] + "AAAA")

    def test_wrong_secret_rejected(self) -> None:
        other = Settings(_env_file=None, auth={"secret_key": "a-completely-different-secret"})
        token = create_access_token("user-5", "club-5", [], settings=other)
        with pytest.raises(AuthError):
            decode_token(token)  # default settings use the dev secret

    def test_missing_claims_rejected(self) -> None:
        settings = Settings(_env_file=None)
        bare = pyjwt.encode(
            {"sub": "user-6", "exp": 4102444800, "iat": 0},
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )
        with pytest.raises(AuthError):
            decode_token(bare, settings=settings)  # club_id/roles/type/jti missing


class TestRbac:
    def test_admin_always_passes(self) -> None:
        assert check_roles(["admin"], ["finance_admin"]) is True

    def test_matching_role_passes(self) -> None:
        assert check_roles(["coach", "player"], ["coach"]) is True

    def test_missing_role_denied(self) -> None:
        assert check_roles(["player"], ["coach", "analyst"]) is False

    def test_extract_roles_from_strings_and_orm_rows(self) -> None:
        assert extract_roles(SimpleNamespace(roles=["coach"])) == {"coach"}
        rows = [SimpleNamespace(role="analyst"), SimpleNamespace(role="coach")]
        assert extract_roles(SimpleNamespace(roles=rows)) == {"analyst", "coach"}
        assert extract_roles({"roles": ["guardian"]}) == {"guardian"}
        assert extract_roles(None) == set()

    def test_require_roles_dependency_allows(self) -> None:
        dependency = require_roles(Role.COACH, Role.ANALYST)
        user = SimpleNamespace(roles=["analyst"])
        assert dependency(user) is user

    def test_require_roles_dependency_admin_bypass(self) -> None:
        dependency = require_roles(Role.FINANCE_ADMIN)
        user = SimpleNamespace(roles=["admin"])
        assert dependency(user) is user

    def test_require_roles_dependency_denies(self) -> None:
        dependency = require_roles(Role.COACH)
        with pytest.raises(PermissionDeniedError):
            dependency(SimpleNamespace(roles=["player"]))
