"""Job dispatching — THE single entry point the API and CLI use (CONTRACTS.md section 11).

``dispatch_job(db, job)`` either executes the job's task function
synchronously in-process (eager mode) or enqueues it on Celery and stores the
``celery_task_id`` on the job row.

Eager mode is active when any of these hold:

- env var ``PLAYSIGHT_EAGER_JOBS=1``
- ``settings.env == "test"``
- ``settings.redis_url`` is empty
"""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import ValidationFailed
from playsight.core.logging import get_logger
from playsight.db.models import ProcessingJob

log = get_logger(__name__)

#: Maps ``processing_jobs.kind`` to the task function name in ``playsight.jobs.tasks``.
KIND_TO_TASK: dict[str, str] = {
    "analyze": "run_analysis",
    "highlights": "run_highlights",
    "annotate": "run_annotate",
    "export_audio": "run_export_audio",
    "publish": "run_publish_youtube",
}


def eager_jobs_enabled(settings: Settings | None = None) -> bool:
    """Return whether jobs must run synchronously in-process (eager mode).

    Args:
        settings: Optional settings override; defaults to the process settings.
    """
    settings = settings or get_settings()
    return (
        os.environ.get("PLAYSIGHT_EAGER_JOBS") == "1"
        or settings.env == "test"
        or not settings.redis_url
    )


def dispatch_job(db: Session, job: ProcessingJob) -> None:
    """Dispatch a persisted ``processing_jobs`` row for execution.

    In eager mode the task function runs synchronously in this process
    (through the same job-state machinery a worker would use); otherwise the
    task is enqueued via ``.delay()`` and the Celery task id is stored on the
    job row.

    Args:
        db: Database session that persisted ``job`` (used to store the
            ``celery_task_id`` in async mode).
        job: The job row to dispatch; ``job.kind`` selects the task.

    Raises:
        ValidationFailed: ``job.kind`` has no registered task.
    """
    # Imported lazily so `import playsight.jobs` stays light and cycle-free.
    from playsight.jobs import tasks as task_module

    task_name = KIND_TO_TASK.get(job.kind)
    if task_name is None:
        raise ValidationFailed(f"no task registered for job kind {job.kind!r} (job {job.id})")
    task = getattr(task_module, task_name)

    if eager_jobs_enabled():
        log.info("job_dispatch_eager", job_id=job.id, kind=job.kind, task=task_name)
        task.run(job.id)
        return

    async_result = task.delay(job.id)
    job.celery_task_id = str(async_result.id)
    db.commit()
    log.info(
        "job_dispatch_enqueued",
        job_id=job.id,
        kind=job.kind,
        task=task_name,
        celery_task_id=job.celery_task_id,
    )
