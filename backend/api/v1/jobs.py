"""Processing job status endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import NotFoundError
from backend.core.rbac import Permission
from backend.models.match import ProcessingJob
from backend.models.user import User
from backend.schemas.job import JobStatusRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusRead)
async def get_job_status(
    job_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.MATCH_READ)),
) -> ProcessingJob:
    """Get the current status/progress of a processing job (queued/running/succeeded/failed)."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return job
