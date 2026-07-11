"""Artifact endpoints: list and streaming download (tenancy-filtered)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import BinaryIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from playsight.api.deps import Pagination, TenantContext, get_db, get_tenant, pagination_params
from playsight.api.schemas.artifacts import ArtifactRead
from playsight.core.errors import NotFoundError
from playsight.db.models import Artifact
from playsight.storage import get_storage

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

_CHUNK_SIZE = 64 * 1024


def _iter_and_close(stream: BinaryIO) -> Iterator[bytes]:
    """Yield the stream in chunks and always close it when exhausted/aborted."""
    try:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        stream.close()


@router.get("", response_model=list[ArtifactRead])
def list_artifacts(
    match_id: str | None = Query(default=None, description="Filter by match."),
    kind: str | None = Query(default=None, description="Filter by artifact kind."),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[Artifact]:
    """List the club's artifacts, newest first."""
    query = db.query(Artifact).filter(Artifact.club_id == tenant.club_id)
    if match_id is not None:
        query = query.filter(Artifact.match_id == match_id)
    if kind is not None:
        query = query.filter(Artifact.kind == kind)
    return query.order_by(Artifact.created_at.desc()).offset(page.offset).limit(page.limit).all()


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the artifact bytes with its stored content type and filename."""
    artifact = db.get(Artifact, artifact_id)
    if artifact is None or artifact.club_id != tenant.club_id:
        raise NotFoundError(f"Artifact not found: {artifact_id}")

    stream = get_storage().open_stream(artifact.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{artifact.filename}"'}
    if artifact.size_bytes:
        headers["Content-Length"] = str(artifact.size_bytes)
    return StreamingResponse(
        _iter_and_close(stream),
        media_type=artifact.content_type or "application/octet-stream",
        headers=headers,
    )
