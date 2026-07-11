"""FastAPI application entry point."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api.v1.router import api_router
from backend.core.config import settings
from backend.core.exceptions import PlaySightError, playsight_exception_handler
from backend.core.logging import configure_logging, get_logger, set_correlation_id

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description="Multi-sport video analytics platform API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Attach a correlation ID to every request for structured log tracing."""
    incoming_id = request.headers.get("X-Correlation-ID")
    correlation_id = set_correlation_id(incoming_id)

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


app.add_exception_handler(PlaySightError, playsight_exception_handler)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with basic service info."""
    return {"service": settings.APP_NAME, "version": __version__, "docs": "/docs"}


def _generate_request_id() -> str:  # pragma: no cover - retained for potential external use
    return str(uuid.uuid4())
