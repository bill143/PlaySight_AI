"""Per-player report generation: JSON document and PDF export."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.analytics.stats import PlayerStatsResult

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class PlayerReportGenerator:
    """Generates JSON and PDF reports for a single player's match performance."""

    def __init__(self) -> None:
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def build_report_dict(
        self,
        player_id: str,
        match_id: str,
        stats: PlayerStatsResult,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the canonical JSON-serializable report document."""
        return {
            "player_id": player_id,
            "match_id": match_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "stats": asdict(stats),
            "extra": extra or {},
        }

    def write_json(self, report: dict[str, Any], output_path: str | Path) -> Path:
        """Write a report dict to disk as JSON, returning the file path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return output_path

    def render_html(self, player_name: str, jersey_number: int | None, report: dict[str, Any]) -> str:
        """Render the HTML template used as the basis for the PDF report."""
        template = self._jinja_env.get_template("player_report.html")
        return template.render(
            player_name=player_name or "Unknown Player",
            jersey_number=jersey_number if jersey_number is not None else "-",
            match_id=report["match_id"],
            generated_at=report["generated_at"],
            stats=report["stats"],
        )

    def write_pdf(self, player_name: str, jersey_number: int | None, report: dict[str, Any], output_path: str | Path) -> Path:
        """Render and write a PDF report using reportlab (no external headless-browser dependency)."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, _height = A4

        y = 280 * mm
        c.setFont("Helvetica-Bold", 18)
        c.drawString(20 * mm, y, f"{player_name or 'Unknown Player'} (#{jersey_number if jersey_number is not None else '-'})")

        y -= 10 * mm
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, f"Match: {report['match_id']}  |  Generated: {report['generated_at']}")

        y -= 15 * mm
        c.setFont("Helvetica-Bold", 13)
        c.drawString(20 * mm, y, "Performance Summary")

        stats = report["stats"]
        rows = [
            ("Distance Covered (m)", stats.get("distance_covered_m")),
            ("Top Speed (km/h)", stats.get("top_speed_kmh")),
            ("Possessions", stats.get("possessions")),
            ("Passes", stats.get("passes")),
            ("Shots", stats.get("shots")),
            ("Goals", stats.get("goals")),
            ("Time on Ball (s)", stats.get("time_on_ball_seconds")),
        ]

        c.setFont("Helvetica", 11)
        for label, value in rows:
            y -= 8 * mm
            c.drawString(25 * mm, y, f"{label}: {value}")

        c.showPage()
        c.save()
        return output_path
