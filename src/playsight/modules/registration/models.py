"""Registration module tables (Phase 3 scaffold; CONTRACTS.md sections 5, 10, 18).

Every table carries the tenancy column ``club_id`` (FK ``clubs.id``, indexed).
Primary keys are 32-char uuid4 hex strings from ``playsight.core.ids.new_id``.

PII note (CONTRACTS.md section 18): registrant names, dates of birth, consent
records, and medical flags are personal data. Storage keys never contain PII,
sensitive mutations are audit-logged, and retention/export/delete workflows are
stubbed in ``service.py``.  # TODO(phase3): full PII retention/export/delete.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from playsight.core.ids import new_id
from playsight.db.base import Base


def utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class RegistrantType(StrEnum):
    """Who is being registered."""

    PLAYER = "player"
    MEMBER = "member"
    OFFICIAL = "official"


class RegistrationStatus(StrEnum):
    """Registration approval workflow states."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"


class RegistrationForm(Base):
    """A club-configurable registration form (season sign-ups, memberships, ...)."""

    __tablename__ = "registration_forms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # List of field definitions: {"key", "label", "type", "required", "options"}.
    fields_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Registration(Base):
    """A single registration moving through the approval workflow."""

    __tablename__ = "registrations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    form_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("registration_forms.id"), nullable=True, index=True
    )
    # Submitting account (a guardian may register a minor on their own account).
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    # player | member | official (RegistrantType)
    registrant_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RegistrantType.PLAYER.value
    )
    registrant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registrant_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Groups sibling registrations (family discounts, shared guardian).
    family_group_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # draft | submitted | approved | rejected | waitlisted (RegistrationStatus)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RegistrationStatus.DRAFT.value, index=True
    )
    # Answers to the form's configurable fields, keyed by field key.
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Terms acceptance + guardian consent for minors:
    # {"terms_accepted": bool, "terms_version": str, "accepted_at": iso8601,
    #  "is_minor": bool, "guardian_name": str, "guardian_relationship": str,
    #  "guardian_accepted": bool}
    consent_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"allergies": [...], "conditions": [...], "notes": str} - PII, handle with care.
    medical_flags_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    documents: Mapped[list[RegistrationDocument]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )


class RegistrationDocument(Base):
    """A supporting document attached to a registration (ID proof, clearance, ...).

    ``storage_key`` never contains PII (CONTRACTS.md section 18); files live in
    object storage under opaque keys.
    """

    __tablename__ = "registration_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    registration_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("registrations.id"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # e.g. "id_proof" | "medical_clearance" | "photo_release" | "other"
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(255), nullable=False, default="application/octet-stream"
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    registration: Mapped[Registration] = relationship(back_populates="documents")
