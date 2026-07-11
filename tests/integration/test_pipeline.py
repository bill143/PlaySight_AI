"""Integration tests exercising the full MatchProcessor pipeline end-to-end."""

from __future__ import annotations

import json

import pytest

from backend.detection.detector import YOLODetector
from backend.identification.resolver import IdentityResolver
from backend.pipeline.processor import MatchProcessor
from backend.tracking.tracker import PlayerTracker


@pytest.fixture
def processor() -> MatchProcessor:
    """A MatchProcessor wired with stub-mode detector/tracker/resolver for deterministic tests."""
    return MatchProcessor(
        detector=YOLODetector(force_stub=True, confidence_threshold=0.0),
        tracker=PlayerTracker(use_bytetrack=True),
        resolver=IdentityResolver(),
    )


class TestMatchProcessorEndToEnd:
    def test_process_match_produces_all_expected_artifacts(self, processor: MatchProcessor, tmp_path) -> None:
        output_dir = tmp_path / "match_output"
        progress_updates: list[tuple[int, str]] = []

        result = processor.process_match(
            video_path=tmp_path / "nonexistent_video.mp4",  # forces synthetic-frame fallback
            metadata={"title": "Test Match", "sport": "football"},
            output_dir=output_dir,
            match_id="test-match-1",
            progress_callback=lambda progress, stage: progress_updates.append((progress, stage)),
        )

        assert result.player_tracks_path.exists()
        assert result.player_identities_path.exists()
        assert result.player_stats_path.exists()
        assert result.match_summary_path.exists()
        assert result.annotated_video_path.exists()
        assert result.match_summary_audio_path.exists()

        # Progress should be reported and end at 100%.
        assert progress_updates[-1][0] == 100
        assert progress_updates[-1][1] == "completed"
        assert progress_updates[0][0] <= progress_updates[-1][0]

    def test_match_summary_contains_expected_structure(self, processor: MatchProcessor, tmp_path) -> None:
        output_dir = tmp_path / "match_output"
        result = processor.process_match(
            video_path=tmp_path / "missing.mp4",
            metadata={},
            output_dir=output_dir,
            match_id="test-match-2",
        )

        summary = json.loads(result.match_summary_path.read_text())
        assert summary["match_id"] == "test-match-2"
        assert "summary" in summary
        assert "player_stats" in summary["summary"]
        assert "events" in summary["summary"]

    def test_player_reports_generated_per_track(self, processor: MatchProcessor, tmp_path) -> None:
        output_dir = tmp_path / "match_output"
        result = processor.process_match(
            video_path=tmp_path / "missing.mp4",
            metadata={},
            output_dir=output_dir,
            match_id="test-match-3",
        )

        assert len(result.player_report_paths) > 0
        for path in result.player_report_paths.values():
            assert path.exists()
            report = json.loads(path.read_text())
            assert report["match_id"] == "test-match-3"
            assert "stats" in report

    def test_player_stats_csv_has_rows(self, processor: MatchProcessor, tmp_path) -> None:
        import pandas as pd

        output_dir = tmp_path / "match_output"
        result = processor.process_match(
            video_path=tmp_path / "missing.mp4",
            metadata={},
            output_dir=output_dir,
            match_id="test-match-4",
        )

        df = pd.read_csv(result.player_stats_path)
        assert len(df) > 0
        assert "distance_covered_m" in df.columns


class TestProcessMatchCeleryTaskEager:
    def test_process_match_task_runs_eagerly_and_updates_job(self, tmp_path, monkeypatch) -> None:
        """The Celery task should run synchronously (eager mode) in the test environment."""
        from backend.workers.celery_app import celery_app

        assert celery_app.conf.task_always_eager is True

        # Patch out DB/storage side effects so this test stays a pure unit-of-work check
        # on the task's control flow without requiring a live Postgres/MinIO instance.
        import backend.workers.tasks.processing as processing_module

        calls: list[dict] = []

        async def _fake_update_job(job_id: str, **fields) -> None:
            calls.append({"job_id": job_id, **fields})

        async def _fake_persist_artifacts(match_id: str, result) -> None:
            calls.append({"match_id": match_id, "persisted": True})

        monkeypatch.setattr(processing_module, "_update_job", _fake_update_job)
        monkeypatch.setattr(processing_module, "_persist_artifacts", _fake_persist_artifacts)

        result = processing_module.process_match_task.apply(
            args=("celery-test-match", str(tmp_path / "missing.mp4"), {}, "job-123")
        )

        assert result.successful()
        assert any(c.get("status") == "succeeded" for c in calls if "status" in c)
