"""Celery task definitions (CONTRACTS.md section 11).

Each task is a thin wrapper around a domain function: it loads the
``processing_jobs`` row, marks it running (``started_at``), binds the job's
``correlation_id`` to the logging context, runs the domain function with a
DB-persisting progress callback, and records ``succeeded``/``failed`` with
``result_json``/``error``. Transient failures (external services, network)
are retried with exponential backoff up to :data:`MAX_RETRIES` times; domain
errors fail immediately.

The retry loop lives inside the task body (not Celery's retry machinery) so
behavior is identical in eager in-process mode and under a real worker, and
importing this module never requires a live redis broker.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.config.settings import get_settings
from playsight.core.errors import ExternalServiceError, NotFoundError, ValidationFailed
from playsight.core.logging import bind_correlation_id, clear_correlation_id, get_logger
from playsight.core.types import EventSpan, IdentityResult
from playsight.db.models import Artifact, MatchEvent, PlayerIdentity, ProcessingJob, utcnow
from playsight.db.session import SessionLocal, get_engine
from playsight.jobs.celery_app import app
from playsight.pipeline.artifacts import outputs_dir, register_artifact, resolve_match_video
from playsight.storage import get_storage

log = get_logger(__name__)

#: Maximum retries for transient failures (CONTRACTS.md section 11).
MAX_RETRIES = 3

#: Base delay of the exponential backoff (seconds): 2, 4, 8.
BACKOFF_BASE_S = 2.0

#: Exceptions treated as transient (worth retrying with backoff).
TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    ExternalServiceError,
    ConnectionError,
    TimeoutError,
)

#: Minimum progress delta persisted to the DB (avoids commit spam).
_PROGRESS_EPSILON = 0.01

_ProgressCb = Callable[[float], None]
_Runner = Callable[[Session, ProcessingJob, _ProgressCb], dict[str, Any]]


class _JobProgress:
    """Progress callback persisting ``processing_jobs.progress`` (throttled)."""

    def __init__(self, db: Session, job: ProcessingJob) -> None:
        self._db = db
        self._job = job

    def __call__(self, value: float) -> None:
        """Persist ``value`` (clamped to [0, 1]) when it moved enough to matter."""
        clamped = min(1.0, max(0.0, float(value)))
        current = float(self._job.progress or 0.0)
        if clamped < 1.0 and clamped - current < _PROGRESS_EPSILON:
            return
        self._job.progress = clamped
        try:
            self._db.commit()
        except Exception as exc:  # progress must never break the job itself
            self._db.rollback()
            log.warning("job_progress_commit_failed", job_id=self._job.id, error=str(exc))


def _open_session() -> Session:
    """Return a new DB session bound to the process engine."""
    get_engine()
    return SessionLocal()


def _execute_job(job_id: str, runner: _Runner) -> dict[str, Any]:
    """Drive one job through its lifecycle with bounded transient retries.

    Args:
        job_id: ``processing_jobs.id`` to execute.
        runner: Domain function ``(db, job, progress_cb) -> result dict``.

    Returns:
        ``{"job_id", "status", ...}`` — the terminal outcome. Errors are
        captured into the job row instead of propagating so the job state is
        always the source of truth.
    """
    db = _open_session()
    try:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            log.error("job_not_found", job_id=job_id)
            return {"job_id": job_id, "status": "not_found"}

        bind_correlation_id(job.correlation_id)
        job.status = "running"
        job.started_at = utcnow()
        job.error = None
        db.commit()
        log.info("job_started", job_id=job.id, kind=job.kind, match_id=job.match_id)

        progress = _JobProgress(db, job)
        attempt = 0
        while True:
            try:
                result = runner(db, job, progress)
            except TRANSIENT_ERRORS as exc:
                db.rollback()
                attempt += 1
                job = db.get(ProcessingJob, job_id)
                if job is None:  # pragma: no cover - row deleted mid-run
                    return {"job_id": job_id, "status": "not_found"}
                if attempt > MAX_RETRIES:
                    return _fail(db, job, exc)
                job.retries = attempt
                db.commit()
                delay = BACKOFF_BASE_S * (2 ** (attempt - 1))
                log.warning(
                    "job_retrying",
                    job_id=job.id,
                    kind=job.kind,
                    attempt=attempt,
                    max_retries=MAX_RETRIES,
                    delay_s=delay,
                    error=f"{type(exc).__name__}: {exc}",
                )
                time.sleep(delay)
            except Exception as exc:
                db.rollback()
                job = db.get(ProcessingJob, job_id)
                if job is None:  # pragma: no cover - row deleted mid-run
                    return {"job_id": job_id, "status": "not_found"}
                return _fail(db, job, exc)
            else:
                job.status = "succeeded"
                job.progress = 1.0
                job.result_json = result
                job.finished_at = utcnow()
                db.commit()
                log.info("job_succeeded", job_id=job.id, kind=job.kind)
                return {"job_id": job.id, "status": "succeeded", "result": result}
    finally:
        clear_correlation_id()
        db.close()


def _fail(db: Session, job: ProcessingJob, exc: Exception) -> dict[str, Any]:
    """Mark a job failed with the exception message; returns the outcome dict."""
    job.status = "failed"
    job.error = f"{type(exc).__name__}: {exc}"
    job.finished_at = utcnow()
    db.commit()
    log.error("job_failed", job_id=job.id, kind=job.kind, error=job.error)
    return {"job_id": job.id, "status": "failed", "error": job.error}


def _require_match_id(job: ProcessingJob) -> str:
    """Return the job's match id (params fallback) or raise ValidationFailed."""
    match_id = job.match_id or (job.params_json or {}).get("match_id")
    if not match_id:
        raise ValidationFailed(f"job {job.id} ({job.kind}) has no match_id")
    return str(match_id)


