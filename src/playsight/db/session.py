"""Engine/session management and FastAPI database dependency."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from playsight.config.settings import get_settings
from playsight.core.logging import get_logger

log = get_logger(__name__)

_engine: Engine | None = None

#: Process-wide session factory. Bound lazily to the engine on first use.
SessionLocal: sessionmaker[Session] = sessionmaker(
    autoflush=False,
    expire_on_commit=False,
)


def get_engine() -> Engine:
    """Return the process-wide engine, creating it from settings on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args: dict[str, object] = {}
        if url.startswith("sqlite"):
            # Allow the same SQLite connection across FastAPI/Celery threads.
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        SessionLocal.configure(bind=_engine)
        log.info("db_engine_created", url=_engine.url.render_as_string(hide_password=True))
    return _engine


def reset_engine() -> None:
    """Dispose the current engine and unbind the session factory (tests only)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal.configure(bind=None)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session, closed after the request."""
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager providing a transactional session (commit/rollback/close)."""
    get_engine()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (``Base.metadata.create_all``) for local/dev bootstrap.

    Production schema management uses Alembic; this exists so the CLI and tests
    can run against SQLite without migrations.
    """
    import playsight.db.models  # noqa: F401  (registers every model on Base.metadata)
    from playsight.db.base import Base

    Base.metadata.create_all(bind=get_engine())
    log.info("db_initialized")
