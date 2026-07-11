"""Application error hierarchy.

Every error carries a machine-readable ``code`` and a human-readable ``message``.
The API layer maps these to HTTP responses with body
``{"error": {"code", "message", "correlation_id"}}`` (see CONTRACTS.md section 4).
The ``http_status`` attribute is the canonical status code for each error class.
"""

from __future__ import annotations


class PlaySightError(Exception):
    """Base class for all PlaySight application errors."""

    default_code: str = "playsight_error"
    http_status: int = 500

    def __init__(self, message: str, code: str | None = None) -> None:
        """Create an error with a message and optional code override."""
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{type(self).__name__}(message={self.message!r}, code={self.code!r})"


class NotFoundError(PlaySightError):
    """Entity does not exist (or is outside the caller's tenant scope) -> HTTP 404."""

    default_code = "not_found"
    http_status = 404


class AuthError(PlaySightError):
    """Authentication failed (missing/invalid/expired credentials) -> HTTP 401."""

    default_code = "auth_error"
    http_status = 401


class PermissionDeniedError(PlaySightError):
    """Authenticated but not allowed to perform the action -> HTTP 403."""

    default_code = "permission_denied"
    http_status = 403


class ValidationFailed(PlaySightError):
    """Domain-level validation failure -> HTTP 422."""

    default_code = "validation_failed"
    http_status = 422


class ExternalServiceError(PlaySightError):
    """Upstream/external service failure (YouTube, storage, ...) -> HTTP 502."""

    default_code = "external_service_error"
    http_status = 502


class FeatureDisabledError(PlaySightError):
    """Feature flag / module disabled for this deployment or club -> HTTP 403."""

    default_code = "feature_disabled"
    http_status = 403
