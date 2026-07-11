"""Processing-job read endpoints (tenancy-filtered)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from playsight.api.deps import Pagination, TenantContext, get_db, get_tenant, pagination_params
from playsight.api.schemas.jobs import JobRead
from playsight.core.errors import NotFoundError
from playsight.db.models import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    status: str | None = Query(default=None, description="Filter by job status."),
    kind: str | None = Query(default=None, description="Filter by job kind."),
    match_id: str | None = Query(default=None, description="Filter by match."),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[ProcessingJob]:
    """List the club's processing jobs, newest first."""
    query = db.query(ProcessingJob).filter(ProcessingJob.club_id == tenant.club_id)
    if status is not None:
        query = query.filter(ProcessingJob.status == status)
    if kind is not None:
        query = query.filter(ProcessingJob.kind == kind)
    if match_id is not None:
        query = query.filter(ProcessingJob.match_id == match_id)
    return (
        query.order_by(ProcessingJob.created_at.desc()).offset(page.offset).limit(page.limit).all()
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> ProcessingJob:
    """Fetch one job with its progress, error, and result payload."""
    job = db.get(ProcessingJob, job_id)
    if job is None or job.club_id != tenant.club_id:
        raise NotFoundError(f"Job not found: {job_id}")
    return job
