"""Club and Team models for multi-tenant support."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.user import User


class Club(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clubs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    sport: Mapped[str] = mapped_column(String(100), nullable=False, default="football")

    teams: Mapped[list["Team"]] = relationship("Team", back_populates="club", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship("User", back_populates="club")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Club {self.name}>"


class Team(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    club_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"))

    club: Mapped["Club"] = relationship("Club", back_populates="teams")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Team {self.name}>"
