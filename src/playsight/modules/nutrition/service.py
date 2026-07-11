"""Nutrition service: profiles/templates/reminders CRUD + macro-target stub.

All module outputs carry ``NOT_MEDICAL_ADVICE_DISCLAIMER`` (attached at the
schema layer); nothing here is medical advice.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.db.models import Player
from playsight.modules.nutrition.models import AthleteProfile, HydrationReminder, MealTemplate
from playsight.modules.nutrition.schemas import (
    HydrationReminderCreate,
    HydrationReminderUpdate,
    MealTemplateCreate,
    ProfileCreate,
    ProfileUpdate,
)


def _apply_updates(entity: object, data: dict) -> None:
    """Assign ``data`` fields onto an ORM entity, unwrapping ``Enum`` values."""
    for field_name, value in data.items():
        setattr(entity, field_name, value.value if isinstance(value, Enum) else value)


class NutritionService:
    """Club-scoped nutrition management.

    Cross-club access surfaces as ``NotFoundError`` (HTTP 404). Macro-target
    recommendation is a Phase 2 stub.
    """

    def __init__(self, db: Session) -> None:
        """Bind the service to an open database session."""
        self.db = db

    # -- athlete profiles ----------------------------------------------------

    def create_profile(self, club_id: str, payload: ProfileCreate) -> AthleteProfile:
        """Create the nutrition profile for a player (one per player).

        Raises:
            NotFoundError: If the player does not exist in this club.
            ValidationFailed: If the player already has a profile.
        """
        self._get_player(club_id, payload.player_id)
        if self._profile_by_player(club_id, payload.player_id) is not None:
            raise ValidationFailed(f"Player {payload.player_id} already has a nutrition profile.")
        profile = AthleteProfile(
            club_id=club_id,
            player_id=payload.player_id,
            units=payload.units.value,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            dietary_flags_json=list(payload.dietary_flags_json),
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def list_profiles(self, club_id: str) -> list[AthleteProfile]:
        """List the club's athlete profiles."""
        stmt = (
            select(AthleteProfile)
            .where(AthleteProfile.club_id == club_id)
            .order_by(AthleteProfile.created_at)
        )
        return list(self.db.scalars(stmt))

    def get_profile(self, club_id: str, profile_id: str) -> AthleteProfile:
        """Return one profile, raising ``NotFoundError`` outside the club scope."""
        profile = self.db.get(AthleteProfile, profile_id)
        if profile is None or profile.club_id != club_id:
            raise NotFoundError(f"Athlete profile {profile_id} not found.")
        return profile

    def update_profile(
        self, club_id: str, profile_id: str, payload: ProfileUpdate
    ) -> AthleteProfile:
        """Apply a partial update to a profile."""
        profile = self.get_profile(club_id, profile_id)
        _apply_updates(profile, payload.model_dump(exclude_unset=True))
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete_profile(self, club_id: str, profile_id: str) -> None:
        """Delete a profile."""
        profile = self.get_profile(club_id, profile_id)
        self.db.delete(profile)
        self.db.commit()

    def _profile_by_player(self, club_id: str, player_id: str) -> AthleteProfile | None:
        stmt = select(AthleteProfile).where(
            AthleteProfile.club_id == club_id, AthleteProfile.player_id == player_id
        )
        return self.db.scalars(stmt).first()

    # -- meal templates ---------------------------------------------------------

    def create_template(self, club_id: str, payload: MealTemplateCreate) -> MealTemplate:
        """Create a meal template with macro targets for a day type."""
        template = MealTemplate(
            club_id=club_id,
            name=payload.name,
            day_type=payload.day_type.value,
            description=payload.description,
            macros_json=dict(payload.macros_json),
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def list_templates(self, club_id: str, *, day_type: str | None = None) -> list[MealTemplate]:
        """List meal templates, optionally filtered by day type."""
        stmt = select(MealTemplate).where(MealTemplate.club_id == club_id)
        if day_type is not None:
            stmt = stmt.where(MealTemplate.day_type == day_type)
        stmt = stmt.order_by(MealTemplate.name)
        return list(self.db.scalars(stmt))

    def get_template(self, club_id: str, template_id: str) -> MealTemplate:
        """Return one template, raising ``NotFoundError`` outside the club scope."""
        template = self.db.get(MealTemplate, template_id)
        if template is None or template.club_id != club_id:
            raise NotFoundError(f"Meal template {template_id} not found.")
        return template

    def delete_template(self, club_id: str, template_id: str) -> None:
        """Delete a meal template."""
        template = self.get_template(club_id, template_id)
        self.db.delete(template)
        self.db.commit()

    # -- hydration reminders ---------------------------------------------------------

    def create_reminder(self, club_id: str, payload: HydrationReminderCreate) -> HydrationReminder:
        """Create a hydration reminder (club-wide or bound to one player)."""
        if payload.player_id is not None:
            self._get_player(club_id, payload.player_id)
        reminder = HydrationReminder(
            club_id=club_id,
            player_id=payload.player_id,
            label=payload.label,
            time_of_day=payload.time_of_day,
            interval_minutes=payload.interval_minutes,
            enabled=payload.enabled,
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def list_reminders(
        self, club_id: str, *, player_id: str | None = None
    ) -> list[HydrationReminder]:
        """List hydration reminders, optionally for one player."""
        stmt = select(HydrationReminder).where(HydrationReminder.club_id == club_id)
        if player_id is not None:
            stmt = stmt.where(HydrationReminder.player_id == player_id)
        stmt = stmt.order_by(HydrationReminder.time_of_day)
        return list(self.db.scalars(stmt))

    def update_reminder(
        self, club_id: str, reminder_id: str, payload: HydrationReminderUpdate
    ) -> HydrationReminder:
        """Apply a partial update to a hydration reminder."""
        reminder = self._get_reminder(club_id, reminder_id)
        _apply_updates(reminder, payload.model_dump(exclude_unset=True))
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def delete_reminder(self, club_id: str, reminder_id: str) -> None:
        """Delete a hydration reminder."""
        reminder = self._get_reminder(club_id, reminder_id)
        self.db.delete(reminder)
        self.db.commit()

    def _get_reminder(self, club_id: str, reminder_id: str) -> HydrationReminder:
        reminder = self.db.get(HydrationReminder, reminder_id)
        if reminder is None or reminder.club_id != club_id:
            raise NotFoundError(f"Hydration reminder {reminder_id} not found.")
        return reminder

    # -- Phase 2 stubs -----------------------------------------------------------------

    def recommend_macro_targets(self, club_id: str, player_id: str) -> dict:
        """Suggest macro targets for a player from profile + activity data.

        # TODO(phase2): derive kcal/protein/carbs/fat targets from the
        # athlete's profile (weight, units) and recent training/match load,
        # always clearly labeled with NOT_MEDICAL_ADVICE_DISCLAIMER and never
        # positioned as medical or dietetic advice.
        """
        self._get_player(club_id, player_id)
        raise NotImplementedError(
            "TODO(phase2): macro-target recommendations are not implemented yet "
            "(see docs/ROADMAP.md)."
        )

    # -- helpers ---------------------------------------------------------------------

    def _get_player(self, club_id: str, player_id: str) -> Player:
        player = self.db.get(Player, player_id)
        if player is None or player.club_id != club_id:
            raise NotFoundError(f"Player {player_id} not found.")
        return player
