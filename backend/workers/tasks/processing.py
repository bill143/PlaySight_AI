"""Celery tasks for the main video processing pipeline."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.core.storage import get_storage_client
from backend.models.artifact import (
    ARTIFACT_TYPE_ANNOTATED_VIDEO,
    ARTIFACT_TYPE_MATCH_SUMMARY,
    ARTIFACT_TYPE_MATCH_SUMMARY_AUDIO,
    ARTIFACT_TYPE_PLAYER_HIGHLIGHTS,
    ARTIFACT_TYPE_PLAYER_IDENTITIES,
    ARTIFACT_TYPE_PLAYER_REPORT,
    ARTIFACT_TYPE_PLAYER_STATS,
    ARTIFACT_TYPE_PLAYER_TRACKS,
    Artifact,
)
from backend.models.match import ProcessingJob
from backend.pipeline.processor import MatchProcessingResult, MatchProcessor
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _update_job(job_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("ProcessingJob %s not found; skipping status update.", job_id)
            return
        for key, value in fields.items():
            setattr(job, key, value)
        await session.commit()


async def _persist_artifacts(match_id: str, result: MatchProcessingResult) -> None:
    storage = get_storage_client()
    storage.ensure_bucket()

    entries: list[tuple[str, Path]] = [
        (ARTIFACT_TYPE_PLAYER_TRACKS, result.player_tracks_path),
        (ARTIFACT_TYPE_PLAYER_IDENTITIES, result.player_identities_path),
        (ARTIFACT_TYPE_PLAYER_STATS, result.player_stats_path),
        (ARTIFACT_TYPE_MATCH_SUMMARY, result.match_summary_path),
        (ARTIFACT_TYPE_ANNOTATED_VIDEO, result.annotated_video_path),
        (ARTIFACT_TYPE_MATCH_SUMMARY_AUDIO, result.match_summary_audio_path),
    ]
    for player_key, path in result.player_report_paths.items():
        entries.append((f"{ARTIFACT_TYPE_PLAYER_REPORT}_{player_key}", path))
    for player_key, path in result.player_highlight_paths.items():
        entries.append((f"{ARTIFACT_TYPE_PLAYER_HIGHLIGHTS}_{player_key}", path))

    async with AsyncSessionLocal() as session:
        for artifact_type, path in entries:
            if not path.exists():
                continue
            key = storage.upload_file(path, f"matches/{match_id}/artifacts/{path.name}")
            session.add(
                Artifact(
                    match_id=match_id,
                    artifact_type=artifact_type,
                    storage_key=key,
                    content_type="application/octet-stream",
                    artifact_metadata={"filename": path.name},
                )
            )
        await session.commit()


def _progress_callback_factory(job_id: str):
    def _callback(progress: int, stage: str) -> None:
        asyncio.run(_update_job(job_id, progress=progress, current_stage=stage, status="running"))

    return _callback


@celery_app.task(bind=True, name="process_match")
def process_match_task(self, match_id: str, video_path: str, metadata: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    """Run the full MatchProcessor pipeline for a match and persist its artifacts."""
    job_id = job_id or match_id
    output_dir = Path(settings.OUTPUT_DIR) / match_id

    try:
        asyncio.run(_update_job(job_id, status="running", progress=1, current_stage="starting", celery_task_id=self.request.id))

        processor = MatchProcessor()
        result = processor.process_match(
            video_path=video_path,
            metadata=metadata,
            output_dir=output_dir,
            match_id=match_id,
            progress_callback=_progress_callback_factory(job_id),
        )

        asyncio.run(_persist_artifacts(match_id, result))
        asyncio.run(_update_job(job_id, status="succeeded", progress=100, current_stage="completed"))

        return {"match_id": match_id, "output_dir": str(result.output_dir)}
    except Exception as exc:
        logger.exception("Match processing failed for match_id=%s", match_id)
        asyncio.run(_update_job(job_id, status="failed", current_stage="failed", error_message=str(exc)))
        raise


@celery_app.task(name="backend.workers.tasks.processing.cleanup_stale_jobs_task")
def cleanup_stale_jobs_task() -> int:
    """Mark long-running jobs stuck in 'running' state as failed. Returns count affected."""

    async def _cleanup() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ProcessingJob).where(ProcessingJob.status == "running"))
            stale_jobs = result.scalars().all()
            for job in stale_jobs:
                job.status = "failed"
                job.error_message = "Job exceeded maximum allowed processing time."
            await session.commit()
            return len(stale_jobs)

    return asyncio.run(_cleanup())
