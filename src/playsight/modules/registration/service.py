"""Registration services (Phase 3 scaffold).

Implemented: form CRUD, registration CRUD, and the status-transition workflow
(with consent validation on submission and ``audit_logs`` writes).

Stubbed with ``NotImplementedError`` + ``# TODO(phase3)``: document upload to
object storage, and PII retention/export/delete workflows (CONTRACTS.md
section 18).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.db.models import AuditLog
from playsight.modules.registration.models import (
    RegistrantType,
    Registration,
    RegistrationDocument,
    RegistrationForm,
    RegistrationStatus,
    utcnow,
)
from playsight.modules.registration.schemas import RegistrationCreate, RegistrationFormCreate

log = get_logger(__name__)

#: Legal workflow transitions (current status -> allowed next statuses).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    RegistrationStatus.DRAFT.value: frozenset({RegistrationStatus.SUBMITTED.value}),
    RegistrationStatus.SUBMITTED.value: frozenset(
        {
            RegistrationStatus.APPROVED.value,
            RegistrationStatus.REJECTED.value,
            RegistrationStatus.WAITLISTED.value,
        }
    ),
    RegistrationStatus.WAITLISTED.value: frozenset(
        {RegistrationStatus.APPROVED.value, RegistrationStatus.REJECTED.value}
    ),
    RegistrationStatus.APPROVED.value: frozenset(),
    RegistrationStatus.REJECTED.value: frozenset(),
}


def create_form(db: Session, club_id: str, data: RegistrationFormCreate) -> RegistrationForm:
    """Create a configurable registration form for a club."""
    form = RegistrationForm(
        club_id=club_id,
        name=data.name,
        description=data.description,
        season=data.season,
        fields_json=data.fields_json,
        is_active=data.is_active,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    log.info("registration_form_created", form_id=form.id, club_id=club_id)
    return form


def list_forms(
    db: Session, club_id: str, *, include_inactive: bool = False
) -> list[RegistrationForm]:
    """List a club's registration forms (active only unless ``include_inactive``)."""
    stmt = select(RegistrationForm).where(RegistrationForm.club_id == club_id)
    if not include_inactive:
        stmt = stmt.where(RegistrationForm.is_active.is_(True))
    stmt = stmt.order_by(RegistrationForm.created_at)
    return list(db.execute(stmt).scalars().all())


def get_form(db: Session, club_id: str, form_id: str) -> RegistrationForm:
    """Return one club-scoped form; raise ``NotFoundError`` (404) outside the tenant."""
    form = db.get(RegistrationForm, form_id)
    if form is None or form.club_id != club_id:
        raise NotFoundError(f"Registration form {form_id} not found.")
    return form


