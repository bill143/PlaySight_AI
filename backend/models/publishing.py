"""Publishing model - tracks upload/publish status to external platforms (e.g. YouTube)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.match import Match


class PublishRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "publish_records"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="youtube")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    privacy: Mapped[str] = mapped_column(String(50), nullable=False, default="private")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    match: Mapped["Match"] = relationship("Match")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PublishRecord {self.platform} status={self.status}>"
