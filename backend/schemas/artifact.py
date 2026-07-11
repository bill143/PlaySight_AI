"""Artifact Pydantic schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    match_id: uuid.UUID
    artifact_type: str
    content_type: str


class ArtifactDownloadResponse(BaseModel):
    artifact_id: uuid.UUID
    download_url: str
    expires_in: int = 3600
