"""Match overview report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.analytics.summary import MatchSummary


class MatchReportGenerator:
    """Generates a match-level overview report from a `MatchSummary`."""

    def build_report_dict(self, summary: MatchSummary, top_n_players: int = 5) -> dict[str, Any]:
        """Build a report dict highlighting top performers alongside the raw summary."""
        top_by_distance = sorted(
            summary.player_stats, key=lambda p: p.get("distance_covered_m", 0), reverse=True
        )[:top_n_players]

        return {
            "match_id": summary.match_id,
            "generated_at": summary.generated_at,
            "duration_seconds": summary.duration_seconds,
            "total_players_tracked": summary.total_players_tracked,
            "total_events": summary.total_events,
            "top_performers_by_distance": top_by_distance,
            "summary": summary.to_dict(),
        }

    def write_json(self, report: dict[str, Any], output_path: str | Path) -> Path:
        """Write the match report to disk as JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return output_path
