"""Celery application instance and configuration."""

from __future__ import annotations

from celery import Celery

from backend.core.config import settings

celery_app = Celery(
    "playsight",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.workers.tasks.processing",
        "backend.workers.tasks.export_tasks",
        "backend.workers.tasks.publish_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24,
)

# Run tasks synchronously (eagerly) in test/dev environments unless overridden,
# so the pipeline can be exercised in unit tests without a live broker.
if settings.ENVIRONMENT == "test":
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
