"""Event heuristics on hand-built synthetic tracks (CONTRACTS.md section 8)."""

from __future__ import annotations

import pandas as pd
import pytest

from playsight.analytics import compute_events
from playsight.core.types import EventType
from tests import factories


class TestComputeEvents:
    def test_handoff_produces_touch_and_pass(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        events = compute_events(tracks_df, factories.handoff_video_info())
        types = {event.event_type for event in events}
        assert EventType.TOUCH.value in types
        assert EventType.PASS.value in types

    def test_pass_links_the_two_possessing_tracks(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        events = compute_events(tracks_df, factories.handoff_video_info())
        passes = [e for e in events if e.event_type == EventType.PASS.value]
        assert len(passes) >= 1
        handoff = passes[0]
        assert handoff.track_id == 1  # attributed to the track losing possession
        assert handoff.meta["from_track"] == 1
        assert handoff.meta["to_track"] == 2
        assert 0.0 <= handoff.meta["gap_s"] < 2.0  # section 8: handoff within 2s

    def test_confidences_and_time_spans_are_valid(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        info = factories.handoff_video_info()
        events = compute_events(tracks_df, info)
        assert events, "expected at least one event from the handoff scenario"
        valid_types = {member.value for member in EventType}
        for event in events:
            assert event.event_type in valid_types
            assert 0.0 <= event.confidence <= 1.0
            assert 0.0 <= event.t_start_s <= event.t_end_s
            assert event.t_end_s <= info.duration_s + 1.0

    def test_events_sorted_by_start_time(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        events = compute_events(tracks_df, factories.handoff_video_info())
        starts = [event.t_start_s for event in events]
        assert starts == sorted(starts)

    def test_deterministic_for_same_input(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        info = factories.handoff_video_info()
        assert compute_events(tracks_df, info) == compute_events(tracks_df.copy(), info)

    def test_empty_tracks_yield_no_events(self) -> None:
        assert compute_events(factories.empty_tracks_df(), factories.handoff_video_info()) == []

    def test_too_few_frames_yield_no_events(self) -> None:
        tracks_df = factories.build_handoff_tracks_df()
        short = tracks_df[tracks_df["frame_index"] < 4]
        assert compute_events(short, factories.handoff_video_info()) == []

    def test_missing_columns_raise(self) -> None:
        broken = pd.DataFrame({"frame_index": [0], "t_s": [0.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            compute_events(broken, factories.handoff_video_info())
