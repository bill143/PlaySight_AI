"""Processing-job response models (CONTRACTS.md sections 11, 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobRead(BaseModel):
    """A processing job: lifecycle state, progress, and result payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    kind: str
    status: str
    progress: float
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = Field(default=None, validation_alias="result_json")
    match_id: str | None = None
    correlation_id: str | None = None


class JobCreatedResponse(BaseModel):
    """Returned by every endpoint that enqueues a job."""

    job_id: str
