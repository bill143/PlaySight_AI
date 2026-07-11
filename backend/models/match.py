"""Match, Video and ProcessingJob models."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin


class Match(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "matches"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sport: Mapped[str] = mapped_column(String(100), nullable=False, default="football")
    club_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    home_team: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    away_team: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    match_date: Mapped[str] = mapped_column(String(50), nullable=True, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    match_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    videos: Mapped[list["Video"]] = relationship("Video", back_populates="match", cascade="all, delete-orphan")
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="match", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Match {self.title}>"


class Video(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "videos"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="videos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Video {self.original_filename}>"


class ProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "processing_jobs"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str] = mapped_column(String(100), nullable=False, default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="jobs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProcessingJob {self.id} status={self.status}>"
