"""Phase-1 database models (CONTRACTS.md section 5).

All Phase-1 core entities carry the tenancy column ``club_id`` (FK clubs.id,
indexed). Primary keys are 32-char uuid4 hex strings from
``playsight.core.ids.new_id``. All timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from playsight.core.ids import new_id
from playsight.db.base import Base


def utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def _default_period_config() -> dict:
    return {"periods": 2, "period_minutes": 45}


class Club(Base):
    """A tenant: sports club owning teams, users, matches, and artifacts."""

    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    teams: Mapped[list[Team]] = relationship(back_populates="club")


class Team(Base):
    """A team within a club."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sport: Mapped[str] = mapped_column(String(64), nullable=False)
    age_group: Mapped[str | None] = mapped_column(String(64), nullable=True)

    club: Mapped[Club] = relationship(back_populates="teams")


class User(Base):
    """An authenticated platform user (club-scoped)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    roles: Mapped[list[UserRole]] = relationship(back_populates="user")


class UserRole(Base):
    """A role assignment for a user, optionally scoped to a team."""

    __tablename__ = "user_roles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # playsight.auth.rbac.Role
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)

    user: Mapped[User] = relationship(back_populates="roles")


class RefreshToken(Base):
    """Server-side record of an issued refresh token (revocable)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Player(Base):
    """A rostered player."""

    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("teams.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Match(Base):
    """A recorded match to be analyzed."""

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("teams.id"), nullable=False, index=True
    )
    opponent: Mapped[str] = mapped_column(String(255), nullable=False)
    sport: Mapped[str] = mapped_column(String(64), nullable=False)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_config_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=_default_period_config
    )
    # created | processing | processed | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class VideoAsset(Base):
    """An ingested match video stored in object storage."""

    __tablename__ = "video_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # registered | ready | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ProcessingJob(Base):
    """A background processing job tracked through its lifecycle."""

    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=True, index=True
    )
    # analyze | highlights | export_audio | annotate | publish | report
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # queued | running | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(32), nullable=False, default=new_id)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlayerIdentity(Base):
    """Estimated (confidence-scored) identity for a track in a match.

    Identification uses jersey OCR and appearance embeddings only - never
    biometric face recognition. Results are estimates, not ground truth.
    """

    __tablename__ = "player_identities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=False, index=True
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=True
    )
    jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # ocr | reid | manual | unresolved
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="unresolved")


class MatchEvent(Base):
    """A heuristic event span detected in a match (see EventType taxonomy)."""

    __tablename__ = "match_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    t_start_s: Mapped[float] = mapped_column(Float, nullable=False)
    t_end_s: Mapped[float] = mapped_column(Float, nullable=False)
    player_identity_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("player_identities.id"), nullable=True
    )
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PlayerMatchStats(Base):
    """Aggregated per-player statistics for one match."""

    __tablename__ = "player_match_stats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=False, index=True
    )
    player_identity_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("player_identities.id"), nullable=False
    )
    minutes_tracked: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    distance_proxy_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    touches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tackles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turnovers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scoring_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 12x8 grid of floats (12 columns x 8 rows), stored row-major (8 lists of 12).
    heatmap_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class Artifact(Base):
    """A generated output file registered in object storage."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    match_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("matches.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class UploadRecord(Base):
    """An idempotent record of a (YouTube) platform upload attempt."""

    __tablename__ = "upload_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    artifact_id: Mapped[str] = mapped_column(String(32), ForeignKey("artifacts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="youtube")
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    # pending | uploading | succeeded | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    platform_video_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    category_id: Mapped[str] = mapped_column(String(16), nullable=False, default="17")  # Sports
    # private | unlisted | public
    privacy: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    error_log_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class AuditLog(Base):
    """Audit trail for sensitive mutations."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class ClubModule(Base):
    """Per-club feature flag override (module_key == flag key)."""

    __tablename__ = "club_modules"
    __table_args__ = (UniqueConstraint("club_id", "module_key", name="uq_club_modules_club_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
