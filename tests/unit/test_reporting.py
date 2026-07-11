"""Reporting: match summary JSON shape (section 9), CSV columns, PDF magic."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from playsight.core.types import EventType, VideoInfo
from playsight.reporting import (
    build_match_summary,
    build_player_report,
    write_identities_csv,
    write_match_summary_json,
    write_player_report_json,
    write_player_report_pdf,
    write_player_stats_csv,
)
from tests import factories

_SUMMARY_KEYS = {
    "match_id",
    "generated_at",
    "video",
    "teams",
    "counts",
    "events_by_type",
    "players",
    "engine",
    "limitations",
}

_VIDEO_INFO = VideoInfo(duration_s=120.0, fps=30.0, width=1280, height=720, frame_count=3600)


def _identities() -> list:
    return [
        factories.make_identity(track_id=1, jersey_number=9, player_id="player-1", method="ocr"),
        factories.make_identity(
            track_id=2, jersey_number=None, player_id=None, confidence=0.0, method="unresolved"
        ),
    ]


def _stats() -> list:
    return [
        factories.make_stats_row(track_id=1, minutes_tracked=12.5, touches=10),
        factories.make_stats_row(
            track_id=2, player_id=None, jersey_number=None, minutes_tracked=3.0, touches=2
        ),
    ]


def _summary() -> dict:
    return build_match_summary(
        "match-1",
        _VIDEO_INFO,
        _identities(),
        factories.make_events(),
        _stats(),
        teams={"home": "Lions", "away": "Tigers"},
    )


class TestMatchSummary:
    def test_exact_top_level_keys(self) -> None:
        assert set(_summary()) == _SUMMARY_KEYS

    def test_counts_and_events_by_type(self) -> None:
        summary = _summary()
        assert summary["counts"] == {"tracks": 2, "identified": 1, "events": 3}
        assert summary["events_by_type"] == {
            "touch": 1,
            "pass": 1,
            "tackle": 0,
            "shot_attempt": 1,
            "turnover": 0,
            "scoring_event": 0,
        }
        assert set(summary["events_by_type"]) == {member.value for member in EventType}

    def test_players_sorted_and_unresolved_naming(self) -> None:
        players = _summary()["players"]
        assert players[0]["player_id"] == "player-1"  # most minutes first
        assert players[0]["jersey_number"] == 9
        assert players[1]["player_id"] == "track_2"  # section 9 fallback naming
        for player in players:
            required = {
                "player_id",
                "track_id",
                "jersey_number",
                "minutes_tracked",
                "touches",
                "confidence",
            }
            assert required.issubset(player)

    def test_video_teams_engine_and_limitations(self) -> None:
        summary = _summary()
        assert summary["video"] == {"duration_s": 120.0, "fps": 30.0}
        assert summary["teams"] == {"home": "Lions", "away": "Tigers"}
        assert summary["engine"] == {"detector": "stub", "tracker": "simple", "ocr": "stub"}
        assert summary["limitations"], "limitations must be honest and non-empty"
        datetime.fromisoformat(summary["generated_at"])  # ISO 8601

    def test_engine_override(self) -> None:
        summary = build_match_summary(
            "match-2",
            _VIDEO_INFO,
            [],
            [],
            [],
            engine={"detector": "yolo", "tracker": "bytetrack", "ocr": "easyocr"},
        )
        assert summary["engine"] == {
            "detector": "yolo",
            "tracker": "bytetrack",
            "ocr": "easyocr",
        }

    def test_write_match_summary_json(self, tmp_path: Path) -> None:
        path = write_match_summary_json(_summary(), tmp_path)
        assert path.name == "match_summary.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["match_id"] == "match-1"
        assert set(loaded) == _SUMMARY_KEYS


class TestCsvExports:
    def test_player_stats_csv_columns(self, tmp_path: Path) -> None:
        path = write_player_stats_csv(_stats(), tmp_path)
        assert path.name == "player_stats.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == [
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
        ]
        assert len(rows) == 3  # header + 2 tracks
        assert rows[1][0] == "1"
        assert rows[1][1] == "player-1"
        assert rows[2][1] == ""  # unresolved player id -> blank

    def test_identities_csv_columns(self, tmp_path: Path) -> None:
        path = write_identities_csv(_identities(), tmp_path)
        assert path.name == "player_identities.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["track_id", "jersey_number", "player_id", "confidence", "method"]
        assert rows[1] == ["1", "9", "player-1", "0.8", "ocr"]
        assert rows[2][4] == "unresolved"


class TestPlayerReports:
    def _report(self) -> dict:
        match = {
            "match_id": "match-1",
            "opponent": "Tigers",
            "sport": "soccer",
            "kickoff_at": None,
            "venue": "Home Ground",
        }
        return build_player_report(match, _identities()[0], _stats()[0], factories.make_events())

    def test_report_payload_shape(self) -> None:
        report = self._report()
        assert set(report) == {
            "report_type",
            "generated_at",
            "match",
            "player",
            "performance_summary",
            "key_metrics",
            "heatmap",
            "event_timeline",
            "disclaimer",
        }
        assert report["player"]["player_id"] == "player-1"
        assert report["player"]["resolved"] is True
        # Only the identity's own events appear in the timeline (track 1).
        assert [entry["event_type"] for entry in report["event_timeline"]] == ["touch", "pass"]
        assert "estimate" in report["disclaimer"].lower()
        assert "face recognition" in report["player"]["identity_note"].lower()

    def test_write_report_json(self, tmp_path: Path) -> None:
        path = write_player_report_json(self._report(), tmp_path)
        assert path.name == "player_report_player-1.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["match"]["match_id"] == "match-1"

    def test_write_report_pdf_magic(self, tmp_path: Path) -> None:
        path = write_player_report_pdf(self._report(), tmp_path)
        assert path.name == "player_report_player-1.pdf"
        content = path.read_bytes()
        assert content.startswith(b"%PDF")
        assert len(content) > 500

    def test_unresolved_identity_uses_track_slug(self, tmp_path: Path) -> None:
        report = build_player_report({"match_id": "match-1"}, _identities()[1], _stats()[1], [])
        assert report["player"]["player_id"] == "track_2"
        assert report["player"]["resolved"] is False
        json_path = write_player_report_json(report, tmp_path)
        pdf_path = write_player_report_pdf(report, tmp_path)
        assert json_path.name == "player_report_track_2.json"
        assert pdf_path.name == "player_report_track_2.pdf"
        assert pdf_path.read_bytes().startswith(b"%PDF")
