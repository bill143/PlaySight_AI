"""Training service: templates/plans/attendance/notes CRUD + workload stub."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.db.models import Player
from playsight.modules.training.models import (
    Attendance,
    CoachNote,
    TrainingPlan,
    TrainingTemplate,
)
from playsight.modules.training.schemas import (
    AttendanceCreate,
    CoachNoteCreate,
    PlanCreate,
    PlanUpdate,
    TemplateCreate,
)


def _apply_updates(entity: object, data: dict) -> None:
    """Assign ``data`` fields onto an ORM entity, unwrapping ``Enum`` values."""
    for field_name, value in data.items():
        setattr(entity, field_name, value.value if isinstance(value, Enum) else value)


class TrainingService:
    """Club-scoped training management.

    Cross-club access surfaces as ``NotFoundError`` (HTTP 404). Workload
    recommendations from ``player_match_stats`` are a Phase 2 stub.
    """

    def __init__(self, db: Session) -> None:
        """Bind the service to an open database session."""
        self.db = db

    # -- templates -------------------------------------------------------------

    def create_template(self, club_id: str, payload: TemplateCreate) -> TrainingTemplate:
        """Create a role-based session template."""
        template = TrainingTemplate(
            club_id=club_id,
            name=payload.name,
            role=payload.role,
            description=payload.description,
            drills_json=list(payload.drills_json),
            duration_minutes=payload.duration_minutes,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def list_templates(self, club_id: str, *, role: str | None = None) -> list[TrainingTemplate]:
        """List templates, optionally filtered by target role."""
        stmt = select(TrainingTemplate).where(TrainingTemplate.club_id == club_id)
        if role is not None:
            stmt = stmt.where(TrainingTemplate.role == role)
        stmt = stmt.order_by(TrainingTemplate.name)
        return list(self.db.scalars(stmt))

    def get_template(self, club_id: str, template_id: str) -> TrainingTemplate:
        """Return one template, raising ``NotFoundError`` outside the club scope."""
        template = self.db.get(TrainingTemplate, template_id)
        if template is None or template.club_id != club_id:
            raise NotFoundError(f"Training template {template_id} not found.")
        return template

    def delete_template(self, club_id: str, template_id: str) -> None:
        """Delete a template (plans keep their ``template_id`` reference nulled)."""
        template = self.get_template(club_id, template_id)
        for plan in self.db.scalars(
            select(TrainingPlan).where(
                TrainingPlan.club_id == club_id, TrainingPlan.template_id == template.id
            )
        ):
            plan.template_id = None
        self.db.delete(template)
        self.db.commit()

    # -- plans ------------------------------------------------------------------

    def create_plan(self, club_id: str, payload: PlanCreate) -> TrainingPlan:
        """Create a multi-week plan with week periodization JSON."""
        if payload.template_id is not None:
            self.get_template(club_id, payload.template_id)
        plan = TrainingPlan(
            club_id=club_id,
            team_id=payload.team_id,
            template_id=payload.template_id,
            name=payload.name,
            starts_on=payload.starts_on,
            weeks=payload.weeks,
            periodization_json=dict(payload.periodization_json),
            status=payload.status.value,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def list_plans(
        self, club_id: str, *, status: str | None = None, team_id: str | None = None
    ) -> list[TrainingPlan]:
        """List plans, optionally filtered by status and team."""
        stmt = select(TrainingPlan).where(TrainingPlan.club_id == club_id)
        if status is not None:
            stmt = stmt.where(TrainingPlan.status == status)
        if team_id is not None:
            stmt = stmt.where(TrainingPlan.team_id == team_id)
        stmt = stmt.order_by(TrainingPlan.created_at)
        return list(self.db.scalars(stmt))

    def get_plan(self, club_id: str, plan_id: str) -> TrainingPlan:
        """Return one plan, raising ``NotFoundError`` outside the club scope."""
        plan = self.db.get(TrainingPlan, plan_id)
        if plan is None or plan.club_id != club_id:
            raise NotFoundError(f"Training plan {plan_id} not found.")
        return plan

    def update_plan(self, club_id: str, plan_id: str, payload: PlanUpdate) -> TrainingPlan:
        """Apply a partial update to a plan."""
        plan = self.get_plan(club_id, plan_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("template_id") is not None:
            self.get_template(club_id, data["template_id"])
        _apply_updates(plan, data)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_plan(self, club_id: str, plan_id: str) -> None:
        """Delete a plan together with its attendance records."""
        plan = self.get_plan(club_id, plan_id)
        self.db.execute(delete(Attendance).where(Attendance.plan_id == plan.id))
        self.db.delete(plan)
        self.db.commit()

    # -- attendance ---------------------------------------------------------------

    def record_attendance(
        self, club_id: str, plan_id: str, payload: AttendanceCreate
    ) -> Attendance:
        """Record one player's attendance for one session of a plan."""
        plan = self.get_plan(club_id, plan_id)
        self._get_player(club_id, payload.player_id)
        record = Attendance(
            club_id=club_id,
            plan_id=plan.id,
            player_id=payload.player_id,
            session_at=payload.session_at,
            status=payload.status.value,
            note=payload.note,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_attendance(
        self, club_id: str, plan_id: str, *, player_id: str | None = None
    ) -> list[Attendance]:
        """List attendance records of a plan, optionally for one player."""
        plan = self.get_plan(club_id, plan_id)
        stmt = select(Attendance).where(
            Attendance.club_id == club_id, Attendance.plan_id == plan.id
        )
        if player_id is not None:
            stmt = stmt.where(Attendance.player_id == player_id)
        stmt = stmt.order_by(Attendance.session_at)
        return list(self.db.scalars(stmt))

    # -- coach notes ------------------------------------------------------------------

    def add_note(
        self, club_id: str, payload: CoachNoteCreate, *, author_user_id: str | None = None
    ) -> CoachNote:
        """Add a coach note about a player."""
        self._get_player(club_id, payload.player_id)
        if payload.plan_id is not None:
            self.get_plan(club_id, payload.plan_id)
        note = CoachNote(
            club_id=club_id,
            player_id=payload.player_id,
            plan_id=payload.plan_id,
            author_user_id=author_user_id,
            note=payload.note,
            visibility=payload.visibility,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_notes(self, club_id: str, *, player_id: str | None = None) -> list[CoachNote]:
        """List coach notes, optionally for one player."""
        stmt = select(CoachNote).where(CoachNote.club_id == club_id)
        if player_id is not None:
            stmt = stmt.where(CoachNote.player_id == player_id)
        stmt = stmt.order_by(CoachNote.created_at)
        return list(self.db.scalars(stmt))

    def delete_note(self, club_id: str, note_id: str) -> None:
        """Delete one coach note."""
        note = self.db.get(CoachNote, note_id)
        if note is None or note.club_id != club_id:
            raise NotFoundError(f"Coach note {note_id} not found.")
        self.db.delete(note)
        self.db.commit()

    # -- Phase 2 stubs -------------------------------------------------------------------

    def recommend_workload(self, club_id: str, player_id: str) -> dict:
        """Recommend next-week training load for a player.

        Intended data source: ``player_match_stats``
        (``playsight.db.models.PlayerMatchStats`` - minutes_tracked,
        distance_proxy_m, touches trends across recent matches) combined with
        attendance history from this module.

        # TODO(phase2): aggregate the player's recent PlayerMatchStats rows,
        # derive an acute:chronic load proxy, and map it to a recommended
        # intensity (with an honest confidence score; these stats are
        # heuristic proxies, not ground truth).
        """
        self._get_player(club_id, player_id)
        raise NotImplementedError(
            "TODO(phase2): workload recommendations from player_match_stats are not "
            "implemented yet (see docs/ROADMAP.md)."
        )

    # -- helpers ----------------------------------------------------------------------

    def _get_player(self, club_id: str, player_id: str) -> Player:
        player = self.db.get(Player, player_id)
        if player is None or player.club_id != club_id:
            raise NotFoundError(f"Player {player_id} not found.")
        return player
