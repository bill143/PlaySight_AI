"""Registration API router (Phase 3 scaffold; CONTRACTS.md sections 10, 12).

All endpoints are guarded by ``require_feature("registration")`` (HTTP 403 with
code ``feature_disabled`` when the flag is off) and are club-scoped through the
tenant context. Registrar decisions require the ``registrar`` role (``admin``
always passes).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from playsight.api.deps import TenantContext, get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.core.logging import get_logger
from playsight.db.session import get_db
from playsight.modules.registration import service
from playsight.modules.registration.models import RegistrantType, RegistrationStatus
from playsight.modules.registration.schemas import (
    RegistrationCreate,
    RegistrationFormCreate,
    RegistrationFormRead,
    RegistrationRead,
    RegistrationStatusUpdate,
)

log = get_logger(__name__)

router = APIRouter(
    prefix="/registration",
    tags=["registration"],
    dependencies=[Depends(require_feature("registration"))],
)

_PHASE3_TODO = {"todo": "phase3", "docs": "docs/ROADMAP.md"}


def _not_implemented() -> JSONResponse:
    """Return the contracted 501 body for not-yet-implemented Phase 3 flows."""
    return JSONResponse(status_code=501, content=_PHASE3_TODO)


@router.get("/forms", response_model=list[RegistrationFormRead])
def list_forms(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's registration forms."""
    return service.list_forms(db, tenant.club_id, include_inactive=include_inactive)


@router.post("/forms", response_model=RegistrationFormRead, status_code=201)
def create_form(
    payload: RegistrationFormCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _registrar: Any = Depends(require_roles(Role.REGISTRAR)),
) -> Any:
    """Create a registration form (registrar/admin only)."""
    return service.create_form(db, tenant.club_id, payload)


@router.get("/registrations", response_model=list[RegistrationRead])
def list_registrations(
    status: RegistrationStatus | None = Query(default=None),
    registrant_type: RegistrantType | None = Query(default=None),
    family_group_id: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """List the club's registrations with optional filters."""
    return service.list_registrations(
        db,
        tenant.club_id,
        status=status,
        registrant_type=registrant_type,
        family_group_id=family_group_id,
    )


@router.post("/registrations", response_model=RegistrationRead, status_code=201)
def create_registration(
    payload: RegistrationCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Create a registration in ``draft`` status for the current tenant."""
    user_id = getattr(getattr(tenant, "user", None), "id", None)
    return service.create_registration(db, tenant.club_id, payload, user_id=user_id)


@router.get("/registrations/{registration_id}", response_model=RegistrationRead)
def get_registration(
    registration_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Fetch one registration (404 outside the caller's club)."""
    return service.get_registration(db, tenant.club_id, registration_id)


@router.post("/registrations/{registration_id}/submit", response_model=RegistrationRead)
def submit_registration(
    registration_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Any:
    """Submit a draft registration (validates terms + guardian consent for minors)."""
    user_id = getattr(getattr(tenant, "user", None), "id", None)
    return service.transition_status(
        db,
        tenant.club_id,
        registration_id,
        RegistrationStatus.SUBMITTED,
        acting_user_id=user_id,
    )


@router.post("/registrations/{registration_id}/status", response_model=RegistrationRead)
def decide_registration(
    registration_id: str,
    payload: RegistrationStatusUpdate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    registrar: Any = Depends(require_roles(Role.REGISTRAR)),
) -> Any:
    """Apply a workflow transition (approve/reject/waitlist) - registrar/admin only."""
    return service.transition_status(
        db,
        tenant.club_id,
        registration_id,
        payload.status,
        acting_user_id=getattr(registrar, "id", None),
    )


@router.post("/registrations/{registration_id}/documents", response_model=None)
def upload_document(
    registration_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(default="other"),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Upload a supporting document. Stub: returns 501 until Phase 3."""
    user_id = getattr(getattr(tenant, "user", None), "id", None)
    try:
        service.upload_document(
            db,
            tenant.club_id,
            registration_id,
            doc_type=doc_type,
            filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            content=file.file.read(),
            uploaded_by=user_id,
        )
    except NotImplementedError:
        log.info("registration_document_upload_stub", registration_id=registration_id)
        return _not_implemented()
    return _not_implemented()  # pragma: no cover - unreachable until phase3
