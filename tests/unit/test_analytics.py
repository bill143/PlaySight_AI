"""Unit tests for the analytics package."""

from __future__ import annotations

from backend.analytics.events import EventDetector, FrameObservation
from backend.analytics.heatmap import HeatmapGenerator
from backend.analytics.stats import PlayerStatsCalculator, TrackFrameSample
from backend.analytics.summary import MatchSummaryBuilder
from backend.detection.models import BoundingBox


class TestPlayerStatsCalculator:
    def test_compute_zero_movement(self) -> None:
        calculator = PlayerStatsCalculator()
        samples = [
            TrackFrameSample(0, 0.0, BoundingBox(0, 0, 10, 10)),
            TrackFrameSample(1, 1.0, BoundingBox(0, 0, 10, 10)),
        ]
        result = calculator.compute("1", 7, samples)
        assert result.distance_covered_m == 0.0
        assert result.top_speed_kmh == 0.0
        assert result.jersey_number == 7

    def test_compute_movement_accumulates_distance(self) -> None:
        calculator = PlayerStatsCalculator(pixels_per_meter=10.0)
        samples = [
            TrackFrameSample(0, 0.0, BoundingBox(0, 0, 10, 10)),
            TrackFrameSample(1, 1.0, BoundingBox(100, 0, 110, 10)),
        ]
        result = calculator.compute("1", None, samples)
        assert result.distance_covered_m == 10.0
        assert result.top_speed_kmh > 0

    def test_compute_with_no_samples(self) -> None:
        calculator = PlayerStatsCalculator()
        result = calculator.compute("1", None, [])
        assert result.distance_covered_m == 0.0
        assert result.heatmap_zones == {}

    def test_compute_passes_through_event_counts(self) -> None:
        calculator = PlayerStatsCalculator()
        result = calculator.compute("1", 10, [], possessions=3, passes=2, shots=1, goals=1, time_on_ball_seconds=12.5)
        assert result.possessions == 3
        assert result.passes == 2
        assert result.shots == 1
        assert result.goals == 1
        assert result.time_on_ball_seconds == 12.5


class TestEventDetector:
    def test_detect_possession_start(self) -> None:
        detector = EventDetector(possession_distance_px=50)
        frames = [
            FrameObservation(0, 0.0, BoundingBox(0, 0, 10, 10), {1: BoundingBox(0, 0, 10, 10)}),
        ]
        events = detector.detect(frames)
        assert len(events) == 1
        assert events[0].event_type == "possession_start"
        assert events[0].track_id == 1

    def test_detect_pass_between_players(self) -> None:
        detector = EventDetector(possession_distance_px=50)
        frames = [
            FrameObservation(0, 0.0, BoundingBox(0, 0, 10, 10), {1: BoundingBox(0, 0, 10, 10), 2: BoundingBox(500, 500, 510, 510)}),
            FrameObservation(1, 1.0, BoundingBox(500, 500, 510, 510), {1: BoundingBox(0, 0, 10, 10), 2: BoundingBox(500, 500, 510, 510)}),
        ]
        events = detector.detect(frames)
        event_types = [e.event_type for e in events]
        assert "possession_start" in event_types
        assert "pass" in event_types

    def test_no_ball_produces_no_events(self) -> None:
        detector = EventDetector()
        frames = [FrameObservation(0, 0.0, None, {1: BoundingBox(0, 0, 10, 10)})]
        assert detector.detect(frames) == []

    def test_possession_and_pass_counts(self) -> None:
        detector = EventDetector(possession_distance_px=50)
        frames = [
            FrameObservation(0, 0.0, BoundingBox(0, 0, 10, 10), {1: BoundingBox(0, 0, 10, 10)}),
            FrameObservation(1, 1.0, BoundingBox(500, 500, 510, 510), {1: BoundingBox(0, 0, 10, 10), 2: BoundingBox(500, 500, 510, 510)}),
        ]
        events = detector.detect(frames)
        possession_counts = detector.compute_possession_counts(events)
        pass_counts = detector.compute_pass_counts(events)
        assert possession_counts.get(1, 0) >= 1
        assert pass_counts.get(1, 0) >= 1


class TestHeatmapGenerator:
    def test_generate_empty_positions(self) -> None:
        generator = HeatmapGenerator()
        grid = generator.generate([], frame_width=640, frame_height=480)
        assert grid.sum() == 0

    def test_generate_normalizes_to_one(self) -> None:
        generator = HeatmapGenerator()
        positions = [BoundingBox(0, 0, 10, 10), BoundingBox(600, 400, 610, 410)]
        grid = generator.generate(positions, frame_width=640, frame_height=480)
        assert abs(grid.sum() - 1.0) < 1e-9

    def test_to_zone_dict_only_includes_nonzero(self) -> None:
        generator = HeatmapGenerator()
        positions = [BoundingBox(0, 0, 10, 10)]
        grid = generator.generate(positions, frame_width=640, frame_height=480)
        zones = generator.to_zone_dict(grid)
        assert len(zones) == 1
        assert all(v > 0 for v in zones.values())


class TestMatchSummaryBuilder:
    def test_build_summary(self) -> None:
        builder = MatchSummaryBuilder()
        calculator = PlayerStatsCalculator()
        stats = [calculator.compute("1", 9, [])]
        detector = EventDetector()
        events = detector.detect([])

        summary = builder.build(match_id="m1", duration_seconds=90.0, player_stats=stats, events=events)
        assert summary.match_id == "m1"
        assert summary.total_players_tracked == 1
        assert summary.total_events == 0
        assert summary.duration_seconds == 90.0
        assert summary.to_dict()["match_id"] == "m1"
