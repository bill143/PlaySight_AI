"""Match analysis pipeline orchestrator (CONTRACTS.md sections 7 and 9).

``run_match_pipeline`` drives the full vision pipeline for one match video:

ingest -> iterate frames (stride / max_frames) -> detect -> track ->
tracks dataframe + ``player_tracks.parquet`` -> identify (+ roster mapping) ->
persist ``player_identities`` + CSV -> events -> persist ``match_events`` ->
stats -> persist ``player_match_stats`` + CSV -> ``match_summary.json`` ->
per-identity player reports (JSON + PDF) -> register every artifact in the
``artifacts`` table AND object storage -> update ``matches.status``.

The match is marked ``processing`` at the start, ``processed`` on success, and
``failed`` on any error (which is re-raised for the job layer).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from playsight.analytics import compute_events, compute_player_stats
from playsight.config.settings import Settings
from playsight.core.errors import NotFoundError
from playsight.core.logging import get_logger
from playsight.core.types import (
    EventSpan,
    IdentityResult,
    PipelineResult,
    PlayerStatsRow,
    VideoInfo,
)
from playsight.db.models import (
    Match,
    MatchEvent,
    Player,
    PlayerIdentity,
    PlayerMatchStats,
    Team,
)
from playsight.detection import create_detector
from playsight.export import render_annotated_video
from playsight.identification import identify_tracks, ocr_engine_name
from playsight.ingestion import ingest_video, iter_frames
from playsight.pipeline.artifacts import outputs_dir, register_artifact
from playsight.reporting import (
    build_match_summary,
    build_player_report,
    write_identities_csv,
    write_match_summary_json,
    write_player_report_json,
    write_player_report_pdf,
    write_player_stats_csv,
)
from playsight.storage import get_storage
from playsight.tracking import create_tracker

log = get_logger(__name__)

#: Tracks dataframe schema (CONTRACTS.md section 7), in column order.
TRACKS_DTYPES: dict[str, str] = {
    "frame_index": "int64",
    "t_s": "float64",
    "track_id": "int64",
    "x1": "float64",
    "y1": "float64",
    "x2": "float64",
    "y2": "float64",
    "confidence": "float64",
}

PLAYER_TRACKS_PARQUET = "player_tracks.parquet"

# Progress checkpoints (fractions of the whole pipeline).
_P_INGESTED = 0.08
_P_TRACKED = 0.55
_P_TRACKS_WRITTEN = 0.60
_P_IDENTIFIED = 0.70
_P_EVENTS = 0.78
_P_STATS = 0.85
_P_SUMMARY = 0.88
_P_ANNOTATED = 0.94
_P_REPORTS = 0.97


class _Progress:
    """Monotonic, clamped, never-raising wrapper around ``progress_cb``."""

    def __init__(self, cb: Callable[[float], None] | None) -> None:
        self._cb = cb
        self._last = -1.0

    def __call__(self, value: float) -> None:
        """Report ``value`` (clamped to [0, 1]); regressions and errors are ignored."""
        if self._cb is None:
            return
        clamped = min(1.0, max(0.0, float(value)))
        if clamped <= self._last:
            return
        self._last = clamped
        try:
            self._cb(clamped)
        except Exception as exc:  # never let a UI callback break the pipeline
            log.warning("progress_callback_failed", error=str(exc))


def run_match_pipeline(
    match_id: str,
    video_path: str | Path,
    *,
    db_session_factory: Callable[[], Session],
    settings: Settings,
    progress_cb: Callable[[float], None] | None = None,
) -> PipelineResult:
    """Run the full analysis pipeline for one match video.

    Args:
        match_id: Id of an existing ``matches`` row.
        video_path: Local path of the source video.
        db_session_factory: Zero-arg callable returning a SQLAlchemy session
            (e.g. ``playsight.db.session.SessionLocal``); the pipeline opens
            and closes its own session.
        settings: Application settings (``pipeline.frame_stride`` /
            ``pipeline.max_frames`` / ``pipeline.detection_conf`` apply).
        progress_cb: Optional callback receiving overall progress in [0, 1]
            at sensible checkpoints.

    Returns:
        A :class:`PipelineResult` with local artifact paths keyed by artifact
        kind (per-player reports use ``"<kind>:<player_id>"`` keys) and
        summary ``counts`` (tracks / identified / events).

    Raises:
        NotFoundError: The match row or video file does not exist.
        PlaySightError: Any stage failure; the match is marked ``failed``
            before the error propagates.
    """
    progress = _Progress(progress_cb)
    db = db_session_factory()
    try:
        match = db.get(Match, match_id)
        if match is None:
            raise NotFoundError(f"match not found: {match_id}")
        match.status = "processing"
        db.commit()
        log.info("pipeline_started", match_id=match_id, video_path=str(video_path))
        progress(0.01)

        try:
            result = _execute(db, match, Path(video_path), settings, progress)
        except Exception as exc:
            db.rollback()
            _mark_match_failed(db, match_id, exc)
            raise

        match = db.get(Match, match_id)
        if match is not None:
            match.status = "processed"
            db.commit()
        progress(1.0)
        log.info("pipeline_finished", match_id=match_id, counts=result.counts)
        return result
    finally:
        db.close()


def _mark_match_failed(db: Session, match_id: str, exc: Exception) -> None:
    """Best-effort ``matches.status = 'failed'`` after a pipeline error."""
    try:
        match = db.get(Match, match_id)
        if match is not None:
            match.status = "failed"
            db.commit()
    except Exception as inner:  # pragma: no cover - double-fault safety net
        log.error("match_failed_status_update_failed", match_id=match_id, error=str(inner))
    log.error(
        "pipeline_failed",
        match_id=match_id,
        error=f"{type(exc).__name__}: {exc}",
    )


def _execute(
    db: Session,
    match: Match,
    video: Path,
    settings: Settings,
    progress: _Progress,
) -> PipelineResult:
    """Run every pipeline stage for ``match`` and return the PipelineResult."""
    storage = get_storage(settings)
    out_dir = outputs_dir(match.id)
    artifact_paths: dict[str, str] = {}

    # 1. Ingest: probe + copy to object storage + video_assets row.
    asset = ingest_video(video, match.id, storage, db)
    frame_count = int((asset.meta_json or {}).get("frame_count") or 0)
    video_info = VideoInfo(
        duration_s=float(asset.duration_s),
        fps=float(asset.fps),
        width=int(asset.width),
        height=int(asset.height),
        frame_count=frame_count,
    )
    progress(_P_INGESTED)

    # 2. Detect + track over strided frames.
    detector = create_detector(settings)
    tracker = create_tracker(settings)
    tracks_df = _detect_and_track(video, video_info, detector, tracker, settings, progress)

    # 3. player_tracks.parquet
    parquet_path = out_dir / PLAYER_TRACKS_PARQUET
    tracks_df.to_parquet(parquet_path, index=False)
    _register(
        db,
        storage,
        match,
        "player_tracks",
        parquet_path,
        artifact_paths,
        meta={"rows": int(len(tracks_df)), "detector": detector.engine, "tracker": tracker.engine},
    )
    progress(_P_TRACKS_WRITTEN)

    # 4. Identify tracks and map jersey numbers onto the roster.
    identities = identify_tracks(video, tracks_df, settings)
    _resolve_roster_players(db, match, identities)
    _clear_previous_results(db, match.id)
    identity_row_ids = _persist_identities(db, match, identities)
    identities_csv = write_identities_csv(identities, out_dir)
    _register(db, storage, match, "player_identities", identities_csv, artifact_paths)
    progress(_P_IDENTIFIED)

    # 5. Events.
    events = compute_events(tracks_df, video_info, settings)
    _persist_events(db, match, events, identity_row_ids)
    progress(_P_EVENTS)

    # 6. Stats.
    stats = compute_player_stats(tracks_df, identities, events, video_info)
    _persist_stats(db, match, stats, identity_row_ids)
    stats_csv = write_player_stats_csv(stats, out_dir)
    _register(db, storage, match, "player_stats", stats_csv, artifact_paths)
    progress(_P_STATS)

    # 7. Match summary.
    team = db.get(Team, match.team_id) if match.team_id else None
    summary = build_match_summary(
        match.id,
        video_info,
        identities,
        events,
        stats,
        teams={"home": team.name if team else "Home", "away": match.opponent or "Away"},
        engine={
            "detector": detector.engine,
            "tracker": tracker.engine,
            "ocr": ocr_engine_name(settings),
        },
    )
    summary_path = write_match_summary_json(summary, out_dir)
    _register(db, storage, match, "match_summary", summary_path, artifact_paths)
    progress(_P_SUMMARY)

    # 8. Annotated match video (boxes + labels + clock), per section 9.
    annotated_path = out_dir / "annotated_video.mp4"
    render_annotated_video(video, tracks_df, identities, annotated_path, settings=settings)
    _register(
        db,
        storage,
        match,
        "annotated_video",
        annotated_path,
        artifact_paths,
        meta={"tracks": len(identities)},
    )
    progress(_P_ANNOTATED)

    # 9. Per-identity player reports (JSON + PDF).
    _write_player_reports(db, storage, match, identities, stats, events, out_dir, artifact_paths)
    progress(_P_REPORTS)

    counts = {
        "tracks": int(summary["counts"]["tracks"]),
        "identified": int(summary["counts"]["identified"]),
        "events": int(summary["counts"]["events"]),
    }
    return PipelineResult(match_id=match.id, artifact_paths=artifact_paths, counts=counts)


def _detect_and_track(
    video: Path,
    video_info: VideoInfo,
    detector: Any,
    tracker: Any,
    settings: Settings,
    progress: _Progress,
) -> pd.DataFrame:
    """Run detection + tracking over strided frames and return the tracks dataframe."""
    stride = max(1, int(settings.pipeline.frame_stride))
    max_frames = settings.pipeline.max_frames
    expected = 0
    if video_info.frame_count > 0:
        expected = (video_info.frame_count + stride - 1) // stride
    if max_frames is not None:
        expected = min(expected, int(max_frames)) if expected else int(max_frames)

    rows: list[tuple[int, float, int, float, float, float, float, float]] = []
    processed = 0
    for frame_index, t_s, frame in iter_frames(video, stride=stride, max_frames=max_frames):
        detections = detector.detect(frame, frame_index, t_s)
        tracked = tracker.update(detections, frame)
        for box in tracked:
            rows.append(
                (
                    int(box.frame_index),
                    float(box.t_s),
                    int(box.track_id),
                    float(box.x1),
                    float(box.y1),
                    float(box.x2),
                    float(box.y2),
                    float(box.confidence),
                )
            )
        processed += 1
        if expected > 0:
            fraction = min(1.0, processed / expected)
            progress(_P_INGESTED + (_P_TRACKED - _P_INGESTED) * fraction)

    df = pd.DataFrame(rows, columns=list(TRACKS_DTYPES))
    df = df.astype(TRACKS_DTYPES)
    log.info(
        "detection_tracking_finished",
        frames_processed=processed,
        track_rows=len(df),
        tracks=int(df["track_id"].nunique()) if not df.empty else 0,
        stride=stride,
    )
    progress(_P_TRACKED)
    return df


def _resolve_roster_players(db: Session, match: Match, identities: list[IdentityResult]) -> None:
    """Map estimated jersey numbers to roster ``players.id`` (in place).

    A number maps only when exactly one player of the match's team wears it;
    ambiguous or unknown numbers keep ``player_id=None``.
    """
    stmt = select(Player).where(
        Player.club_id == match.club_id,
        Player.team_id == match.team_id,
        Player.jersey_number.is_not(None),
    )
    by_number: dict[int, list[str]] = {}
    for player in db.execute(stmt).scalars():
        by_number.setdefault(int(player.jersey_number or 0), []).append(player.id)

    resolved = 0
    for identity in identities:
        if identity.jersey_number is None:
            continue
        candidates = by_number.get(int(identity.jersey_number), [])
        if len(candidates) == 1:
            identity.player_id = candidates[0]
            resolved += 1
    log.info(
        "roster_players_resolved",
        match_id=match.id,
        identities=len(identities),
        roster_matched=resolved,
    )


def _clear_previous_results(db: Session, match_id: str) -> None:
    """Delete stats/events/identities from an earlier run so reprocessing is idempotent."""
    db.execute(delete(PlayerMatchStats).where(PlayerMatchStats.match_id == match_id))
    db.execute(delete(MatchEvent).where(MatchEvent.match_id == match_id))
    db.execute(delete(PlayerIdentity).where(PlayerIdentity.match_id == match_id))
    db.commit()


def _persist_identities(
    db: Session, match: Match, identities: list[IdentityResult]
) -> dict[int, str]:
    """Insert ``player_identities`` rows; returns ``{track_id: row_id}``."""
    row_ids: dict[int, str] = {}
    for identity in identities:
        row = PlayerIdentity(
            club_id=match.club_id,
            match_id=match.id,
            track_id=int(identity.track_id),
            player_id=identity.player_id,
            jersey_number=identity.jersey_number,
            confidence=float(identity.confidence),
            method=identity.method,
        )
        db.add(row)
        db.flush()
        row_ids[int(identity.track_id)] = row.id
    db.commit()
    return row_ids


def _persist_events(
    db: Session,
    match: Match,
    events: list[EventSpan],
    identity_row_ids: dict[int, str],
) -> None:
    """Insert ``match_events`` rows linked to their track's identity row."""
    for event in events:
        track_id = None if event.track_id is None else int(event.track_id)
        db.add(
            MatchEvent(
                club_id=match.club_id,
                match_id=match.id,
                event_type=_event_type_value(event.event_type),
                t_start_s=float(event.t_start_s),
                t_end_s=float(event.t_end_s),
                player_identity_id=(
                    identity_row_ids.get(track_id) if track_id is not None else None
                ),
                track_id=track_id,
                confidence=float(event.confidence),
                meta_json=_json_safe(event.meta or {}),
            )
        )
    db.commit()


