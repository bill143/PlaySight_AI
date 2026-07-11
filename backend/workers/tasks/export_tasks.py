"""Celery tasks for data/report export jobs."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.core.storage import get_storage_client
from backend.export.data_export import DataExporter, ExportFormat
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="export_match_reports")
def export_match_reports_task(self, match_id: str, formats: list[str]) -> dict[str, Any]:
    """Re-export a match's player_stats records to the requested formats and upload them."""
    output_dir = Path(settings.OUTPUT_DIR) / match_id
    stats_csv = output_dir / "player_stats.csv"

    if not stats_csv.exists():
        raise FileNotFoundError(f"No player_stats.csv found for match {match_id} at {stats_csv}")

    import pandas as pd

    records = pd.read_csv(stats_csv).to_dict(orient="records")

    exporter = DataExporter()
    valid_formats: list[ExportFormat] = [f for f in formats if f in ("csv", "json", "parquet")]  # type: ignore[list-item]
    exported = exporter.export_multi(records, output_dir, base_name="player_stats_export", formats=valid_formats)

    storage = get_storage_client()
    storage.ensure_bucket()
    uploaded_keys: dict[str, str] = {}
    for fmt, path in exported.items():
        key = storage.upload_file(path, f"matches/{match_id}/artifacts/{path.name}")
        uploaded_keys[fmt] = key

    return {"match_id": match_id, "exports": uploaded_keys}


async def _noop() -> None:  # pragma: no cover - placeholder for future async export hooks
    await asyncio.sleep(0)
