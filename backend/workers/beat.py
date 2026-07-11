"""Celery Beat periodic task schedules."""

from __future__ import annotations

from celery.schedules import crontab

from backend.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "cleanup-stale-jobs-daily": {
        "task": "backend.workers.tasks.processing.cleanup_stale_jobs_task",
        "schedule": crontab(hour=3, minute=0),
    },
}
