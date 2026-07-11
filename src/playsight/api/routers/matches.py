"""Match endpoints: CRUD, video ingest, job creation, and analysis reads.

Job-creating endpoints (``process``/``highlights``/``annotate``/``export/audio``)
persist a ``processing_jobs`` row and hand it to
``playsight.jobs.dispatch.dispatch_job`` -- the single dispatch entry point
(eager in-process execution in test/dev without redis, Celery otherwise).

Every query is tenancy-filtered: a match outside ``tenant.club_id`` answers
404 (CONTRACTS.md section 6).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from playsight.api.audit import write_audit
from playsight.api.deps import (
    Pagination,
    TenantContext,
    get_db,
    get_tenant,
    pagination_params,
)
from playsight.api.schemas.jobs import JobCreatedResponse
from playsight.api.schemas.matches import (
    HighlightsRequest,
    MatchCreate,
    MatchEventRead,
    MatchRead,
    PlayerIdentityRead,
    PlayerStatsRead,
    VideoAssetRead,
)
from playsight.auth.rbac import Role, require_roles
from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.ids import new_id
from playsight.core.logging import get_logger
from playsight.db.models import (
    Artifact,
    Match,
    MatchEvent,
    PlayerIdentity,
    PlayerMatchStats,
    ProcessingJob,
    Team,
    UploadRecord,
    VideoAsset,
)
from playsight.ingestion import ingest_video
from playsight.jobs.dispatch import dispatch_job
from playsight.storage import get_storage

log = get_logger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])

_require_writer = require_roles(Role.ADMIN, Role.COACH, Role.ANALYST)

#: Local landing directory for multipart uploads before storage ingest.
UPLOADS_ROOT = Path("data") / "uploads"


def _get_match(db: Session, tenant: TenantContext, match_id: str) -> Match:
    """Load a match within the tenant's club or raise 404."""
    match = db.get(Match, match_id)
    if match is None or match.club_id != tenant.club_id:
        raise NotFoundError(f"Match not found: {match_id}")
    return match


