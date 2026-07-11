"""YouTube publishing service (CONTRACTS.md sections 9 and 13).

``publish_artifact`` drives one ``upload_records`` row through its lifecycle
(``pending -> uploading -> succeeded | failed``), downloads the referenced
artifact from object storage to a temp file, uploads it via
:class:`playsight.integrations.youtube.client.YouTubeClient`, and refreshes
the per-match ``upload_status.json`` artifact after every terminal state.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import NotFoundError
from playsight.core.logging import get_logger
from playsight.db.models import Artifact, UploadRecord, utcnow
from playsight.integrations.youtube.client import (
    YouTubeClient,
    YouTubeUploadError,
    error_entry,
)
from playsight.storage.base import ObjectStorage

log = get_logger(__name__)

UPLOAD_STATUS_KIND = "upload_status"
UPLOAD_STATUS_FILENAME = "upload_status.json"

#: Per-match artifact directory root (CONTRACTS.md section 9), relative to the
#: process working directory (repo root in dev/docker).
OUTPUTS_ROOT = Path("outputs")


def publish_artifact(
    db: Session,
    storage: ObjectStorage,
    upload_record_id: str,
    *,
    settings: Settings | None = None,
    client: YouTubeClient | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> UploadRecord:
    """Publish the artifact referenced by an upload record to YouTube.

    Idempotent: a record already in ``succeeded`` state returns immediately
    without re-uploading. On failure the record is marked ``failed`` with
    structured entries appended to ``error_log_json`` and the original
    exception is re-raised so the job layer can mark the job failed. The
    ``upload_status.json`` artifact for the match is refreshed after every
    terminal state (best effort).

    Args:
        db: Database session (commits record state transitions).
        storage: Object storage holding the artifact bytes.
        upload_record_id: ``upload_records.id`` to publish.
        settings: Optional settings override (defaults to process settings).
        client: Optional pre-built client (tests inject a mock here).
        progress_cb: Optional callback receiving upload progress in ``[0, 1]``.

    Returns:
        The (refreshed) UploadRecord row.

    Raises:
        NotFoundError: Unknown upload record or missing artifact row.
        ExternalServiceError: Download or upload failed terminally.
    """
    record = db.get(UploadRecord, upload_record_id)
    if record is None:
        raise NotFoundError(f"Upload record not found: {upload_record_id}")
    if record.status == "succeeded":
        log.info(
            "youtube_publish_already_succeeded",
            upload_record_id=record.id,
            video_id=record.platform_video_id,
            url=record.url,
        )
        return record

    artifact = db.get(Artifact, record.artifact_id)
    if artifact is None:
        raise NotFoundError(f"Artifact not found: {record.artifact_id} (record {record.id})")

    record.status = "uploading"
    record.attempts = (record.attempts or 0) + 1
    record.updated_at = utcnow()
    db.commit()
    log.info(
        "youtube_publish_started",
        upload_record_id=record.id,
        artifact_id=artifact.id,
        match_id=artifact.match_id,
        attempt=record.attempts,
    )

    yt_client = client or YouTubeClient(settings or get_settings())
    tmp_dir = Path(tempfile.mkdtemp(prefix="playsight_publish_"))
    try:
        local_path = tmp_dir / artifact.filename
        try:
            storage.download_to(artifact.storage_key, local_path)
        except Exception as exc:
            raise YouTubeUploadError(
                f"Failed to download artifact {artifact.id} from storage: {exc}",
                error_log=[error_entry("download", f"{type(exc).__name__}: {exc}", False)],
            ) from exc

        result = yt_client.upload_video(
            local_path,
            title=record.title,
            description=record.description or "",
            tags=list(record.tags_json or []),
            category_id=record.category_id or "17",
            privacy=record.privacy or "private",
            progress_cb=progress_cb,
        )
    except Exception as exc:
        entries = getattr(exc, "error_log", None) or [
            error_entry("publish", f"{type(exc).__name__}: {exc}", False)
        ]
        record.status = "failed"
        record.error_log_json = [*(record.error_log_json or []), *entries]
        record.updated_at = utcnow()
        db.commit()
        log.error("youtube_publish_failed", upload_record_id=record.id, error=str(exc))
        _safe_write_upload_status(db, storage, artifact)
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    record.status = "succeeded"
    record.platform_video_id = result.video_id
    record.url = result.url
    record.updated_at = utcnow()
    db.commit()
    log.info(
        "youtube_publish_succeeded",
        upload_record_id=record.id,
        video_id=result.video_id,
        url=result.url,
    )
    _safe_write_upload_status(db, storage, artifact)
    return record


def write_upload_status_artifact(
    db: Session, storage: ObjectStorage, source_artifact: Artifact
) -> Artifact | None:
    """Write/refresh the ``upload_status.json`` artifact for a match.

    The JSON body is the list of all upload records whose artifacts belong to
    the same match (CONTRACTS.md section 9). The file is written both to the
    local ``outputs/<match_id>/`` directory (best effort) and to object
    storage under ``matches/<match_id>/upload_status.json``, then registered
    (or refreshed) in the ``artifacts`` table.

    Args:
        db: Database session (commits the artifact row).
        storage: Object storage backend.
        source_artifact: The artifact that was published; provides the match
            and club scope.

    Returns:
        The upload-status Artifact row, or None when the source artifact is
        not attached to a match.
    """
    match_id = source_artifact.match_id
    if match_id is None:
        log.info("upload_status_skipped_no_match", artifact_id=source_artifact.id)
        return None
    club_id = source_artifact.club_id

    records_stmt = (
        select(UploadRecord)
        .join(Artifact, UploadRecord.artifact_id == Artifact.id)
        .where(Artifact.match_id == match_id, UploadRecord.club_id == club_id)
        .order_by(UploadRecord.created_at)
    )
    records = db.execute(records_stmt).scalars().all()
    payload = [_record_to_dict(r) for r in records]
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")

    storage_key = f"matches/{match_id}/{UPLOAD_STATUS_FILENAME}"
    storage.put_bytes(data, storage_key, content_type="application/json")

    local_path = OUTPUTS_ROOT / match_id / UPLOAD_STATUS_FILENAME
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
    except OSError as exc:
        log.warning("upload_status_local_write_failed", path=str(local_path), error=str(exc))

    existing_stmt = select(Artifact).where(
        Artifact.match_id == match_id,
        Artifact.club_id == club_id,
        Artifact.kind == UPLOAD_STATUS_KIND,
    )
    status_artifact = db.execute(existing_stmt).scalars().first()
    if status_artifact is None:
        status_artifact = Artifact(
            club_id=club_id,
            match_id=match_id,
            kind=UPLOAD_STATUS_KIND,
            storage_key=storage_key,
            filename=UPLOAD_STATUS_FILENAME,
            content_type="application/json",
            size_bytes=len(data),
            meta_json={"records": len(payload)},
        )
        db.add(status_artifact)
    else:
        status_artifact.storage_key = storage_key
        status_artifact.size_bytes = len(data)
        status_artifact.meta_json = {"records": len(payload)}
    db.commit()
    log.info(
        "upload_status_artifact_written",
        match_id=match_id,
        storage_key=storage_key,
        records=len(payload),
    )
    return status_artifact


def _safe_write_upload_status(db: Session, storage: ObjectStorage, artifact: Artifact) -> None:
    """Refresh ``upload_status.json`` without masking the publish outcome."""
    try:
        write_upload_status_artifact(db, storage, artifact)
    except Exception as exc:
        log.error("upload_status_artifact_failed", artifact_id=artifact.id, error=str(exc))


def _record_to_dict(record: UploadRecord) -> dict[str, Any]:
    """Serialize an UploadRecord row for ``upload_status.json``."""
    return {
        "id": record.id,
        "club_id": record.club_id,
        "artifact_id": record.artifact_id,
        "platform": record.platform,
        "idempotency_key": record.idempotency_key,
        "status": record.status,
        "platform_video_id": record.platform_video_id,
        "url": record.url,
        "title": record.title,
        "description": record.description,
        "tags": list(record.tags_json or []),
        "category_id": record.category_id,
        "privacy": record.privacy,
        "attempts": record.attempts,
        "error_log": list(record.error_log_json or []),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
