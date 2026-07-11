"""Narration builder for the audio match summary (tolerant, honest wording)."""

from __future__ import annotations

from playsight.export import build_narration


def _summary() -> dict:
    return {
        "teams": {"home": "Lions", "away": "Tigers"},
        "video": {"duration_s": 125.0, "fps": 30.0},
        "counts": {"tracks": 5, "identified": 2, "events": 3},
        "events_by_type": {"touch": 2, "pass": 1, "tackle": 0},
        "players": [
            {"track_id": 1, "jersey_number": 7, "touches": 2, "minutes_tracked": 1.5},
            {"track_id": 2, "jersey_number": None, "touches": 1, "minutes_tracked": 0.5},
        ],
    }


class TestBuildNarration:
    def test_teams_and_duration(self) -> None:
        text = build_narration(_summary())
        assert "Lions versus Tigers." in text
        assert "2 minutes and 5 seconds" in text

    def test_counts_sentence(self) -> None:
        text = build_narration(_summary())
        assert "5 player tracks" in text
        assert "2 identities" in text
        assert "3 notable moments" in text

    def test_event_breakdown_pluralization(self) -> None:
        text = build_narration(_summary())
        assert "2 touches" in text
        assert "1 pass" in text
        assert "0 tackle" not in text  # zero-count types are omitted

    def test_top_players_mentioned(self) -> None:
        text = build_narration(_summary())
        assert "Number 7" in text
        assert "Track 2" in text  # no jersey -> track reference

    def test_honesty_disclaimer_always_present(self) -> None:
        assert "not official match statistics" in build_narration(_summary())
        assert "not official match statistics" in build_narration({})

    def test_empty_summary_tolerated(self) -> None:
        text = build_narration({})
        assert "the home team versus the away team." in text.lower()
        assert "0 player tracks" in text

    def test_singular_counts(self) -> None:
        summary = {"counts": {"tracks": 1, "identified": 1, "events": 1}}
        text = build_narration(summary)
        assert "1 player track," in text
        assert "resolved 1 identity" in text
        assert "1 notable moment" in text
