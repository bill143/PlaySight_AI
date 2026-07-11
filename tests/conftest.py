"""Shared pytest fixtures (CONTRACTS.md section 16).

``tests._env`` is imported before the ``playsight`` imports below; it sets the
test environment variables (env=test, tmp SQLite, local storage in a tmp dir,
empty redis URL for eager jobs) so the process-wide cached settings are built
from the test configuration.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import tests._env as _env
from playsight.api.main import create_app
from playsight.auth.security import hash_password
from playsight.config.settings import Settings, get_settings
from playsight.db.base import Base
from playsight.db.models import Club, User, UserRole
from playsight.db.session import SessionLocal, get_engine, init_db, reset_engine
from playsight.modules import import_all_models

API = "/api/v1"

#: Shared plaintext password for every fixture-created user.
TEST_PASSWORD = "S3curePass!word"


@dataclass
class AuthContext:
    """A registered club with a logged-in admin and ready-to-use headers."""

    club_id: str
    user_id: str
    email: str
    password: str
    headers: dict[str, str]


@pytest.fixture(scope="session", autouse=True)
def _test_environment() -> Iterator[None]:
    """Chdir into the tmp workdir and create the full schema once per session.

    The engine is a session-scoped SQLite tmp file (see ``tests._env``); it is
    disposed at the end of the session so Windows can delete the file.
    """
    original_cwd = Path.cwd()
    os.chdir(_env.WORK_DIR)
    reset_engine()
    import_all_models()
    init_db()
    yield
    os.chdir(original_cwd)
    reset_engine()


@pytest.fixture(autouse=True)
def _clean_tables(_test_environment: None) -> Iterator[None]:
    """Truncate every table after each test (cheap on SQLite)."""
    yield
    engine = get_engine()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture()
def db(_test_environment: None) -> Iterator[Session]:
    """A database session bound to the session-scoped test engine."""
    get_engine()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def settings() -> Settings:
    """The process-wide cached settings (built from the test environment)."""
    return get_settings()


@pytest.fixture(scope="session")
def app(_test_environment: None) -> FastAPI:
    """The FastAPI application under test."""
    return create_app()


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Iterator[TestClient]:
    """A TestClient with the lifespan running (logging + schema bootstrap)."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def auth(client: TestClient) -> AuthContext:
    """Register a club through the API, log in, and return bearer headers."""
    unique = uuid4().hex[:10]
    email = f"admin-{unique}@example.com"
    response = client.post(
        f"{API}/auth/register-club",
        json={
            "club_name": f"Test Club {unique}",
            "slug": f"test-club-{unique}",
            "email": email,
            "password": TEST_PASSWORD,
            "full_name": "Test Admin",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    login = client.post(f"{API}/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return AuthContext(
        club_id=body["club"]["id"],
        user_id=body["user"]["id"],
        email=email,
        password=TEST_PASSWORD,
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.fixture()
def make_club(client: TestClient, db: Session) -> Callable[[str], AuthContext]:
    """Factory creating extra clubs directly in the DB (bootstrap is closed).

    ``env=test`` keeps ``POST /auth/register-club`` open only while no club
    exists, so additional tenants (e.g. club B in the tenancy test) are seeded
    straight into the database and then logged in through the API.
    """

    def _make(label: str = "b") -> AuthContext:
        unique = uuid4().hex[:10]
        email = f"{label}-admin-{unique}@example.com"
        club = Club(name=f"Club {label} {unique}", slug=f"club-{label}-{unique}", settings_json={})
        db.add(club)
        db.flush()
        user = User(
            club_id=club.id,
            email=email,
            hashed_password=hash_password(TEST_PASSWORD),
            full_name=f"Admin {label}",
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role="admin", club_id=club.id))
        db.commit()
        login = client.post(f"{API}/auth/login", json={"email": email, "password": TEST_PASSWORD})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        return AuthContext(
            club_id=club.id,
            user_id=user.id,
            email=email,
            password=TEST_PASSWORD,
            headers={"Authorization": f"Bearer {token}"},
        )

    return _make


def _write_synthetic_video(
    path: Path, fourcc: str = "mp4v", frames: int = 16, size: int = 64
) -> Path | None:
    """Write a tiny deterministic video with OpenCV; None when encoding fails."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), 8.0, (size, size))
    if not writer.isOpened():
        writer.release()
        return None
    for index in range(frames):
        frame = np.zeros((size, size, 3), dtype=np.uint8)
        x = (4 + 3 * index) % (size - 14)
        cv2.rectangle(frame, (x, 8), (x + 12, 28), (40, 40, 220), -1)
        y = (6 + 2 * index) % (size - 24)
        cv2.rectangle(frame, (40, y), (52, y + 20), (220, 60, 40), -1)
        writer.write(frame)
    writer.release()
    if not path.is_file() or path.stat().st_size == 0:
        return None
    return path


@pytest.fixture(scope="session")
def synthetic_video(_test_environment: None) -> Path:
    """Tiny synthetic video (16 frames, 64x64, ~2s) cached for the session."""
    path = _env.MEDIA_DIR / "synthetic_match.mp4"
    if path.is_file() and path.stat().st_size > 0:
        return path
    written = _write_synthetic_video(path)
    if written is None:
        written = _write_synthetic_video(_env.MEDIA_DIR / "synthetic_match.avi", fourcc="MJPG")
    if written is None:
        pytest.skip("OpenCV cannot encode a video on this platform")
    return written
