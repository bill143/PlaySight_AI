"""Shared pytest fixtures and test environment configuration.

Sets required environment variables *before* any `backend` module is
imported so `backend.core.config.Settings` picks up test-safe values (an
in-memory SQLite database instead of Postgres, dummy secrets, etc.).
"""

from __future__ import annotations

import os

os.environ.setdefault("PLAYSIGHT_TESTING", "1")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("YOLO_MODEL_PATH", "yolov8n.pt")

import uuid
from collections.abc import AsyncGenerator

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401  (register all models on Base.metadata)
from backend.core.security import hash_password
from backend.models.base import Base


@pytest.fixture
def sample_frame() -> np.ndarray:
    """A deterministic synthetic BGR video frame for detector/tracker/OCR tests."""
    rng = np.random.default_rng(seed=42)
    return rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest_asyncio.fixture
async def test_engine():
    """A fresh in-memory SQLite async engine with all tables created, per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """A transactional AsyncSession bound to the per-test in-memory database."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """Create and persist a default 'admin' user for authenticated API tests."""
    from backend.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="admin@playsight.ai",
        hashed_password=hash_password("password123"),
        full_name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient wired to the FastAPI app with the DB dependency overridden."""
    from backend.core.database import get_db
    from backend.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user) -> dict[str, str]:
    """Log in as `test_user` and return an Authorization header with a valid access token."""
    from backend.core.security import create_access_token

    token = create_access_token(str(test_user.id), extra_claims={"role": test_user.role})
    return {"Authorization": "Bearer " + token}