def _create_and_dispatch_job(
    request: Request,
    db: Session,
    tenant: TenantContext,
    *,
    kind: str,
    match_id: str | None,
    params: dict[str, Any],
) -> ProcessingJob:
    """Persist a queued processing job and dispatch it."""
    job = ProcessingJob(
        club_id=tenant.club_id,
        match_id=match_id,
        kind=kind,
        status="queued",
        progress=0.0,
        params_json=params,
        correlation_id=getattr(request.state, "correlation_id", None) or new_id(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log.info("job_created", job_id=job.id, kind=kind, match_id=match_id)
    dispatch_job(db, job)
    db.refresh(job)
    return job


@router.get("", response_model=list[MatchRead])
def list_matches(
    status: str | None = Query(default=None, description="Filter by match status."),
    team_id: str | None = Query(default=None, description="Filter by team."),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[Match]:
    """List the club's matches, newest first."""
    query = db.query(Match).filter(Match.club_id == tenant.club_id)
    if status is not None:
        query = query.filter(Match.status == status)
    if team_id is not None:
        query = query.filter(Match.team_id == team_id)
    return query.order_by(Match.created_at.desc()).offset(page.offset).limit(page.limit).all()


@router.post("", response_model=MatchRead, status_code=201)
def create_match(
    payload: MatchCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> Match:
    """Create a match (audit-logged)."""
    team = db.get(Team, payload.team_id)
    if team is None or team.club_id != tenant.club_id:
        raise NotFoundError(f"Team not found: {payload.team_id}")

    match = Match(
        club_id=tenant.club_id,
        team_id=payload.team_id,
        opponent=payload.opponent,
        sport=payload.sport,
        kickoff_at=payload.kickoff_at,
        venue=payload.venue,
        status="created",
    )
    if payload.period_config is not None:
        match.period_config_json = payload.period_config
    db.add(match)
    db.flush()
    write_audit(
        db,
        club_id=tenant.club_id,
        user_id=tenant.user.id if tenant.user else None,
        action="match.create",
        entity_type="match",
        entity_id=match.id,
        after={"team_id": match.team_id, "opponent": match.opponent, "sport": match.sport},
    )
    db.commit()
    db.refresh(match)
    return match


@router.get("/{match_id}", response_model=MatchRead)
def get_match(
    match_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Match:
    """Fetch one match."""
    return _get_match(db, tenant, match_id)


@router.delete("/{match_id}", status_code=204)
def delete_match(
    match_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> None:
    """Delete a match and all its derived rows (audit-logged)."""
    match = _get_match(db, tenant, match_id)
    before = {
        "team_id": match.team_id,
        "opponent": match.opponent,
        "sport": match.sport,
        "status": match.status,
    }

    artifact_ids = [
        row[0] for row in db.query(Artifact.id).filter(Artifact.match_id == match.id).all()
    ]
    if artifact_ids:
        db.query(UploadRecord).filter(UploadRecord.artifact_id.in_(artifact_ids)).delete(
            synchronize_session=False
        )
    db.query(MatchEvent).filter(MatchEvent.match_id == match.id).delete(synchronize_session=False)
    db.query(PlayerMatchStats).filter(PlayerMatchStats.match_id == match.id).delete(
        synchronize_session=False
    )
    db.query(PlayerIdentity).filter(PlayerIdentity.match_id == match.id).delete(
        synchronize_session=False
    )
    db.query(Artifact).filter(Artifact.match_id == match.id).delete(synchronize_session=False)
    db.query(VideoAsset).filter(VideoAsset.match_id == match.id).delete(synchronize_session=False)
    db.query(ProcessingJob).filter(ProcessingJob.match_id == match.id).delete(
        synchronize_session=False
    )
    db.delete(match)

    write_audit(
        db,
        club_id=tenant.club_id,
        user_id=tenant.user.id if tenant.user else None,
        action="match.delete",
        entity_type="match",
        entity_id=match_id,
        before=before,
    )
    db.commit()
    log.info("match_deleted", match_id=match_id)


@router.post("/{match_id}/videos", response_model=VideoAssetRead, status_code=201)
async def upload_video(
    match_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> VideoAsset:
    """Register a match video: multipart file upload OR JSON ``{"source_path"}``.

    Multipart bodies must carry a ``file`` part (or a ``source_path`` form
    field pointing at a server-local file). JSON bodies must be
    ``{"source_path": "..."}``. The video is probed, copied into object
    storage, and registered as a ``video_assets`` row.
    """
    match = _get_match(db, tenant, match_id)
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        form_source = form.get("source_path")
        if isinstance(upload, StarletteUploadFile):
            filename = Path(upload.filename or "upload.mp4").name
            dest_dir = UPLOADS_ROOT / match.id
            dest_dir.mkdir(parents=True, exist_ok=True)
            source = dest_dir / filename
            with source.open("wb") as out:
                shutil.copyfileobj(upload.file, out)
            await upload.close()
        elif isinstance(form_source, str) and form_source:
            source = Path(form_source)
        else:
            raise ValidationFailed(
                "Multipart body must include a 'file' upload or a 'source_path' field."
            )
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise ValidationFailed(
                "Body must be multipart/form-data or JSON with 'source_path'."
            ) from exc
        source_path = payload.get("source_path") if isinstance(payload, dict) else None
        if not isinstance(source_path, str) or not source_path:
            raise ValidationFailed("JSON body requires a non-empty 'source_path'.")
        source = Path(source_path)

    asset = ingest_video(source, match.id, get_storage(), db)
    return asset


@router.post("/{match_id}/process", response_model=JobCreatedResponse, status_code=202)
def process_match(
    match_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> JobCreatedResponse:
    """Run the full analysis pipeline for the match's registered video."""
    match = _get_match(db, tenant, match_id)
    asset = (
        db.query(VideoAsset)
        .filter(VideoAsset.match_id == match.id, VideoAsset.status == "ready")
        .order_by(VideoAsset.id)
        .first()
    )
    if asset is None:
        raise ValidationFailed(
            "No ready video is registered for this match; upload one via POST "
            f"/matches/{match_id}/videos first."
        )
    job = _create_and_dispatch_job(
        request,
        db,
        tenant,
        kind="analyze",
        match_id=match.id,
        params={"video_asset_id": asset.id, "storage_key": asset.storage_key},
    )
    return JobCreatedResponse(job_id=job.id)


@router.post("/{match_id}/highlights", response_model=JobCreatedResponse, status_code=202)
def create_highlights(
    match_id: str,
    payload: HighlightsRequest,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> JobCreatedResponse:
    """Build a per-player highlight reel (by identity id or raw track id)."""
    match = _get_match(db, tenant, match_id)
    params: dict[str, Any] = {}
    if payload.player_identity_id is not None:
        identity = db.get(PlayerIdentity, payload.player_identity_id)
        if identity is None or identity.club_id != tenant.club_id or identity.match_id != match.id:
            raise NotFoundError(f"Player identity not found: {payload.player_identity_id}")
        params["player_identity_id"] = identity.id
    if payload.track_id is not None:
        params["track_id"] = payload.track_id
    job = _create_and_dispatch_job(
        request, db, tenant, kind="highlights", match_id=match.id, params=params
    )
    return JobCreatedResponse(job_id=job.id)


@router.post("/{match_id}/annotate", response_model=JobCreatedResponse, status_code=202)
def annotate_match(
    match_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> JobCreatedResponse:
    """Render the annotated (boxes + track ids) match video."""
    match = _get_match(db, tenant, match_id)
    job = _create_and_dispatch_job(
        request, db, tenant, kind="annotate", match_id=match.id, params={}
    )
    return JobCreatedResponse(job_id=job.id)


@router.post("/{match_id}/export/audio", response_model=JobCreatedResponse, status_code=202)
def export_audio(
    match_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> JobCreatedResponse:
    """Render the spoken match-summary MP3."""
    match = _get_match(db, tenant, match_id)
    job = _create_and_dispatch_job(
        request, db, tenant, kind="export_audio", match_id=match.id, params={}
    )
    return JobCreatedResponse(job_id=job.id)


@router.get("/{match_id}/summary", response_model=dict[str, Any])
def get_summary(
    match_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the ``match_summary.json`` payload produced by the pipeline."""
    match = _get_match(db, tenant, match_id)
    artifact = (
        db.query(Artifact)
        .filter(
            Artifact.club_id == tenant.club_id,
            Artifact.match_id == match.id,
            Artifact.kind == "match_summary",
        )
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if artifact is None:
        raise NotFoundError(
            f"No summary available for match {match_id}; run POST /matches/{match_id}/process."
        )
    with get_storage().open_stream(artifact.storage_key) as stream:
        payload: dict[str, Any] = json.load(stream)
    return payload


@router.get("/{match_id}/events", response_model=list[MatchEventRead])
def list_events(
    match_id: str,
    event_type: str | None = Query(default=None, alias="type"),
    player: str | None = Query(default=None, description="Filter by player_identity_id."),
    period: int | None = Query(default=None, ge=1, description="1-based match period."),
    t0: float | None = Query(default=None, ge=0, description="Window start (seconds)."),
    t1: float | None = Query(default=None, ge=0, description="Window end (seconds)."),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[MatchEvent]:
    """List the match's events with optional type/player/period/time filters."""
    match = _get_match(db, tenant, match_id)
    query = db.query(MatchEvent).filter(
        MatchEvent.club_id == tenant.club_id, MatchEvent.match_id == match.id
    )
    if event_type is not None:
        query = query.filter(MatchEvent.event_type == event_type)
    if player is not None:
        query = query.filter(MatchEvent.player_identity_id == player)
    if period is not None:
        config = match.period_config_json or {}
        periods = int(config.get("periods", 2))
        period_minutes = float(config.get("period_minutes", 45))
        if period > periods:
            raise ValidationFailed(f"Match has {periods} periods; got period={period}.")
        p_start = (period - 1) * period_minutes * 60.0
        p_end = period * period_minutes * 60.0
        query = query.filter(MatchEvent.t_end_s >= p_start, MatchEvent.t_start_s < p_end)
    if t0 is not None:
        query = query.filter(MatchEvent.t_end_s >= t0)
    if t1 is not None:
        query = query.filter(MatchEvent.t_start_s <= t1)
    return query.order_by(MatchEvent.t_start_s).offset(page.offset).limit(page.limit).all()


@router.get("/{match_id}/stats", response_model=list[PlayerStatsRead])
def list_stats(
    match_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[PlayerStatsRead]:
    """Return per-player statistics with their (estimated) identities."""
    match = _get_match(db, tenant, match_id)
    identity_rows = (
        db.query(PlayerIdentity)
        .filter(PlayerIdentity.club_id == tenant.club_id, PlayerIdentity.match_id == match.id)
        .all()
    )
    identities = {identity.id: identity for identity in identity_rows}
    rows = (
        db.query(PlayerMatchStats)
        .filter(PlayerMatchStats.club_id == tenant.club_id, PlayerMatchStats.match_id == match.id)
        .order_by(PlayerMatchStats.minutes_tracked.desc())
        .all()
    )
    out: list[PlayerStatsRead] = []
    for row in rows:
        item = PlayerStatsRead.model_validate(row)
        identity = identities.get(row.player_identity_id)
        if identity is not None:
            item.identity = PlayerIdentityRead.model_validate(identity)
        out.append(item)
    return out


@router.get("/{match_id}/players/{identity_id}/report", response_model=dict[str, Any])
def get_player_report(
    match_id: str,
    identity_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the per-player JSON report for one (estimated) identity."""
    match = _get_match(db, tenant, match_id)
    identity = db.get(PlayerIdentity, identity_id)
    if identity is None or identity.club_id != tenant.club_id or identity.match_id != match.id:
        raise NotFoundError(f"Player identity not found: {identity_id}")

    player_ref = identity.player_id or f"track_{identity.track_id}"
    filename = f"player_report_{player_ref}.json"
    artifact = (
        db.query(Artifact)
        .filter(
            Artifact.club_id == tenant.club_id,
            Artifact.match_id == match.id,
            Artifact.kind == "player_report_json",
            Artifact.filename == filename,
        )
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if artifact is None:
        raise NotFoundError(
            f"No report available for identity {identity_id}; process the match first."
        )
    with get_storage().open_stream(artifact.storage_key) as stream:
        payload: dict[str, Any] = json.load(stream)
    return payload
