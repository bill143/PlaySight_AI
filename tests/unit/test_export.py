"""Unit tests for the export package."""

from __future__ import annotations

import json

import numpy as np

from backend.export.audio_export import AudioSummaryExporter
from backend.export.data_export import DataExporter
from backend.export.video_export import VideoExporter


class TestDataExporter:
    def test_export_records_csv(self, tmp_path) -> None:
        exporter = DataExporter()
        records = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        path = exporter.export_records(records, tmp_path / "out.csv", fmt="csv")
        assert path.exists()
        content = path.read_text()
        assert "a,b" in content

    def test_export_records_json(self, tmp_path) -> None:
        exporter = DataExporter()
        records = [{"a": 1}]
        path = exporter.export_records(records, tmp_path / "out.json", fmt="json")
        assert json.loads(path.read_text()) == records

    def test_export_records_parquet(self, tmp_path) -> None:
        exporter = DataExporter()
        records = [{"a": 1, "b": 2.5}]
        path = exporter.export_records(records, tmp_path / "out.parquet", fmt="parquet")
        assert path.exists()

    def test_export_empty_records_csv(self, tmp_path) -> None:
        exporter = DataExporter()
        path = exporter.export_records([], tmp_path / "empty.csv", fmt="csv")
        assert path.exists()

    def test_export_multi_formats(self, tmp_path) -> None:
        exporter = DataExporter()
        records = [{"a": 1}]
        results = exporter.export_multi(records, tmp_path, base_name="data", formats=["csv", "json"])
        assert set(results.keys()) == {"csv", "json"}
        assert all(p.exists() for p in results.values())


class TestVideoExporter:
    def test_export_empty_frames_writes_placeholder(self, tmp_path) -> None:
        exporter = VideoExporter()
        path = exporter.export([], tmp_path / "video.mp4")
        assert path.exists()

    def test_export_with_frames_does_not_raise(self, tmp_path) -> None:
        exporter = VideoExporter()
        frames = [np.zeros((32, 32, 3), dtype=np.uint8) for _ in range(3)]
        path = exporter.export(frames, tmp_path / "video.mp4", fps=10.0)
        assert path.exists()


class TestAudioSummaryExporter:
    def test_build_summary_text_includes_duration(self) -> None:
        exporter = AudioSummaryExporter()
        text = exporter.build_summary_text({"duration_seconds": 120, "total_players_tracked": 10, "total_events": 5})
        assert "2.0 minutes" in text
        assert "10 players" in text

    def test_build_summary_text_mentions_top_scorer(self) -> None:
        exporter = AudioSummaryExporter()
        text = exporter.build_summary_text(
            {
                "duration_seconds": 60,
                "total_players_tracked": 2,
                "total_events": 1,
                "player_stats": [{"jersey_number": 9, "goals": 2}],
            }
        )
        assert "9" in text

    def test_export_writes_file(self, tmp_path) -> None:
        exporter = AudioSummaryExporter()
        path = exporter.export({"duration_seconds": 10, "total_players_tracked": 1, "total_events": 0}, tmp_path / "audio.mp3")
        assert path.exists()
