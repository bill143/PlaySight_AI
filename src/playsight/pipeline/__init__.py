"""Pipeline orchestration (CONTRACTS.md section 7).

Public interface::

    pipeline.run_match_pipeline(match_id, video_path, *, db_session_factory,
                                settings, progress_cb=None) -> PipelineResult
"""

from playsight.core.types import PipelineResult
from playsight.pipeline.artifacts import (
    content_type_for,
    outputs_dir,
    register_artifact,
    resolve_match_video,
)
from playsight.pipeline.runner import TRACKS_DTYPES, run_match_pipeline

__all__ = [
    "TRACKS_DTYPES",
    "PipelineResult",
    "content_type_for",
    "outputs_dir",
    "register_artifact",
    "resolve_match_video",
    "run_match_pipeline",
]
