"""Background jobs: Celery app, task definitions, and dispatching (CONTRACTS.md section 11).

Public interface:

- ``playsight.jobs.app`` — the Celery application (worker entry point).
- ``playsight.jobs.dispatch_job(db, job)`` — THE single dispatch entry point
  used by the API and CLI (eager in-process mode or Celery ``.delay()``).
- Task functions live in ``playsight.jobs.tasks`` (imported lazily by
  ``dispatch_job`` so importing this package stays light).
"""

from playsight.jobs.celery_app import app, create_celery_app
from playsight.jobs.dispatch import KIND_TO_TASK, dispatch_job, eager_jobs_enabled

__all__ = [
    "KIND_TO_TASK",
    "app",
    "create_celery_app",
    "dispatch_job",
    "eager_jobs_enabled",
]
