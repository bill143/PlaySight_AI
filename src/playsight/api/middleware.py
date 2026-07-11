"""Correlation-ID middleware (CONTRACTS.md section 4).

Every request gets a correlation id: propagated from the incoming
``X-Correlation-ID`` header when present, freshly generated otherwise. The id
is bound into the structlog context for the duration of the request, stored on
``request.state.correlation_id`` (error handlers and job creation read it from
there), and echoed back on the response as ``X-Correlation-ID``.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from playsight.core.logging import bind_correlation_id, clear_correlation_id, get_logger

log = get_logger(__name__)

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id per request and emit structured access logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Handle one request: bind id, time it, set the response header."""
        cid = bind_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = cid
        started = time.perf_counter()
        log.info("request_started", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled errors bubble to the outer ServerErrorMiddleware; the
            # generic handler in main.py builds the JSON body and header.
            duration_ms = (time.perf_counter() - started) * 1000.0
            log.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
            )
            clear_correlation_id()
            raise
        response.headers[CORRELATION_HEADER] = cid
        duration_ms = (time.perf_counter() - started) * 1000.0
        log.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        clear_correlation_id()
        return response
