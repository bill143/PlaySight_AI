"""Structured data export: CSV / JSON / Parquet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd

ExportFormat = Literal["csv", "json", "parquet"]


class DataExporter:
    """Exports tabular/records data (e.g. player stats, tracks) to CSV, JSON, or Parquet."""

    def export_records(
        self, records: list[dict[str, Any]], output_path: str | Path, fmt: ExportFormat = "csv"
    ) -> Path:
        """Export a list of flat dict records to the requested format."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
            return output_path

        df = pd.DataFrame.from_records(records) if records else pd.DataFrame()

        if fmt == "csv":
            df.to_csv(output_path, index=False)
        elif fmt == "parquet":
            df.to_parquet(output_path, index=False)
        else:  # pragma: no cover - guarded by Literal type at call sites
            raise ValueError(f"Unsupported export format: {fmt}")

        return output_path

    def export_multi(
        self, records: list[dict[str, Any]], output_dir: str | Path, base_name: str, formats: list[ExportFormat]
    ) -> dict[str, Path]:
        """Export the same records to multiple formats, returning a `{format: path}` mapping."""
        output_dir = Path(output_dir)
        results: dict[str, Path] = {}
        for fmt in formats:
            extension = "json" if fmt == "json" else fmt
            path = output_dir / f"{base_name}.{extension}"
            results[fmt] = self.export_records(records, path, fmt)
        return results