def _persist_stats(
    db: Session,
    match: Match,
    stats: list[PlayerStatsRow],
    identity_row_ids: dict[int, str],
) -> None:
    """Insert ``player_match_stats`` rows (skips tracks without an identity row)."""
    skipped = 0
    for row in stats:
        identity_id = identity_row_ids.get(int(row.track_id))
        if identity_id is None:  # pragma: no cover - identities cover every track
            skipped += 1
            continue
        db.add(
            PlayerMatchStats(
                club_id=match.club_id,
                match_id=match.id,
                player_identity_id=identity_id,
                minutes_tracked=float(row.minutes_tracked),
                distance_proxy_m=float(row.distance_proxy_m),
                touches=int(row.touches),
                passes=int(row.passes),
                tackles=int(row.tackles),
                shots=int(row.shots),
                turnovers=int(row.turnovers),
                scoring_events=int(row.scoring_events),
                avg_confidence=float(row.avg_confidence),
                heatmap_json=_json_safe(row.heatmap),
            )
        )
    db.commit()
    if skipped:
        log.warning("stats_rows_skipped_no_identity", match_id=match.id, skipped=skipped)


def _write_player_reports(
    db: Session,
    storage: Any,
    match: Match,
    identities: list[IdentityResult],
    stats: list[PlayerStatsRow],
    events: list[EventSpan],
    out_dir: Path,
    artifact_paths: dict[str, str],
) -> None:
    """Write + register per-identity player reports (JSON and PDF)."""
    stats_by_track = {int(row.track_id): row for row in stats}
    for identity in identities:
        stats_row = stats_by_track.get(int(identity.track_id)) or _empty_stats_row(identity)
        report = build_player_report(match, identity, stats_row, events)
        slug = identity.player_id or f"track_{identity.track_id}"
        json_path = write_player_report_json(report, out_dir)
        pdf_path = write_player_report_pdf(report, out_dir)
        meta = {
            "player_id": identity.player_id,
            "track_id": int(identity.track_id),
            "jersey_number": identity.jersey_number,
        }
        _register(
            db,
            storage,
            match,
            "player_report_json",
            json_path,
            artifact_paths,
            meta=meta,
            path_key=f"player_report_json:{slug}",
        )
        _register(
            db,
            storage,
            match,
            "player_report_pdf",
            pdf_path,
            artifact_paths,
            meta=meta,
            path_key=f"player_report_pdf:{slug}",
        )


