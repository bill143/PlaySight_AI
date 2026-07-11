"""Structured logging configuration using structlog with correlation ID support."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

from backend.core.config import settings

_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    """Return the correlation ID for the current context, if any."""
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set (or generate) the correlation ID for the current context."""
    value = correlation_id or str(uuid.uuid4())
    _correlation_id_ctx.set(value)
    return value


def _add_correlation_id(logger: object, method_name: str, event_dict: dict) -> dict:
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging for the whole application."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _add_correlation_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if settings.ENVIRONMENT == "production"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)
