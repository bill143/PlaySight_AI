"""Artifact model - tracks generated output files (reports, videos, exports)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.match import Match


class Artifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A generated output file: annotated video, report, highlight clip, export, etc."""

    __tablename__ = "artifacts"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    artifact_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    match: Mapped["Match"] = relationship("Match")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Artifact {self.artifact_type} {self.storage_key}>"


# Recognized artifact type constants used across pipeline/reporting/export modules.
ARTIFACT_TYPE_PLAYER_TRACKS = "player_tracks"
ARTIFACT_TYPE_PLAYER_IDENTITIES = "player_identities"
ARTIFACT_TYPE_PLAYER_STATS = "player_stats"
ARTIFACT_TYPE_MATCH_SUMMARY = "match_summary"
ARTIFACT_TYPE_ANNOTATED_VIDEO = "annotated_video"
ARTIFACT_TYPE_PLAYER_REPORT = "player_report"
ARTIFACT_TYPE_PLAYER_HIGHLIGHTS = "player_highlights"
ARTIFACT_TYPE_MATCH_SUMMARY_AUDIO = "match_summary_audio"
