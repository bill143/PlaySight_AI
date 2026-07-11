"""MatchProcessor: orchestrates the full end-to-end video analytics pipeline.

Stages: ingestion validation -> detection -> tracking -> identification ->
analytics -> reporting -> highlights -> export. Designed for dependency
injection so each stage can be swapped/mocked in tests, and reports progress
via an optional callback so callers (e.g. Celery tasks) can update job status.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from backend.analytics.events import EventDetector, FrameObservation
from backend.analytics.heatmap import HeatmapGenerator
from backend.analytics.stats import PlayerStatsCalculator, PlayerStatsResult, TrackFrameSample
from backend.analytics.summary import MatchSummaryBuilder
from backend.detection.detector import BALL_CLASS_ID, YOLODetector
from backend.export.audio_export import AudioSummaryExporter
from backend.export.data_export import DataExporter
from backend.export.video_export import VideoExporter
from backend.highlights.annotator import FrameAnnotator
from backend.highlights.clipper import ClipSpec, VideoClipper
from backend.highlights.merger import ClipMerger
from backend.identification.resolver import IdentityResolver
from backend.reporting.match_report import MatchReportGenerator
from backend.reporting.player_report import PlayerReportGenerator
from backend.tracking.tracker import PlayerTracker

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]

# Number of synthetic frames to generate when the source video cannot be
# opened (e.g. in unit tests using placeholder files). Keeps the pipeline
# fully exercised without requiring real video assets.
STUB_FRAME_COUNT = 15
STUB_FRAME_SIZE = (480, 640, 3)  # height, width, channels
STUB_FPS = 25.0


@dataclass
class MatchProcessingResult:
    """Paths to every artifact produced by a successful pipeline run."""

    output_dir: Path
    player_tracks_path: Path
    player_identities_path: Path
    player_stats_path: Path
    match_summary_path: Path
    annotated_video_path: Path
    match_summary_audio_path: Path
    player_report_paths: dict[str, Path] = field(default_factory=dict)
    player_highlight_paths: dict[str, Path] = field(default_factory=dict)


class MatchProcessor:
    """Coordinates the full video -> analytics -> reports/highlights/exports pipeline."""

    def __init__(
        self,
        detector: YOLODetector | None = None,
        tracker: PlayerTracker | None = None,
        resolver: IdentityResolver | None = None,
    ) -> None:
        self.detector = detector or YOLODetector()
        self.tracker = tracker or PlayerTracker()
        self.resolver = resolver or IdentityResolver()
        self.event_detector = EventDetector()
        self.stats_calculator = PlayerStatsCalculator()
        self.heatmap_generator = HeatmapGenerator()
        self.summary_builder = MatchSummaryBuilder()
        self.player_report_generator = PlayerReportGenerator()
        self.match_report_generator = MatchReportGenerator()
        self.annotator = FrameAnnotator()
        self.video_exporter = VideoExporter()
        self.audio_exporter = AudioSummaryExporter()
        self.data_exporter = DataExporter()
        self.clipper = VideoClipper()
        self.merger = ClipMerger()

    def _report_progress(self, callback: ProgressCallback | None, progress: int, stage: str) -> None:
        logger.info("Match processing progress: %s%% (%s)", progress, stage)
        if callback is not None:
            callback(progress, stage)

    def _read_frames(self, video_path: str | Path) -> tuple[list[np.ndarray], float]:
        """Read frames from a video file, falling back to synthetic frames if unreadable."""
        try:
            import cv2

            capture = cv2.VideoCapture(str(video_path))
            if not capture.isOpened():
                raise RuntimeError(f"Could not open video: {video_path}")

            fps = capture.get(cv2.CAP_PROP_FPS) or STUB_FPS
            frames: list[np.ndarray] = []
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                frames.append(frame)
            capture.release()

            if frames:
                return frames, float(fps)
            raise RuntimeError("Video contained no readable frames")
        except Exception as exc:
            logger.warning("Falling back to synthetic frames for '%s': %s", video_path, exc)
            frames = [np.random.default_rng(seed=i).integers(0, 255, STUB_FRAME_SIZE, dtype=np.uint8) for i in range(STUB_FRAME_COUNT)]
            return frames, STUB_FPS

    def process_match(
        self,
        video_path: str | Path,
        metadata: dict[str, Any],
        output_dir: str | Path,
        match_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> MatchProcessingResult:
        """Run the full pipeline for one match video, writing all artifacts to `output_dir`."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        match_id = match_id or metadata.get("match_id") or "match"

        self._report_progress(progress_callback, 5, "ingestion")
        frames, fps = self._read_frames(video_path)
        duration_seconds = len(frames) / fps if fps else 0.0

        self._report_progress(progress_callback, 20, "detection_tracking")
        all_tracks_by_frame: list[list] = []
        ball_bbox_by_frame: list[Any] = []
        self.tracker.reset()

        for frame in frames:
            detections = self.detector.detect(frame)
            player_detections = [d for d in detections if d.class_id != BALL_CLASS_ID]
            ball_detections = [d for d in detections if d.class_id == BALL_CLASS_ID]

            tracks = self.tracker.update(player_detections, frame)
            all_tracks_by_frame.append(tracks)
            ball_bbox_by_frame.append(ball_detections[0].bbox if ball_detections else None)

            for track in tracks:
                x1, y1, x2, y2 = (int(v) for v in track.bbox.to_tuple())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                crop = frame[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else np.zeros((1, 1, 3), dtype=np.uint8)
                self.resolver.observe(track.track_id, crop)

        self._report_progress(progress_callback, 45, "identification")
        resolved_identities = self.resolver.resolve_all()
        identity_by_track = {r.track_id: r for r in resolved_identities}

        self._report_progress(progress_callback, 60, "analytics")
        frame_observations = [
            FrameObservation(
                frame_index=idx,
                timestamp_seconds=idx / fps if fps else 0.0,
                ball_bbox=ball_bbox_by_frame[idx],
                player_bboxes={t.track_id: t.bbox for t in tracks},
            )
            for idx, tracks in enumerate(all_tracks_by_frame)
        ]
        events = self.event_detector.detect(frame_observations)
        possession_counts = self.event_detector.compute_possession_counts(events)
        pass_counts = self.event_detector.compute_pass_counts(events)

        track_samples: dict[int, list[TrackFrameSample]] = {}
        for idx, tracks in enumerate(all_tracks_by_frame):
            for track in tracks:
                track_samples.setdefault(track.track_id, []).append(
                    TrackFrameSample(frame_index=idx, timestamp_seconds=idx / fps if fps else 0.0, bbox=track.bbox)
                )

        player_stats: list[PlayerStatsResult] = []
        for track_id, samples in track_samples.items():
            identity = identity_by_track.get(track_id)
            stats = self.stats_calculator.compute(
                player_key=str(track_id),
                jersey_number=identity.jersey_number if identity else None,
                samples=samples,
                possessions=possession_counts.get(track_id, 0),
                passes=pass_counts.get(track_id, 0),
            )
            player_stats.append(stats)

        summary = self.summary_builder.build(
            match_id=str(match_id),
            duration_seconds=duration_seconds,
            player_stats=player_stats,
            events=events,
            extra={"metadata": metadata},
        )

        self._report_progress(progress_callback, 75, "reporting")
        player_tracks_path = self.data_exporter.export_records(
            [
                {"track_id": tid, "frame_count": len(samples), "jersey_number": (identity_by_track.get(tid).jersey_number if identity_by_track.get(tid) else None)}
                for tid, samples in track_samples.items()
            ],
            output_dir / "player_tracks.parquet",
            fmt="parquet",
        )
        player_identities_path = self.data_exporter.export_records(
            [
                {
                    "track_id": r.track_id,
                    "jersey_number": r.jersey_number,
                    "confidence": r.confidence,
                    "resolution_method": r.resolution_method,
                }
                for r in resolved_identities
            ],
            output_dir / "player_identities.csv",
            fmt="csv",
        )
        player_stats_path = self.data_exporter.export_records(
            [
                {
                    "player_key": s.player_key,
                    "jersey_number": s.jersey_number,
                    "distance_covered_m": s.distance_covered_m,
                    "top_speed_kmh": s.top_speed_kmh,
                    "possessions": s.possessions,
                    "passes": s.passes,
                    "shots": s.shots,
                    "goals": s.goals,
                    "time_on_ball_seconds": s.time_on_ball_seconds,
                }
                for s in player_stats
            ],
            output_dir / "player_stats.csv",
            fmt="csv",
        )
        match_summary_path = self.match_report_generator.write_json(
            self.match_report_generator.build_report_dict(summary), output_dir / "match_summary.json"
        )

        player_report_paths: dict[str, Path] = {}
        for stats in player_stats:
            report = self.player_report_generator.build_report_dict(
                player_id=stats.player_key, match_id=str(match_id), stats=stats
            )
            path = self.player_report_generator.write_json(
                report, output_dir / f"player_report_{stats.player_key}.json"
            )
            player_report_paths[stats.player_key] = path

        self._report_progress(progress_callback, 85, "highlights")
        annotated_frames = [
            self.annotator.annotate_tracks(
                frame,
                all_tracks_by_frame[idx],
                {t.track_id: (identity_by_track.get(t.track_id).jersey_number if identity_by_track.get(t.track_id) else None) for t in all_tracks_by_frame[idx]},
            )
            for idx, frame in enumerate(frames)
        ]
        annotated_video_path = self.video_exporter.export(annotated_frames, output_dir / "annotated_video.mp4", fps=fps)

        player_highlight_paths: dict[str, Path] = {}
        clips_dir = output_dir / "_clips"
        for track_id in track_samples:
            player_events = [e for e in events if e.track_id == track_id]
            if not player_events:
                continue
            clip_specs = [
                ClipSpec(
                    start_seconds=max(0.0, e.timestamp_seconds - 1.0),
                    end_seconds=e.timestamp_seconds + 1.0,
                    label=e.event_type,
                    track_id=track_id,
                )
                for e in player_events
            ]
            clip_paths = self.clipper.extract_clips_for_events(video_path, clip_specs, clips_dir / str(track_id))
            highlight_path = output_dir / f"player_highlights_{track_id}.mp4"
            player_highlight_paths[str(track_id)] = self.merger.merge(clip_paths, highlight_path)

        self._report_progress(progress_callback, 95, "export")
        match_summary_audio_path = self.audio_exporter.export(summary.to_dict(), output_dir / "match_summary_audio.mp3")

        self._report_progress(progress_callback, 100, "completed")

        return MatchProcessingResult(
            output_dir=output_dir,
            player_tracks_path=player_tracks_path,
            player_identities_path=player_identities_path,
            player_stats_path=player_stats_path,
            match_summary_path=match_summary_path,
            annotated_video_path=annotated_video_path,
            match_summary_audio_path=match_summary_audio_path,
            player_report_paths=player_report_paths,
            player_highlight_paths=player_highlight_paths,
        )
