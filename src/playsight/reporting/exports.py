"""CSV/JSON artifact writers with contract-exact filenames (CONTRACTS.md section 9).

Writers take an output directory (typically ``outputs/<match_id>/``), create it
if needed, write the artifact under its contracted filename, and return the
written path. Uploading to object storage and registering ``artifacts`` rows is
the pipeline orchestrator's responsibility.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from playsight.core.logging import get_logger
from playsight.core.types import EventSpan, IdentityResult, PlayerStatsRow
from playsight.reporting._util import ensure_out_dir, event_type_value

__all__ = [
    "MATCH_EVENTS_CSV",
    "MATCH_SUMMARY_JSON",
    "PLAYER_IDENTITIES_CSV",
    "PLAYER_STATS_CSV",
    "write_events_csv",
    "write_identities_csv",
    "write_match_summary_json",
    "write_player_stats_csv",
]

PLAYER_STATS_CSV = "player_stats.csv"
PLAYER_IDENTITIES_CSV = "player_identities.csv"
MATCH_SUMMARY_JSON = "match_summary.json"
MATCH_EVENTS_CSV = "match_events.csv"  # optional extra (not in the section 9 table)

_STATS_COLUMNS = (
    "track_id",
    "player_id",
    "jersey_number",
    "minutes_tracked",
    "distance_proxy_m",
    "touches",
    "passes",
    "tackles",
    "shots",
    "turnovers",
    "scoring_events",
    "avg_confidence",
)

_IDENTITY_COLUMNS = ("track_id", "jersey_number", "player_id", "confidence", "method")

_EVENT_COLUMNS = ("event_type", "t_start_s", "t_end_s", "track_id", "confidence", "meta_json")


def write_player_stats_csv(stats: Sequence[PlayerStatsRow], out_dir: Path | str) -> Path:
    """Write ``player_stats.csv`` and return its path.

    The 8x12 heatmap grid is intentionally omitted from the CSV; it lives in
    the per-player reports and in ``player_match_stats.heatmap_json``.

    Args:
        stats: per-track stats rows (written sorted by ``track_id``).
        out_dir: output directory, created if missing.
    """
    path = ensure_out_dir(out_dir) / PLAYER_STATS_CSV
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_STATS_COLUMNS)
        for row in sorted(stats, key=lambda s: s.track_id):
            writer.writerow(
                [
                    row.track_id,
                    row.player_id or "",
                    "" if row.jersey_number is None else row.jersey_number,
                    row.minutes_tracked,
                    row.distance_proxy_m,
                    row.touches,
                    row.passes,
                    row.tackles,
                    row.shots,
                    row.turnovers,
                    row.scoring_events,
                    row.avg_confidence,
                ]
            )
    get_logger(__name__).info("artifact_written", kind="player_stats", path=str(path))
    return path


def write_identities_csv(identities: Sequence[IdentityResult], out_dir: Path | str) -> Path:
    """Write ``player_identities.csv`` and return its path.

    Args:
        identities: estimated identities (written sorted by ``track_id``).
        out_dir: output directory, created if missing.
    """
    path = ensure_out_dir(out_dir) / PLAYER_IDENTITIES_CSV
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_IDENTITY_COLUMNS)
        for identity in sorted(identities, key=lambda i: i.track_id):
            writer.writerow(
                [
                    identity.track_id,
                    "" if identity.jersey_number is None else identity.jersey_number,
                    identity.player_id or "",
                    round(float(identity.confidence), 4),
                    identity.method,
                ]
            )
    get_logger(__name__).info("artifact_written", kind="player_identities", path=str(path))
    return path


def write_events_csv(events: Sequence[EventSpan], out_dir: Path | str) -> Path:
    """Write ``match_events.csv`` (optional extra artifact) and return its path.

    Args:
        events: match events (written sorted by start time, then type).
        out_dir: output directory, created if missing.
    """
    path = ensure_out_dir(out_dir) / MATCH_EVENTS_CSV
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_EVENT_COLUMNS)
        ordered = sorted(events, key=lambda e: (e.t_start_s, event_type_value(e.event_type)))
        for event in ordered:
            writer.writerow(
                [
                    event_type_value(event.event_type),
                    event.t_start_s,
                    event.t_end_s,
                    "" if event.track_id is None else event.track_id,
                    event.confidence,
                    json.dumps(event.meta or {}, sort_keys=True, default=str),
                ]
            )
    get_logger(__name__).info("artifact_written", kind="match_events", path=str(path))
    return path


def write_match_summary_json(summary: Mapping[str, Any], out_dir: Path | str) -> Path:
    """Write ``match_summary.json`` and return its path.

    Args:
        summary: payload from :func:`playsight.reporting.build_match_summary`.
        out_dir: output directory, created if missing.
    """
    path = ensure_out_dir(out_dir) / MATCH_SUMMARY_JSON
    with path.open("w", encoding="utf-8") as fh:
        json.dump(dict(summary), fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")
    get_logger(__name__).info("artifact_written", kind="match_summary", path=str(path))
    return path
