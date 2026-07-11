"""Reporting: match summary JSON, CSV exports, and per-player reports.

Public interface (CONTRACTS.md sections 7 and 9):

- :func:`build_match_summary` -- exact ``match_summary.json`` payload.
- :func:`write_player_stats_csv` / :func:`write_identities_csv` /
  :func:`write_events_csv` / :func:`write_match_summary_json` -- artifact
  writers with contract-exact filenames.
- :func:`build_player_report` / :func:`write_player_report_json` /
  :func:`write_player_report_pdf` -- per-player reports (JSON + fpdf2 PDF).
"""

from playsight.reporting.exports import (
    MATCH_EVENTS_CSV,
    MATCH_SUMMARY_JSON,
    PLAYER_IDENTITIES_CSV,
    PLAYER_STATS_CSV,
    write_events_csv,
    write_identities_csv,
    write_match_summary_json,
    write_player_stats_csv,
)
from playsight.reporting.player_report import (
    CONFIDENCE_DISCLAIMER,
    ESTIMATED_IDENTITY_NOTE,
    build_player_report,
    write_player_report_json,
    write_player_report_pdf,
)
from playsight.reporting.summary import DEFAULT_ENGINE, DEFAULT_LIMITATIONS, build_match_summary

__all__ = [
    "CONFIDENCE_DISCLAIMER",
    "DEFAULT_ENGINE",
    "DEFAULT_LIMITATIONS",
    "ESTIMATED_IDENTITY_NOTE",
    "MATCH_EVENTS_CSV",
    "MATCH_SUMMARY_JSON",
    "PLAYER_IDENTITIES_CSV",
    "PLAYER_STATS_CSV",
    "build_match_summary",
    "build_player_report",
    "write_events_csv",
    "write_identities_csv",
    "write_match_summary_json",
    "write_player_report_json",
    "write_player_report_pdf",
    "write_player_stats_csv",
]