def _job_video_path(db: Session, storage: Any, job: ProcessingJob, match_id: str) -> Path:
    """Resolve the source video: explicit ``params_json['video_path']`` or the asset."""
    video_path = (job.params_json or {}).get("video_path")
    if video_path and Path(video_path).is_file():
        return Path(video_path)
    return resolve_match_video(db, storage, match_id)


# --- Domain runners ------------------------------------------------------------------


def _run_analysis_job(db: Session, job: ProcessingJob, progress: _ProgressCb) -> dict[str, Any]:
    """Run the full match analysis pipeline for the job's match."""
    from playsight.pipeline import run_match_pipeline

    settings = get_settings()
    match_id = _require_match_id(job)
    storage = get_storage(settings)
    video_path = _job_video_path(db, storage, job, match_id)
    result = run_match_pipeline(
        match_id,
        video_path,
        db_session_factory=SessionLocal,
        settings=settings,
        progress_cb=progress,
    )
    return {
        "match_id": result.match_id,
        "artifact_paths": result.artifact_paths,
        "counts": result.counts,
    }


def _run_highlights_job(db: Session, job: ProcessingJob, progress: _ProgressCb) -> dict[str, Any]:
    """Build a per-player highlight reel and register it as an artifact."""
    from playsight.highlights import build_player_highlights

    settings = get_settings()
    match_id = _require_match_id(job)
    storage = get_storage(settings)
    params = job.params_json or {}

    identity = _load_identity(db, match_id, params)
    events = _load_events(db, match_id)
    video_path = _job_video_path(db, storage, job, match_id)
    progress(0.2)

    slug = identity.player_id or f"track_{identity.track_id}"
    out_path = outputs_dir(match_id) / f"player_highlights_{slug}.mp4"
    padding_s = float(params.get("padding_s", 1.5))
    build_player_highlights(video_path, events, identity, out_path, padding_s=padding_s)
    progress(0.9)

    artifact = register_artifact(
        db,
        storage,
        club_id=job.club_id,
        match_id=match_id,
        kind="player_highlights",
        local_path=out_path,
        meta={
            "player_id": identity.player_id,
            "track_id": int(identity.track_id),
            "jersey_number": identity.jersey_number,
            "events": sum(1 for e in events if e.track_id == identity.track_id),
        },
    )
    return {"artifact_id": artifact.id, "kind": "player_highlights", "path": str(out_path)}


