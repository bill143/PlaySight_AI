"""Artifact response models (CONTRACTS.md section 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRead(BaseModel):
    """A generated output file registered in object storage."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    club_id: str
    match_id: str | None = None
    kind: str
    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict, validation_alias="meta_json")
