"""Match ingestion and retrieval endpoints."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import NotFoundError, ValidationFailedError
from backend.core.rbac import Permission
from backend.ingestion.metadata import parse_metadata
from backend.ingestion.uploader import VideoUploader
from backend.ingestion.validator import VideoValidator
from backend.models.match import Match, ProcessingJob, Video
from backend.models.user import User
from backend.schemas.match import MatchIngestResponse, MatchRead
from backend.workers.tasks.processing import process_match_task

router = APIRouter(prefix="/matches", tags=["matches"])

UPLOAD_STAGING_DIR = Path("data/uploads")


@router.post("/ingest", response_model=MatchIngestResponse, status_code=201)
async def ingest_match(
    db: DbSession,
    video: UploadFile = File(...),
    metadata: str = Form(...),
    _user: User = Depends(require_permission(Permission.MATCH_CREATE)),
) -> MatchIngestResponse:
    """Upload a match video plus metadata, persist it, and enqueue processing."""
    parsed_metadata = parse_metadata(metadata)

    validator = VideoValidator()
    validation = validator.validate_upload(video.filename or "upload.mp4", size_bytes=video.size or 0)
    validation.raise_if_invalid()

    match = Match(
        title=parsed_metadata.title or (video.filename or "Untitled match"),
        sport=parsed_metadata.sport,
        home_team=parsed_metadata.home_team,
        away_team=parsed_metadata.away_team,
        match_date=parsed_metadata.match_date,
        club_id=parsed_metadata.club_id,
        match_metadata=parsed_metadata.extra,
        status="queued",
    )
    db.add(match)
    await db.flush()

    UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_STAGING_DIR / f"{match.id}_{video.filename}"
    contents = await video.read()
    local_path.write_bytes(contents)

    uploader = VideoUploader()
    storage_key = uploader.upload_video(local_path, str(match.id), video.filename or "upload.mp4")

    db.add(
        Video(
            match_id=match.id,
            storage_key=storage_key,
            original_filename=video.filename or "upload.mp4",
        )
    )

    job = ProcessingJob(match_id=match.id, status="queued", progress=0, current_stage="queued")
    db.add(job)
    await db.flush()
    await db.commit()

    task_metadata = parsed_metadata.to_dict()
    task_metadata["match_id"] = str(match.id)
    async_result = process_match_task.delay(str(match.id), str(local_path), task_metadata, str(job.id))

    job.celery_task_id = async_result.id
    await db.commit()

    return MatchIngestResponse(match_id=match.id, job_id=job.id, status=job.status)


@router.get("", response_model=list[MatchRead])
async def list_matches(
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(require_permission(Permission.MATCH_READ)),
) -> list[Match]:
    """List matches, most recent first."""
    result = await db.execute(select(Match).order_by(Match.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all())


@router.get("/{match_id}", response_model=MatchRead)
async def get_match(
    match_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.MATCH_READ)),
) -> Match:
    """Get details for a single match."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundError(f"Match {match_id} not found")
    return match


def _validate_metadata_or_raise(raw: str) -> None:
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationFailedError(f"Invalid metadata JSON: {exc}") from exc