def _run_annotate_job(db: Session, job: ProcessingJob, progress: _ProgressCb) -> dict[str, Any]:
    """Render the annotated match video and register it as an artifact."""
    from playsight.export import render_annotated_video

    settings = get_settings()
    match_id = _require_match_id(job)
    storage = get_storage(settings)

    tracks_df = _load_tracks_df(db, storage, match_id)
    identities = _load_identities(db, match_id)
    video_path = _job_video_path(db, storage, job, match_id)
    progress(0.15)

    out_path = outputs_dir(match_id) / "annotated_video.mp4"
    render_annotated_video(video_path, tracks_df, identities, out_path, settings=settings)
    progress(0.9)

    artifact = register_artifact(
        db,
        storage,
        club_id=job.club_id,
        match_id=match_id,
        kind="annotated_video",
        local_path=out_path,
        meta={"tracks": len(identities)},
    )
    return {"artifact_id": artifact.id, "kind": "annotated_video", "path": str(out_path)}


def _run_export_audio_job(db: Session, job: ProcessingJob, progress: _ProgressCb) -> dict[str, Any]:
    """Render the audio match summary MP3 and register it as an artifact."""
    from playsight.export import render_audio_summary_detailed

    settings = get_settings()
    match_id = _require_match_id(job)
    storage = get_storage(settings)

    summary = _load_match_summary(db, storage, match_id)
    progress(0.2)

    out_path = outputs_dir(match_id) / "match_summary_audio.mp3"
    audio_meta = render_audio_summary_detailed(summary, out_path)
    progress(0.9)

    artifact = register_artifact(
        db,
        storage,
        club_id=job.club_id,
        match_id=match_id,
        kind="match_audio",
        local_path=out_path,
        meta={
            "tts_engine": audio_meta.get("engine"),
            "transcript": audio_meta.get("transcript_path"),
        },
    )
    return {
        "artifact_id": artifact.id,
        "kind": "match_audio",
        "path": str(out_path),
        "tts_engine": audio_meta.get("engine"),
    }


def _run_publish_job(db: Session, job: ProcessingJob, progress: _ProgressCb) -> dict[str, Any]:
    """Publish an artifact to YouTube via its ``upload_records`` row."""
    from playsight.integrations.youtube import publish_artifact

    settings = get_settings()
    storage = get_storage(settings)
    upload_record_id = (job.params_json or {}).get("upload_record_id")
    if not upload_record_id:
        raise ValidationFailed(f"publish job {job.id} has no params_json['upload_record_id']")

    record = publish_artifact(
        db,
        storage,
        str(upload_record_id),
        settings=settings,
        progress_cb=progress,
    )
    return {
        "upload_record_id": record.id,
        "status": record.status,
        "platform_video_id": record.platform_video_id,
        "url": record.url,
    }


# --- Loaders shared by the domain runners --------------------------------------------


def _load_identity(db: Session, match_id: str, params: dict[str, Any]) -> IdentityResult:
    """Resolve the target identity from ``player_identity_id`` or ``track_id`` params."""
    identity_id = params.get("player_identity_id")
    if identity_id:
        row = db.get(PlayerIdentity, str(identity_id))
        if row is None or row.match_id != match_id:
            raise NotFoundError(f"player identity not found for match {match_id}: {identity_id}")
        return _identity_from_row(row)

    track_id = params.get("track_id")
    if track_id is None:
        raise ValidationFailed(
            "highlights job needs params_json['player_identity_id'] or ['track_id']"
        )
    track = int(track_id)
    stmt = select(PlayerIdentity).where(
        PlayerIdentity.match_id == match_id, PlayerIdentity.track_id == track
    )
    row = db.execute(stmt).scalars().first()
    if row is not None:
        return _identity_from_row(row)
    return IdentityResult(
        track_id=track, jersey_number=None, player_id=None, confidence=0.0, method="unresolved"
    )


def _identity_from_row(row: PlayerIdentity) -> IdentityResult:
    """Convert a ``player_identities`` row to the pipeline dataclass."""
    return IdentityResult(
        track_id=int(row.track_id),
        jersey_number=row.jersey_number,
        player_id=row.player_id,
        confidence=float(row.confidence),
        method=row.method,
    )