def create_registration(
    db: Session, club_id: str, data: RegistrationCreate, *, user_id: str | None = None
) -> Registration:
    """Create a registration in ``draft`` status."""
    if data.form_id is not None:
        get_form(db, club_id, data.form_id)  # 404 when the form is not in this club
    registration = Registration(
        club_id=club_id,
        form_id=data.form_id,
        user_id=user_id,
        registrant_type=RegistrantType(data.registrant_type).value,
        registrant_name=data.registrant_name,
        registrant_dob=data.registrant_dob,
        family_group_id=data.family_group_id,
        status=RegistrationStatus.DRAFT.value,
        answers_json=data.answers_json,
        consent_json=data.consent_json,
        medical_flags_json=data.medical_flags_json,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    log.info("registration_created", registration_id=registration.id, club_id=club_id)
    return registration


def list_registrations(
    db: Session,
    club_id: str,
    *,
    status: RegistrationStatus | str | None = None,
    registrant_type: RegistrantType | str | None = None,
    family_group_id: str | None = None,
) -> list[Registration]:
    """List a club's registrations with optional filters."""
    stmt = select(Registration).where(Registration.club_id == club_id)
    if status is not None:
        stmt = stmt.where(Registration.status == RegistrationStatus(status).value)
    if registrant_type is not None:
        stmt = stmt.where(Registration.registrant_type == RegistrantType(registrant_type).value)
    if family_group_id is not None:
        stmt = stmt.where(Registration.family_group_id == family_group_id)
    stmt = stmt.order_by(Registration.created_at)
    return list(db.execute(stmt).scalars().all())


def get_registration(db: Session, club_id: str, registration_id: str) -> Registration:
    """Return one club-scoped registration; 404 outside the tenant."""
    registration = db.get(Registration, registration_id)
    if registration is None or registration.club_id != club_id:
        raise NotFoundError(f"Registration {registration_id} not found.")
    return registration


def _validate_consent_for_submission(registration: Registration) -> None:
    """Reject submission unless terms are accepted (and guardian consent for minors)."""
    consent = registration.consent_json or {}
    if consent.get("terms_accepted") is not True:
        raise ValidationFailed(
            "Submission requires terms acceptance: set consent_json.terms_accepted = true."
        )
    if consent.get("is_minor") is True and (
        not consent.get("guardian_name") or consent.get("guardian_accepted") is not True
    ):
        raise ValidationFailed(
            "Minors require guardian consent: set consent_json.guardian_name and "
            "consent_json.guardian_accepted = true."
        )


def transition_status(
    db: Session,
    club_id: str,
    registration_id: str,
    new_status: RegistrationStatus | str,
    *,
    acting_user_id: str | None = None,
) -> Registration:
    """Move a registration through the workflow, writing an ``audit_logs`` row.

    Allowed transitions are defined in ``ALLOWED_TRANSITIONS``. Submission
    additionally validates consent (terms acceptance, guardian consent for
    minors). Raises ``ValidationFailed`` (422) on illegal transitions and
    ``NotFoundError`` (404) outside the tenant.
    """
    try:
        target = RegistrationStatus(new_status).value
    except ValueError as exc:
        raise ValidationFailed(f"Unknown registration status: {new_status!r}.") from exc

    registration = get_registration(db, club_id, registration_id)
    current = registration.status
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValidationFailed(f"Illegal status transition: {current!r} -> {target!r}.")

    if target == RegistrationStatus.SUBMITTED.value:
        _validate_consent_for_submission(registration)

    now: datetime = utcnow()
    registration.status = target
    if target == RegistrationStatus.SUBMITTED.value:
        registration.submitted_at = now
    else:
        registration.decided_at = now
        registration.decided_by = acting_user_id
    # TODO(phase3): before approving, enforce the payment-required-before-activation
    # rule via playsight.modules.payments.service.assert_paid_before_activation when
    # the "payments" feature is enabled for this club.

    db.add(
        AuditLog(
            club_id=club_id,
            user_id=acting_user_id,
            action="registration.status_change",
            entity_type="registration",
            entity_id=registration.id,
            before_json={"status": current},
            after_json={"status": target},
        )
    )
    db.commit()
    db.refresh(registration)
    log.info(
        "registration_status_changed",
        registration_id=registration.id,
        club_id=club_id,
        from_status=current,
        to_status=target,
        acting_user_id=acting_user_id,
    )
    return registration


def upload_document(
    db: Session,
    club_id: str,
    registration_id: str,
    *,
    doc_type: str,
    filename: str,
    content_type: str,
    content: bytes,
    uploaded_by: str | None = None,
) -> RegistrationDocument:
    """Store a supporting document in object storage and register it. Stub.

    Planned flow: validate the registration (club-scoped), write ``content`` to
    object storage under an opaque, PII-free key
    ``registrations/<registration_id>/documents/<document_id>``, then persist a
    ``RegistrationDocument`` row and an ``audit_logs`` entry.
    """
    get_registration(db, club_id, registration_id)  # 404 outside the tenant
    # TODO(phase3): wire to playsight.storage (put_bytes) + audit log + virus scanning.
    raise NotImplementedError(
        "TODO(phase3): registration document upload to object storage is not implemented yet."
    )


def export_registrant_data(db: Session, club_id: str, registration_id: str) -> dict:
    """Export all personal data held for a registrant (GDPR-style export). Stub."""
    get_registration(db, club_id, registration_id)  # 404 outside the tenant
    # TODO(phase3): collect registration rows, documents, and audit trail into a
    # portable JSON bundle for data-subject access requests (CONTRACTS.md section 18).
    raise NotImplementedError("TODO(phase3): registrant data export is not implemented yet.")


def delete_registrant_data(db: Session, club_id: str, registration_id: str) -> None:
    """Erase personal data held for a registrant (retention/delete workflow). Stub."""
    get_registration(db, club_id, registration_id)  # 404 outside the tenant
    # TODO(phase3): anonymize registration rows, purge stored documents, and keep a
    # minimal audit record of the erasure (CONTRACTS.md section 18).
    raise NotImplementedError("TODO(phase3): registrant data deletion is not implemented yet.")