def _empty_stats_row(identity: IdentityResult) -> PlayerStatsRow:
    """Zeroed stats row for an identity whose track produced no stats."""
    return PlayerStatsRow(
        track_id=int(identity.track_id),
        player_id=identity.player_id,
        jersey_number=identity.jersey_number,
        minutes_tracked=0.0,
        distance_proxy_m=0.0,
        touches=0,
        passes=0,
        tackles=0,
        shots=0,
        turnovers=0,
        scoring_events=0,
        avg_confidence=0.0,
    )


def _register(
    db: Session,
    storage: Any,
    match: Match,
    kind: str,
    path: Path,
    artifact_paths: dict[str, str],
    *,
    meta: dict[str, Any] | None = None,
    path_key: str | None = None,
) -> None:
    """Register one artifact (storage + DB) and record its local path."""
    register_artifact(
        db,
        storage,
        club_id=match.club_id,
        match_id=match.id,
        kind=kind,
        local_path=path,
        meta=meta,
    )
    artifact_paths[path_key or kind] = str(path)


def _event_type_value(event_type: Any) -> str:
    """Return the plain string value of an event type (enum or str)."""
    return str(getattr(event_type, "value", event_type))


def _json_safe(value: Any) -> Any:
    """Recursively coerce numpy/datetime values into JSON-serializable types."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
