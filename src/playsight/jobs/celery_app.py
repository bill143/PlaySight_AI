"""Celery application (CONTRACTS.md section 11).

The module-level ``app`` is the Celery instance the worker runs against::

    celery -A playsight.jobs.celery_app worker --loglevel=INFO

Task definitions live in ``playsight.jobs.tasks``; dispatching (including the
eager in-process mode) lives in ``playsight.jobs.dispatch``.
"""

from __future__ import annotations

import os

from celery import Celery

from playsight.config.settings import Settings, get_settings


def _eager_mode(settings: Settings) -> bool:
    """Return whether jobs must execute synchronously in-process."""
    return (
        not settings.redis_url
        or settings.env == "test"
        or os.environ.get("PLAYSIGHT_EAGER_JOBS") == "1"
    )


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Build the Celery app from settings (redis broker + result backend)."""
    settings = settings or get_settings()
    broker = settings.redis_url or "memory://"
    backend = settings.redis_url or "cache+memory://"

    celery_app = Celery("playsight", broker=broker, backend=backend)
    celery_app.conf.update(
        task_acks_late=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_default_retry_delay=10,
        task_track_started=True,
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
        task_always_eager=_eager_mode(settings),
        task_eager_propagates=True,
        include=["playsight.jobs.tasks"],
    )
    return celery_app


#: Process-wide Celery app (also exposed as ``playsight.jobs.app``).
app: Celery = create_celery_app()
