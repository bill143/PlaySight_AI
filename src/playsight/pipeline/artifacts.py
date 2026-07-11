"""Artifact registration and shared asset resolution for the orchestration layer.

Every generated file is written to ``outputs/<match_id>/`` with its
contract-exact filename (CONTRACTS.md section 9), copied to object storage
under ``matches/<match_id>/<filename>``, and upserted into the ``artifacts``
table. The pipeline runner and the job tasks share these helpers.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.core.logging import get_logger
from playsight.db.models import Artifact, VideoAsset
from playsight.storage.base import ObjectStorage

log = get_logger(__name__)

#: Root directory for per-match artifact output (CONTRACTS.md section 9),
#: relative to the process working directory (repo root in dev/docker).
OUTPUTS_ROOT = Path("outputs")

#: Content types for the contracted artifact file extensions.
_CONTENT_TYPES: dict[str, str] = {
    ".parquet": "application/octet-stream",
    ".csv": "text/csv",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".txt": "text/plain",
}


def outputs_dir(match_id: str) -> Path:
    """Return (and create) the local artifact directory ``outputs/<match_id>/``.

    Args:
        match_id: The match the artifacts belong to.
    """
    path = OUTPUTS_ROOT / match_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def content_type_for(path: str | Path) -> str:
    """Return the content type for an artifact file based on its extension.

    Args:
        path: Artifact filename or path.

    Returns:
        A MIME type; ``application/octet-stream`` when unknown.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _CONTENT_TYPES:
        return _CONTENT_TYPES[suffix]
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def register_artifact(
    db: Session,
    storage: ObjectStorage,
    *,
    club_id: str,
    match_id: str,
    kind: str,
    local_path: str | Path,
    meta: dict[str, Any] | None = None,
) -> Artifact:
    """Copy a generated file to object storage and upsert its ``artifacts`` row.

    The storage key is ``matches/<match_id>/<filename>`` (CONTRACTS.md
    section 9). Re-registering the same ``(club, match, kind, filename)``
    updates the existing row in place so reprocessing a match never duplicates
    artifact rows. The session is committed before returning.

    Args:
        db: Database session (committed by this function).
        storage: Object storage backend receiving a copy of the file.
        club_id: Tenancy scope of the artifact.
        match_id: Match the artifact belongs to.
        kind: Artifact kind (section 9 table, e.g. ``"player_tracks"``).
        local_path: Local file to register; must exist.
        meta: Optional JSON-serializable metadata stored in ``meta_json``.

    Returns:
        The persisted (created or refreshed) :class:`Artifact` row.

    Raises:
        NotFoundError: ``local_path`` does not exist.
    """
    path = Path(local_path)
    if not path.is_file():
        raise NotFoundError(f"artifact file not found: {path}")

    filename = path.name
    storage_key = f"matches/{match_id}/{filename}"
    storage.put_file(path, storage_key)
    size_bytes = path.stat().st_size
    ctype = content_type_for(path)

    existing = (
        db.execute(
            select(Artifact).where(
                Artifact.club_id == club_id,
                Artifact.match_id == match_id,
                Artifact.kind == kind,
                Artifact.filename == filename,
            )
        )
        .scalars()
        .first()
    )

    if existing is None:
        artifact = Artifact(
            club_id=club_id,
            match_id=match_id,
            kind=kind,
            storage_key=storage_key,
            filename=filename,
            content_type=ctype,
            size_bytes=size_bytes,
            meta_json=dict(meta or {}),
        )
        db.add(artifact)
    else:
        artifact = existing
        artifact.storage_key = storage_key
        artifact.content_type = ctype
        artifact.size_bytes = size_bytes
        artifact.meta_json = dict(meta or {})
    db.commit()
    db.refresh(artifact)

    log.info(
        "artifact_registered",
        artifact_id=artifact.id,
        kind=kind,
        match_id=match_id,
        storage_key=storage_key,
        size_bytes=size_bytes,
    )
    return artifact


def resolve_match_video(db: Session, storage: ObjectStorage, match_id: str) -> Path:
    """Return a local path to the source video of a match.

    Prefers the original ``source_path`` recorded at ingest time when it still
    exists on disk; otherwise downloads the object-storage copy to
    ``outputs/<match_id>/source/<filename>`` (skipped when already present).

    Args:
        db: Database session (reads ``video_assets``).
        storage: Object storage holding the ingested copy.
        match_id: Match whose video is needed.

    Returns:
        Local filesystem path of a readable video file.

    Raises:
        NotFoundError: No usable video asset is registered for the match.
    """
    assets = db.execute(select(VideoAsset).where(VideoAsset.match_id == match_id)).scalars().all()
    ready = [a for a in assets if a.status == "ready"] or list(assets)
    if not ready:
        raise NotFoundError(f"no video asset registered for match {match_id}")
    asset = ready[-1]

    source_path = (asset.meta_json or {}).get("source_path")
    if source_path and Path(source_path).is_file():
        return Path(source_path)

    local_path = outputs_dir(match_id) / "source" / asset.filename
    if local_path.is_file() and local_path.stat().st_size > 0:
        return local_path
    storage.download_to(asset.storage_key, local_path)
    log.info(
        "match_video_downloaded",
        match_id=match_id,
        storage_key=asset.storage_key,
        local_path=str(local_path),
    )
    return local_path
