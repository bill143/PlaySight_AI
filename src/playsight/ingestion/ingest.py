"""Register a match video: copy to object storage and create a video_assets row."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.core.logging import get_logger
from playsight.db.models import Match, VideoAsset
from playsight.ingestion.probe import probe_video
from playsight.storage.base import ObjectStorage


def ingest_video(
    path: str | Path,
    match_id: str,
    storage: ObjectStorage,
    db: Session,
) -> VideoAsset:
    """Ingest a local video file for a match.

    Probes the video, copies it into object storage under
    ``matches/<match_id>/source/<filename>``, and creates a ``video_assets``
    row (status ``ready``). The session is committed before returning so the
    row is durable even when the caller is a one-shot CLI command.

    Args:
        path: Local filesystem path of the source video.
        match_id: Id of an existing ``matches`` row (provides ``club_id``).
        storage: Object storage backend to copy the file into.
        db: SQLAlchemy session (committed by this function).

    Returns:
        The persisted :class:`playsight.db.models.VideoAsset`.

    Raises:
        NotFoundError: The video file or the match row does not exist.
        ValidationFailed: The video file could not be probed.
    """
    log = get_logger(__name__)
    p = Path(path)
    if not p.is_file():
        raise NotFoundError(f"video file not found: {p}")

    match = db.get(Match, match_id)
    if match is None:
        raise NotFoundError(f"match not found: {match_id}")

    info = probe_video(p)
    filename = p.name
    storage_key = f"matches/{match_id}/source/{filename}"
    storage.put_file(p, storage_key)

    asset = VideoAsset(
        club_id=match.club_id,
        match_id=match_id,
        storage_key=storage_key,
        filename=filename,
        duration_s=info.duration_s,
        fps=info.fps,
        width=info.width,
        height=info.height,
        status="ready",
        meta_json={"frame_count": info.frame_count, "source_path": str(p)},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    log.info(
        "video_ingested",
        match_id=match_id,
        video_asset_id=asset.id,
        storage_key=storage_key,
        duration_s=info.duration_s,
        fps=info.fps,
    )
    return asset
