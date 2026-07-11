"""Health endpoints (no auth): liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from playsight.config.settings import get_settings
from playsight.core.logging import get_logger
from playsight.db.session import get_db

log = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness probe: the process is up and serving requests."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    """Readiness probe: checks the database and (when configured) redis.

    Returns 200 with per-dependency check results, or 503 when any
    dependency is unavailable.
    """
    checks: dict[str, str] = {}
    healthy = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        healthy = False
        checks["database"] = "error"
        log.error("readiness_db_failed", error=str(exc))

    settings = get_settings()
    if settings.redis_url:
        client = None
        try:
            client = Redis.from_url(
                settings.redis_url, socket_connect_timeout=1.0, socket_timeout=1.0
            )
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            healthy = False
            checks["redis"] = "error"
            log.error("readiness_redis_failed", error=str(exc))
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # best-effort cleanup
                    log.debug("readiness_redis_close_failed")

    status_code = 200 if healthy else 503
    body = {"status": "ok" if healthy else "unavailable", "checks": checks}
    return JSONResponse(status_code=status_code, content=body)
