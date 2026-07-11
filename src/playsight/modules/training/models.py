"""Training module tables (CONTRACTS.md sections 5, 12).

Role-based session templates, week-periodized plans, attendance tracking, and
coach notes. Workload recommendations from ``player_match_stats`` are a
# TODO(phase2) service stub.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from playsight.core.ids import new_id
from playsight.db.base import Base
from playsight.db.models import utcnow


class PlanStatus(StrEnum):
    """Lifecycle of a training plan."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AttendanceStatus(StrEnum):
    """Attendance outcome for one player at one session."""

    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"
    INJURED = "injured"


class TrainingTemplate(Base):
    """A reusable session template targeting a player role/position."""

    __tablename__ = "training_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Player role/position this template targets (e.g. "goalkeeper", "any").
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="any", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Ordered drill list: [{"name": ..., "minutes": ..., "focus": ...}, ...]
    drills_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class TrainingPlan(Base):
    """A multi-week plan with per-week periodization."""

    __tablename__ = "training_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("training_templates.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Week periodization: {"weeks": [{"week": 1, "focus": ..., "load": 0.8}, ...]}
    periodization_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # draft | active | archived (PlanStatus)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Attendance(Base):
    """One player's attendance record for one training session."""

    __tablename__ = "training_attendance"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("training_plans.id"), nullable=False, index=True
    )
    player_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=False, index=True
    )
    session_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # present | absent | excused | injured (AttendanceStatus)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="present")
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class CoachNote(Base):
    """A coach's note about a player (optionally tied to a plan)."""

    __tablename__ = "coach_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    player_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=False, index=True
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("training_plans.id"), nullable=True
    )
    author_user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    # Who may read the note: "coaches" (default) or "player" (shared).
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="coaches")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
