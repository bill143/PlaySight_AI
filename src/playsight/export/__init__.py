"""Annotated video MP4 and audio summary MP3 export (CONTRACTS.md section 7).

Public interface::

    export.render_annotated_video(video_path, tracks_df, identities, out_path) -> Path
    export.render_audio_summary(summary, out_path) -> Path
"""

from playsight.export.annotate import render_annotated_video
from playsight.export.audio import (
    build_narration,
    render_audio_summary,
    render_audio_summary_detailed,
)

__all__ = [
    "build_narration",
    "render_annotated_video",
    "render_audio_summary",
    "render_audio_summary_detailed",
]
