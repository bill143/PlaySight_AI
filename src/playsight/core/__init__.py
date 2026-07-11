"""Core utilities: logging, errors, IDs, and shared types."""

from playsight.core.errors import (
    AuthError,
    ExternalServiceError,
    FeatureDisabledError,
    NotFoundError,
    PermissionDeniedError,
    PlaySightError,
    ValidationFailed,
)
from playsight.core.ids import new_id
from playsight.core.logging import bind_correlation_id, configure_logging, get_logger

__all__ = [
    "AuthError",
    "ExternalServiceError",
    "FeatureDisabledError",
    "NotFoundError",
    "PermissionDeniedError",
    "PlaySightError",
    "ValidationFailed",
    "bind_correlation_id",
    "configure_logging",
    "get_logger",
    "new_id",
]
