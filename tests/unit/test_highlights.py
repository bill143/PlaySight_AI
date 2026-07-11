"""Highlights: window merge logic (pure functions) and mocked ffmpeg build."""

from __future__ import annotations

from pathlib import Path

import pytest

from playsight.core.errors import ValidationFailed
from playsight.core.types import EventSpan
from playsight.highlights import build_player_highlights
from playsight.highlights.builder import merge_time_windows, select_event_windows
from tests import factories


def _event(t0: float, t1: float, track_id: int | None = 1) -> EventSpan:
    return EventSpan(
        event_type="touch", t_start_s=t0, t_end_s=t1, track_id=track_id, confidence=0.8
    )


class TestMergeTimeWindows:
    def test_empty(self) -> None:
        assert merge_time_windows([]) == []

    def test_disjoint_sorted(self) -> None:
        assert merge_time_windows([(5.0, 7.0), (1.0, 3.0)]) == [(1.0, 3.0), (5.0, 7.0)]

    def test_overlapping_merged(self) -> None:
        assert merge_time_windows([(1.0, 4.0), (3.0, 6.0)]) == [(1.0, 6.0)]

    def test_touching_merged(self) -> None:
        assert merge_time_windows([(1.0, 2.0), (2.0, 3.0)]) == [(1.0, 3.0)]

    def test_contained_window_absorbed(self) -> None:
        assert merge_time_windows([(1.0, 10.0), (2.0, 3.0)]) == [(1.0, 10.0)]

    def test_reversed_tuple_normalized(self) -> None:
        assert merge_time_windows([(7.0, 5.0)]) == [(5.0, 7.0)]


class TestSelectEventWindows:
    def test_padding_applied_and_clamped_at_zero(self) -> None:
        events = [_event(0.2, 0.4), _event(10.0, 11.0)]
        windows = select_event_windows(events, track_id=1, padding_s=1.5)
        assert windows == [(0.0, 1.9), (8.5, 12.5)]

    def test_other_tracks_excluded(self) -> None:
        events = [_event(1.0, 2.0, track_id=1), _event(5.0, 6.0, track_id=2)]
        assert select_event_windows(events, track_id=2, padding_s=0.0) == [(5.0, 6.0)]

    def test_overlapping_padded_windows_merge(self) -> None:
        events = [_event(1.0, 2.0), _event(2.5, 3.5)]
        assert select_event_windows(events, track_id=1, padding_s=1.0) == [(0.0, 4.5)]

    def test_minimum_clip_duration_enforced(self) -> None:
        windows = select_event_windows([_event(1.0, 1.0)], track_id=1, padding_s=0.0)
        assert windows == [(1.0, 1.5)]

    def test_no_events_yields_no_windows(self) -> None:
        assert select_event_windows([_event(1.0, 2.0, track_id=3)], track_id=1) == []


class TestBuildPlayerHighlights:
    def test_missing_video_raises(self, tmp_path: Path) -> None:
        identity = factories.make_identity(track_id=1)
        with pytest.raises(ValidationFailed):
            build_player_highlights(
                tmp_path / "missing.mp4", [_event(1.0, 2.0)], identity, tmp_path / "out.mp4"
            )

    def test_no_events_for_track_raises(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video bytes")
        identity = factories.make_identity(track_id=99, player_id=None, jersey_number=None)
        with pytest.raises(ValidationFailed):
            build_player_highlights(video, [_event(1.0, 2.0)], identity, tmp_path / "out.mp4")

    def test_cuts_and_concats_with_mocked_ffmpeg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video bytes")
        out = tmp_path / "player_highlights_player-1.mp4"
        calls: list[list[str]] = []

        def fake_run_ffmpeg(args, log=None, *, check=True):
            arg_strings = [str(a) for a in args]
            calls.append(arg_strings)
            Path(arg_strings[-1]).write_bytes(b"encoded")
            return None

        monkeypatch.setattr("playsight.highlights.builder.run_ffmpeg", fake_run_ffmpeg)
        events = [_event(1.0, 2.0), _event(20.0, 21.0)]
        identity = factories.make_identity(track_id=1)
        result = build_player_highlights(video, events, identity, out, padding_s=1.5)

        assert result == out
        assert out.read_bytes() == b"encoded"
        # Two merged windows -> two cut invocations, plus one concat.
        assert len(calls) == 3
        cut_calls = [c for c in calls if "-ss" in c]
        assert len(cut_calls) == 2
        assert cut_calls[0][cut_calls[0].index("-ss") + 1] == "0.000"  # padding clamped at 0
        concat_calls = [c for c in calls if "concat" in c]
        assert len(concat_calls) == 1
