"""Custom application exceptions and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse


class PlaySightError(Exception):
    """Base class for all application-specific errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "playsight_error"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code


class NotFoundError(PlaySightError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationFailedError(PlaySightError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_failed"


class AuthenticationError(PlaySightError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_failed"


class AuthorizationError(PlaySightError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "authorization_failed"


class FeatureDisabledError(PlaySightError):
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "feature_disabled"


class ProcessingError(PlaySightError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "processing_error"


async def playsight_exception_handler(request: Request, exc: PlaySightError) -> JSONResponse:
    """Convert a `PlaySightError` into a consistent JSON error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )
