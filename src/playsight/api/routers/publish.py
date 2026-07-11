"""YouTube publishing endpoints (CONTRACTS.md sections 12-13, 18).

Idempotency: the ``Idempotency-Key`` header (server-generated when absent) is
stored uniquely on ``upload_records``. Re-posting the same key returns the
existing record (HTTP 200) without creating another upload job.

Legal invariant: the body must carry ``confirm_rights: true`` (the caller
confirms they hold publishing rights) or the request fails 422. Privacy
defaults to ``private``; the platform never auto-publishes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from playsight.api.audit import write_audit
from playsight.api.deps import TenantContext, get_db, get_tenant
from playsight.api.schemas.publish import PublishAccepted, PublishRequest, UploadRecordRead
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.ids import new_id
from playsight.core.logging import get_logger
from playsight.db.models import Artifact, ProcessingJob, UploadRecord
from playsight.jobs.dispatch import dispatch_job

log = get_logger(__name__)

# get_tenant runs first so require_feature sees request.state.tenant and can
# apply the per-club override of the ``publishing_youtube`` flag.
router = APIRouter(
    prefix="/publish",
    tags=["publish"],
    dependencies=[Depends(get_tenant), Depends(require_feature("publishing_youtube"))],
)

_require_publisher = require_roles(Role.ADMIN, Role.COACH, Role.ANALYST)


def _find_publish_job_id(db: Session, tenant: TenantContext, upload_record_id: str) -> str | None:
    """Locate the newest publish job referencing an upload record (best effort)."""
    jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.club_id == tenant.club_id, ProcessingJob.kind == "publish")
        .order_by(ProcessingJob.created_at.desc())
        .all()
    )
    for job in jobs:
        params = job.params_json or {}
        if params.get("upload_record_id") == upload_record_id:
            return job.id
    return None


@router.post("/youtube", response_model=PublishAccepted, status_code=201)
def publish_youtube(
    payload: PublishRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_publisher),
) -> PublishAccepted:
    """Create an upload record + publish job for an artifact (idempotent)."""
    if not payload.confirm_rights:
        raise ValidationFailed(
            "You must confirm you hold the rights to publish this footage by setting "
            "'confirm_rights': true (copyright confirmation is required)."
        )

    artifact = db.get(Artifact, payload.artifact_id)
    if artifact is None or artifact.club_id != tenant.club_id:
        raise NotFoundError(f"Artifact not found: {payload.artifact_id}")

    key = idempotency_key or new_id()
    existing = (
        db.query(UploadRecord)
        .filter(UploadRecord.idempotency_key == key, UploadRecord.club_id == tenant.club_id)
        .one_or_none()
    )
    if existing is not None:
        response.status_code = 200
        log.info("publish_idempotent_hit", upload_id=existing.id, idempotency_key=key)
        return PublishAccepted(
            upload_id=existing.id,
            job_id=_find_publish_job_id(db, tenant, existing.id),
            status=existing.status,
        )

    record = UploadRecord(
        club_id=tenant.club_id,
        artifact_id=artifact.id,
        platform="youtube",
        idempotency_key=key,
        status="pending",
        title=payload.title,
        description=payload.description,
        tags_json=list(payload.tags),
        category_id=payload.category_id,
        privacy=payload.privacy,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race on the unique idempotency key: return the winner's record.
        db.rollback()
        winner = (
            db.query(UploadRecord)
            .filter(UploadRecord.idempotency_key == key, UploadRecord.club_id == tenant.club_id)
            .one_or_none()
        )
        if winner is None:  # key collision from another club
            raise ValidationFailed(f"Idempotency key already in use: {key}") from None
        response.status_code = 200
        return PublishAccepted(
            upload_id=winner.id,
            job_id=_find_publish_job_id(db, tenant, winner.id),
            status=winner.status,
        )
    db.refresh(record)

    job = ProcessingJob(
        club_id=tenant.club_id,
        match_id=artifact.match_id,
        kind="publish",
        status="queued",
        progress=0.0,
        params_json={"upload_record_id": record.id, "artifact_id": artifact.id},
        correlation_id=getattr(request.state, "correlation_id", None) or new_id(),
    )
    db.add(job)
    write_audit(
        db,
        club_id=tenant.club_id,
        user_id=tenant.user.id if tenant.user else None,
        action="publish.youtube.request",
        entity_type="upload_record",
        entity_id=record.id,
        after={
            "artifact_id": artifact.id,
            "title": payload.title,
            "privacy": payload.privacy,
            "idempotency_key": key,
        },
    )
    db.commit()
    db.refresh(job)
    log.info("publish_requested", upload_id=record.id, job_id=job.id, privacy=payload.privacy)
    dispatch_job(db, job)
    return PublishAccepted(upload_id=record.id, job_id=job.id, status=record.status)


@router.get("/{upload_id}", response_model=UploadRecordRead)
def get_upload_record(
    upload_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> UploadRecord:
    """Fetch the full upload record (status, platform video id, error log)."""
    record = db.get(UploadRecord, upload_id)
    if record is None or record.club_id != tenant.club_id:
        raise NotFoundError(f"Upload record not found: {upload_id}")
    return record
