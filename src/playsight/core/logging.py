"""structlog configuration for JSON logging.

Usage::

    from playsight.core.logging import configure_logging, get_logger, bind_correlation_id

    configure_logging()
    log = get_logger(__name__)
    cid = bind_correlation_id()          # every subsequent log line carries correlation_id
    log.info("job_started", job_id="...")
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for structured JSON output on stdout.

    Idempotent: calling it repeatedly reconfigures with the given level.

    Args:
        level: stdlib logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    global _CONFIGURED
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger, configuring logging on first use.

    Args:
        name: Logger name, typically ``__name__``.
    """
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name) if name else structlog.get_logger()


def bind_correlation_id(correlation_id: str | None = None) -> str:
    """Bind a correlation id to the structlog context and return it.

    Every API request and background job calls this once; all subsequent log
    lines in the same context carry ``correlation_id``.

    Args:
        correlation_id: Existing id to propagate (e.g. from ``X-Correlation-ID``).
            A new uuid4 hex is generated when ``None``.

    Returns:
        The bound correlation id.
    """
    cid = correlation_id or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def clear_correlation_id() -> None:
    """Remove the correlation id from the structlog context (end of request/job)."""
    structlog.contextvars.unbind_contextvars("correlation_id")
