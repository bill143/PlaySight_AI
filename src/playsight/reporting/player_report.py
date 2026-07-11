"""Per-player match reports: payload assembly plus JSON and PDF writers.

Filenames follow CONTRACTS.md section 9: ``player_report_<player_id>.json`` /
``.pdf`` where ``<player_id>`` is ``players.id`` when the identity is resolved,
else ``track_<track_id>``. Wording follows section 18: identity is always
presented as *estimated* and confidence-scored, never as verified, and no
biometric face recognition is involved.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from playsight.core.logging import get_logger
from playsight.core.types import EventSpan, IdentityResult, PlayerStatsRow
from playsight.reporting._util import ensure_out_dir, event_type_value, format_clock

__all__ = [
    "CONFIDENCE_DISCLAIMER",
    "ESTIMATED_IDENTITY_NOTE",
    "build_player_report",
    "write_player_report_json",
    "write_player_report_pdf",
]

#: Section 18 wording: identification is estimated, confidence-scored, non-biometric.
ESTIMATED_IDENTITY_NOTE = (
    "Estimated identity based on jersey OCR and appearance embeddings; "
    "confidence-scored and potentially incorrect. "
    "No biometric face recognition is used."
)

#: Standard confidence disclaimer attached to every player report.
CONFIDENCE_DISCLAIMER = (
    "All events and metrics in this report are produced by rule-based MVP heuristics "
    "with confidence scores. They are estimates -- not ground truth -- and should be "
    "reviewed before being used for coaching, selection, or disciplinary decisions."
)

_METRIC_FORMATS: tuple[tuple[str, str, str], ...] = (
    ("minutes_tracked", "Minutes tracked", "{:.1f}"),
    ("distance_proxy_m", "Distance covered (proxy, m)", "{:.0f}"),
    ("touches", "Touches", "{:.0f}"),
    ("passes", "Passes", "{:.0f}"),
    ("tackles", "Tackles", "{:.0f}"),
    ("shots", "Shot attempts", "{:.0f}"),
    ("turnovers", "Turnovers", "{:.0f}"),
    ("scoring_events", "Scoring events", "{:.0f}"),
    ("avg_confidence", "Avg. detection confidence", "{:.2f}"),
)


def build_player_report(
    match: Any,
    identity: IdentityResult,
    stats: PlayerStatsRow,
    events: Sequence[EventSpan],
) -> dict[str, Any]:
    """Assemble the per-player report payload (performance summary, metrics, timeline).

    Args:
        match: match context; a mapping or ORM-like object exposing
            ``match_id``/``id``, ``opponent``, ``sport``, ``kickoff_at``, and
            ``venue`` (all optional; ``None`` is tolerated).
        identity: estimated identity for the player's track.
        stats: computed stats row for the same track.
        events: match events; entries are filtered to ``identity.track_id``.

    Returns:
        A JSON-serializable dict with keys ``report_type, generated_at, match,
        player, performance_summary, key_metrics, heatmap, event_timeline,
        disclaimer``.
    """
    own_events = sorted(
        (event for event in events if event.track_id == identity.track_id),
        key=lambda event: (event.t_start_s, event_type_value(event.event_type)),
    )
    timeline = [
        {
            "event_type": event_type_value(event.event_type),
            "t_start_s": round(float(event.t_start_s), 3),
            "t_end_s": round(float(event.t_end_s), 3),
            "confidence": round(float(event.confidence), 3),
            "clock": format_clock(event.t_start_s),
        }
        for event in own_events
    ]
    kickoff = _match_field(match, "kickoff_at")
    if isinstance(kickoff, datetime):
        kickoff = kickoff.isoformat()
    key_metrics: dict[str, Any] = {
        "minutes_tracked": round(float(stats.minutes_tracked), 2),
        "distance_proxy_m": round(float(stats.distance_proxy_m), 1),
        "touches": int(stats.touches),
        "passes": int(stats.passes),
        "tackles": int(stats.tackles),
        "shots": int(stats.shots),
        "turnovers": int(stats.turnovers),
        "scoring_events": int(stats.scoring_events),
        "avg_confidence": round(float(stats.avg_confidence), 4),
    }
    performance_summary = (
        f"Tracked for {key_metrics['minutes_tracked']:.1f} minutes with an estimated "
        f"{key_metrics['distance_proxy_m']:.0f} m covered (pixel-displacement proxy). "
        f"Involved in {key_metrics['touches']} touches, {key_metrics['passes']} passes, "
        f"{key_metrics['tackles']} tackles, {key_metrics['shots']} shot attempts, "
        f"{key_metrics['turnovers']} turnovers, and {key_metrics['scoring_events']} scoring "
        f"events. Mean detection confidence {key_metrics['avg_confidence']:.2f}. "
        "All figures are rule-based MVP estimates."
    )
    return {
        "report_type": "player_match_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "match": {
            "match_id": _match_field(match, "match_id", "id"),
            "opponent": _match_field(match, "opponent"),
            "sport": _match_field(match, "sport"),
            "kickoff_at": kickoff,
            "venue": _match_field(match, "venue"),
        },
        "player": {
            "player_id": identity.player_id or f"track_{identity.track_id}",
            "resolved": identity.player_id is not None,
            "track_id": int(identity.track_id),
            "jersey_number": identity.jersey_number,
            "identity_method": identity.method,
            "identity_confidence": round(float(identity.confidence), 3),
            "identity_note": ESTIMATED_IDENTITY_NOTE,
        },
        "performance_summary": performance_summary,
        "key_metrics": key_metrics,
        "heatmap": stats.heatmap,
        "event_timeline": timeline,
        "disclaimer": CONFIDENCE_DISCLAIMER,
    }


def write_player_report_json(report: Mapping[str, Any], out_dir: Path | str) -> Path:
    """Write ``player_report_<player_id>.json`` and return its path.

    Args:
        report: payload from :func:`build_player_report`.
        out_dir: output directory, created if missing.
    """
    path = ensure_out_dir(out_dir) / f"player_report_{_player_slug(report)}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(dict(report), fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")
    get_logger(__name__).info("artifact_written", kind="player_report_json", path=str(path))
    return path


def write_player_report_pdf(report: Mapping[str, Any], out_dir: Path | str) -> Path:
    """Render ``player_report_<player_id>.pdf`` (single page) and return its path.

    Layout: header (player and match context), estimated-identity note
    (CONTRACTS.md section 18), performance summary, key-metric table, a capped
    event timeline, and a confidence disclaimer footer.

    Args:
        report: payload from :func:`build_player_report`.
        out_dir: output directory, created if missing.
    """
    player: Mapping[str, Any] = report.get("player", {})
    match: Mapping[str, Any] = report.get("match", {})
    metrics: Mapping[str, Any] = report.get("key_metrics", {})
    timeline: Sequence[Mapping[str, Any]] = report.get("event_timeline", [])

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(15.0, 12.0, 15.0)
    pdf.add_page()
    pdf.set_title(_pdf_text(f"PlaySight player report {_player_slug(report)}"))
    pdf.set_creator("PlaySight AI")

    jersey = player.get("jersey_number")
    label = f"Jersey #{jersey}" if jersey is not None else f"Track {player.get('track_id', '?')}"
    if not player.get("resolved", False):
        label += " (estimated identity)"

    pdf.set_text_color(25, 25, 25)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "PlaySight Player Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, _pdf_text(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(95, 95, 95)
    match_line = _match_line(match)
    if match_line:
        pdf.cell(0, 6, _pdf_text(match_line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    generated_at = report.get("generated_at", "")
    pdf.cell(0, 6, _pdf_text(f"Generated: {generated_at}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "I", 9)
    identity_line = (
        f"Identity: {player.get('identity_method', 'unresolved')} "
        f"(confidence {float(player.get('identity_confidence', 0.0)):.2f}). "
        f"{player.get('identity_note', ESTIMATED_IDENTITY_NOTE)}"
    )
    pdf.multi_cell(0, 4.5, _pdf_text(identity_line))
    pdf.ln(1)
    pdf.set_text_color(25, 25, 25)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _pdf_text(str(report.get("performance_summary", ""))))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Key Metrics", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_draw_color(200, 200, 200)
    for key, metric_label, fmt in _METRIC_FORMATS:
        raw = metrics.get(key, 0)
        value = fmt.format(float(raw if raw is not None else 0))
        pdf.cell(75, 6.5, _pdf_text(metric_label), border=1)
        pdf.cell(
            45, 6.5, _pdf_text(value), border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Event Timeline", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    row_h = 5.5
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(22, row_h, "Clock", border="B")
    pdf.cell(30, row_h, "Start (s)", border="B")
    pdf.cell(30, row_h, "End (s)", border="B")
    pdf.cell(48, row_h, "Event", border="B")
    pdf.cell(25, row_h, "Conf.", border="B", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    footer_reserve = 34.0
    available = pdf.h - pdf.b_margin - footer_reserve - pdf.get_y()
    max_rows = max(0, int(available // row_h))
    entries = list(timeline)
    shown = entries if len(entries) <= max_rows else entries[: max(0, max_rows - 1)]
    for entry in shown:
        pdf.cell(22, row_h, _pdf_text(entry.get("clock", "")))
        pdf.cell(30, row_h, f"{float(entry.get('t_start_s', 0.0)):.2f}")
        pdf.cell(30, row_h, f"{float(entry.get('t_end_s', 0.0)):.2f}")
        pdf.cell(48, row_h, _pdf_text(str(entry.get("event_type", "")).replace("_", " ")))
        pdf.cell(
            25,
            row_h,
            f"{float(entry.get('confidence', 0.0)):.2f}",
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    if not entries:
        pdf.cell(
            0,
            row_h,
            "No events attributed to this player.",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    elif len(shown) < len(entries):
        remaining = len(entries) - len(shown)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(
            0,
            row_h,
            _pdf_text(f"... and {remaining} more events (see the JSON report)"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.set_y(-30.0)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 4, _pdf_text(str(report.get("disclaimer", CONFIDENCE_DISCLAIMER))))

    path = ensure_out_dir(out_dir) / f"player_report_{_player_slug(report)}.pdf"
    pdf.output(str(path))
    get_logger(__name__).info("artifact_written", kind="player_report_pdf", path=str(path))
    return path


def _match_field(match: Any, *names: str) -> Any:
    """Best-effort field lookup supporting mappings and ORM-like objects."""
    if match is None:
        return None
    for name in names:
        value = match.get(name) if isinstance(match, Mapping) else getattr(match, name, None)
        if value is not None:
            return value
    return None


def _match_line(match: Mapping[str, Any]) -> str:
    """Compact one-line match context for the PDF header."""
    parts: list[str] = []
    opponent = match.get("opponent")
    if opponent:
        parts.append(f"vs {opponent}")
    sport = match.get("sport")
    if sport:
        parts.append(str(sport))
    kickoff = match.get("kickoff_at")
    if kickoff:
        parts.append(str(kickoff))
    match_id = match.get("match_id")
    if match_id:
        parts.append(f"match {match_id}")
    return " | ".join(parts)


def _player_slug(report: Mapping[str, Any]) -> str:
    """Return the ``<player_id>`` filename component for a report payload."""
    player: Mapping[str, Any] = report.get("player", {})
    return str(player.get("player_id") or f"track_{player.get('track_id', 0)}")


def _pdf_text(value: Any) -> str:
    """Coerce a value to text renderable by the built-in latin-1 PDF fonts."""
    return str(value).encode("latin-1", "replace").decode("latin-1")
