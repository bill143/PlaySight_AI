"""Nutrition module tables (CONTRACTS.md sections 5, 12, 18).

Athlete profiles (units preference), meal templates keyed by day type
(training/recovery) with macro targets, and hydration reminders. All outputs
carry the "not medical advice" disclaimer defined in ``schemas.py``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from playsight.core.ids import new_id
from playsight.db.base import Base
from playsight.db.models import utcnow


class UnitsPreference(StrEnum):
    """Measurement system preferred by the athlete."""

    METRIC = "metric"
    IMPERIAL = "imperial"


class DayType(StrEnum):
    """Meal-template day type."""

    TRAINING = "training"
    RECOVERY = "recovery"


class AthleteProfile(Base):
    """Per-player nutrition profile (one per player per club)."""

    __tablename__ = "athlete_profiles"
    __table_args__ = (
        UniqueConstraint("club_id", "player_id", name="uq_athlete_profiles_club_player"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    player_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=False, index=True
    )
    # metric | imperial (UnitsPreference)
    units: Mapped[str] = mapped_column(String(16), nullable=False, default="metric")
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Free-form dietary flags, e.g. ["vegetarian", "lactose_free"].
    dietary_flags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class MealTemplate(Base):
    """A reusable meal template with macro targets for a day type."""

    __tablename__ = "meal_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # training | recovery (DayType)
    day_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Macro targets: {"kcal": 2600, "protein_g": 140, "carbs_g": 320, "fat_g": 70}
    macros_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class HydrationReminder(Base):
    """A recurring hydration reminder (club-wide or per player)."""

    __tablename__ = "hydration_reminders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    player_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Drink water")
    # 24h local time "HH:MM" for the first reminder of the day.
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    # Optional repeat interval in minutes after time_of_day (None = once daily).
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
