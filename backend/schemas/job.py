"""Job status Pydantic schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class JobStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    match_id: uuid.UUID
    status: str
    progress: int
    current_stage: str
    error_message: str | None = None


class JobStatusEnum:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
