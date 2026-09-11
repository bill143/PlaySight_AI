"""FastAPI application factory (CONTRACTS.md sections 4, 10, 12).

Run with::

    uvicorn playsight.api.main:app --reload

Wiring:

- All routers mount under ``/api/v1``.
- CORS origins come from settings (``PLAYSIGHT_CORS_ORIGINS``, comma-separated;
  default ``http://localhost:3000`` for local dev).
- ``CorrelationIdMiddleware`` reads/sets ``X-Correlation-ID`` and binds it
  into structlog for every request.
- ``PlaySightError`` maps to its canonical HTTP status with body
  ``{"error": {"code", "message", "correlation_id"}}``.
- Startup: ``configure_logging()`` + ``init_db()`` (after importing every
  Phase 2/3 module's models so their tables register on the metadata).
- Phase 2/3 module routers are included via ``playsight.modules.iter_routers()``;
  each carries its own ``require_feature`` guard (disabled -> 403).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from playsight import __version__
from playsight.api.middleware import CORRELATION_HEADER, CorrelationIdMiddleware
from playsight.api.routers import (
    artifacts,
    auth,
    health,
    jobs,
    matches,
    players,
    publish,
    teams,
)
from playsight.config.settings import get_settings
from playsight.core.errors import PlaySightError
from playsight.core.logging import configure_logging, get_logger
from playsight.db.session import init_db
from playsight.modules import import_all_models, iter_routers

log = get_logger(__name__)

API_PREFIX = "/api/v1"

OPENAPI_TAGS: list[dict[str, Any]] = [
    {"name": "auth", "description": "Registration bootstrap, login, token refresh."},
    {"name": "teams", "description": "Club teams."},
    {"name": "players", "description": "Rostered players."},
    {"name": "matches", "description": "Matches: CRUD, video ingest, analysis jobs, results."},
    {"name": "jobs", "description": "Background processing jobs and their progress."},
    {"name": "artifacts", "description": "Generated output files (list + download)."},
    {"name": "publish", "description": "YouTube publishing (rights-confirmed, idempotent)."},
    {"name": "health", "description": "Liveness and readiness probes."},
    {"name": "competition", "description": "Phase 2: fixtures and standings sync."},
    {"name": "merchandise", "description": "Phase 2: club shop catalog."},
    {"name": "playbook", "description": "Phase 2: plays, diagrams, clip links."},
    {"name": "training", "description": "Phase 2: training plans and attendance."},
    {"name": "nutrition", "description": "Phase 2: nutrition profiles and templates."},
    {"name": "registration", "description": "Phase 3: registrations and approvals."},
    {"name": "payments", "description": "Phase 3: payment processing."},
    {"name": "commerce", "description": "Phase 3: cart, checkout, orders."},
]


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def playsight_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a PlaySightError to its canonical HTTP status and JSON error body."""
    error = exc if isinstance(exc, PlaySightError) else PlaySightError(str(exc))
    cid = _correlation_id(request)
    log.info(
        "request_error",
        code=error.code,
        status=error.http_status,
        message=error.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=error.http_status,
        content={"error": {"code": error.code, "message": error.message, "correlation_id": cid}},
        headers={CORRELATION_HEADER: cid} if cid else None,
    )


def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the exception and answer a JSON 500 (no internals leaked)."""
    cid = _correlation_id(request)
    log.error(
        "unhandled_exception",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error.",
                "correlation_id": cid,
            }
        },
        headers={CORRELATION_HEADER: cid} if cid else None,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: configure logging, register all models, create tables."""
    configure_logging()
    loaded = import_all_models()
    init_db()
    log.info("api_started", version=__version__, modules_loaded=loaded)
    yield
    log.info("api_stopped")


def create_app() -> FastAPI:
    """Build the PlaySight FastAPI application."""
    configure_logging()
    app = FastAPI(
        title="PlaySight AI",
        version=__version__,
        description=(
            "Multi-sport video analytics, club operations, and athlete development. "
            "Analytics outputs are heuristic estimates with confidence scores, "
            "not ground truth."
        ),
        openapi_tags=OPENAPI_TAGS,
        lifespan=_lifespan,
    )

    # Last-added middleware runs first: CORS wraps the correlation middleware.
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_HEADER],
    )

    app.add_exception_handler(PlaySightError, playsight_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    for router in (
        auth.router,
        teams.router,
        players.router,
        matches.router,
        jobs.router,
        artifacts.router,
        publish.router,
        health.router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    # Phase 2/3 module routers (each guarded by its own require_feature).
    for module_router in iter_routers():
        app.include_router(module_router, prefix=API_PREFIX)

    return app


#: Module-level app for ``uvicorn playsight.api.main:app``.
app = create_app()
