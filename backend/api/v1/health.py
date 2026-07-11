"""Health/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness check; always returns ok if the process is running."""
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check placeholder; extend to verify DB/Redis/storage connectivity."""
    return {"status": "ready"}