def _load_identities(db: Session, match_id: str) -> list[IdentityResult]:
    """Load every identity of a match as pipeline dataclasses (sorted by track)."""
    stmt = (
        select(PlayerIdentity)
        .where(PlayerIdentity.match_id == match_id)
        .order_by(PlayerIdentity.track_id)
    )
    return [_identity_from_row(row) for row in db.execute(stmt).scalars()]


def _load_events(db: Session, match_id: str) -> list[EventSpan]:
    """Load the match's persisted events as pipeline dataclasses."""
    stmt = select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.t_start_s)
    return [
        EventSpan(
            event_type=row.event_type,
            t_start_s=float(row.t_start_s),
            t_end_s=float(row.t_end_s),
            track_id=row.track_id,
            confidence=float(row.confidence),
            meta=dict(row.meta_json or {}),
        )
        for row in db.execute(stmt).scalars()
    ]


def _load_tracks_df(db: Session, storage: Any, match_id: str) -> pd.DataFrame:
    """Load ``player_tracks.parquet`` (local file, else the stored artifact)."""
    local_path = outputs_dir(match_id) / "player_tracks.parquet"
    if not local_path.is_file():
        artifact = _find_artifact(db, match_id, "player_tracks")
        storage.download_to(artifact.storage_key, local_path)
    return pd.read_parquet(local_path)


def _load_match_summary(db: Session, storage: Any, match_id: str) -> dict[str, Any]:
    """Load ``match_summary.json`` (local file, else the stored artifact)."""
    local_path = outputs_dir(match_id) / "match_summary.json"
    if not local_path.is_file():
        artifact = _find_artifact(db, match_id, "match_summary")
        storage.download_to(artifact.storage_key, local_path)
    with local_path.open("r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise ValidationFailed(f"match summary for {match_id} is not a JSON object")
    return loaded


def _find_artifact(db: Session, match_id: str, kind: str) -> Artifact:
    """Return the newest artifact row of ``kind`` for a match or raise NotFoundError."""
    stmt = (
        select(Artifact)
        .where(Artifact.match_id == match_id, Artifact.kind == kind)
        .order_by(Artifact.created_at.desc())
    )
    artifact = db.execute(stmt).scalars().first()
    if artifact is None:
        raise NotFoundError(
            f"no '{kind}' artifact for match {match_id}; run the analysis pipeline first"
        )
    return artifact


# --- Celery tasks (CONTRACTS.md section 11) ------------------------------------------


@app.task(name="playsight.jobs.tasks.run_analysis")
def run_analysis(job_id: str) -> dict[str, Any]:
    """Run the full match analysis pipeline for an ``analyze`` job.

    Args:
        job_id: ``processing_jobs.id`` of a job with ``kind='analyze'``.
    """
    return _execute_job(job_id, _run_analysis_job)


@app.task(name="playsight.jobs.tasks.run_highlights")
def run_highlights(job_id: str) -> dict[str, Any]:
    """Build a per-player highlight reel for a ``highlights`` job.

    Args:
        job_id: ``processing_jobs.id`` of a job with ``kind='highlights'``.
    """
    return _execute_job(job_id, _run_highlights_job)


@app.task(name="playsight.jobs.tasks.run_annotate")
def run_annotate(job_id: str) -> dict[str, Any]:
    """Render the annotated match video for an ``annotate`` job.

    Args:
        job_id: ``processing_jobs.id`` of a job with ``kind='annotate'``.
    """
    return _execute_job(job_id, _run_annotate_job)


@app.task(name="playsight.jobs.tasks.run_export_audio")
def run_export_audio(job_id: str) -> dict[str, Any]:
    """Render the audio match summary for an ``export_audio`` job.

    Args:
        job_id: ``processing_jobs.id`` of a job with ``kind='export_audio'``.
    """
    return _execute_job(job_id, _run_export_audio_job)


@app.task(name="playsight.jobs.tasks.run_publish_youtube")
def run_publish_youtube(job_id: str) -> dict[str, Any]:
    """Publish an artifact to YouTube for a ``publish`` job.

    Args:
        job_id: ``processing_jobs.id`` of a job with ``kind='publish'`` and
            ``params_json['upload_record_id']`` set.
    """
    return _execute_job(job_id, _run_publish_job)
