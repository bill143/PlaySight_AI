"""Player stats: minutes, distance proxy, heatmap shape 8x12, event counts."""

from __future__ import annotations

import pytest

from playsight.analytics import compute_player_stats
from playsight.core.types import HEATMAP_COLS, HEATMAP_ROWS, EventSpan, IdentityResult
from tests import factories


def _identities() -> list[IdentityResult]:
    return [
        factories.make_identity(track_id=1, jersey_number=9, player_id="player-1", method="reid"),
        factories.make_identity(
            track_id=2, jersey_number=None, player_id=None, confidence=0.0, method="unresolved"
        ),
    ]


def _events() -> list[EventSpan]:
    return [
        EventSpan(event_type="touch", t_start_s=0.1, t_end_s=1.9, track_id=1, confidence=0.8),
        EventSpan(event_type="pass", t_start_s=1.9, t_end_s=2.0, track_id=1, confidence=0.7),
        EventSpan(event_type="touch", t_start_s=2.0, t_end_s=3.9, track_id=2, confidence=0.8),
    ]


class TestComputePlayerStats:
    def test_one_row_per_track_sorted(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(),
            _identities(),
            _events(),
            factories.handoff_video_info(),
        )
        assert [row.track_id for row in rows] == [1, 2, 3]

    def test_minutes_tracked_uses_processed_frame_period(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(), [], [], factories.handoff_video_info()
        )
        # 40 frames x 0.1s each = 4.0s = 0.0667 minutes per track.
        for row in rows:
            assert row.minutes_tracked == pytest.approx(0.067, abs=0.001)

    def test_distance_proxy_scaled_and_capped(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(), [], [], factories.handoff_video_info()
        )
        by_track = {row.track_id: row for row in rows}
        # Track 1 moves 19 steps x 5px = 95px; nominal 105m over 1000px width.
        assert by_track[1].distance_proxy_m == pytest.approx(10.0, abs=0.2)
        assert by_track[3].distance_proxy_m == 0.0  # static track

    def test_heatmap_shape_and_normalization(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(), [], [], factories.handoff_video_info()
        )
        for row in rows:
            assert len(row.heatmap) == HEATMAP_ROWS == 8
            assert all(len(grid_row) == HEATMAP_COLS == 12 for grid_row in row.heatmap)
            total = sum(sum(grid_row) for grid_row in row.heatmap)
            assert total == pytest.approx(1.0, abs=0.01)
            assert all(value >= 0.0 for grid_row in row.heatmap for value in grid_row)

    def test_event_counts_joined_by_track(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(),
            _identities(),
            _events(),
            factories.handoff_video_info(),
        )
        by_track = {row.track_id: row for row in rows}
        assert by_track[1].touches == 1
        assert by_track[1].passes == 1
        assert by_track[2].touches == 1
        assert by_track[2].passes == 0
        assert by_track[3].touches == 0

    def test_identity_join(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(),
            _identities(),
            [],
            factories.handoff_video_info(),
        )
        by_track = {row.track_id: row for row in rows}
        assert by_track[1].player_id == "player-1"
        assert by_track[1].jersey_number == 9
        assert by_track[2].player_id is None
        assert by_track[3].player_id is None  # no identity provided at all

    def test_avg_confidence(self) -> None:
        rows = compute_player_stats(
            factories.build_handoff_tracks_df(), [], [], factories.handoff_video_info()
        )
        for row in rows:
            assert row.avg_confidence == pytest.approx(0.9, abs=1e-6)

    def test_empty_tracks_yield_no_rows(self) -> None:
        rows = compute_player_stats(
            factories.empty_tracks_df(), [], [], factories.handoff_video_info()
        )
        assert rows == []
