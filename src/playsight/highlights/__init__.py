"""Per-player highlight reel building (ffmpeg), CONTRACTS.md section 7.

Public interface::

    highlights.build_player_highlights(video_path, events, identity, out_path) -> Path
"""

from playsight.highlights.builder import (
    build_player_highlights,
    merge_time_windows,
    select_event_windows,
)
from playsight.highlights.ffmpeg_util import ffmpeg_available, resolve_ffmpeg, run_ffmpeg

__all__ = [
    "build_player_highlights",
    "ffmpeg_available",
    "merge_time_windows",
    "resolve_ffmpeg",
    "run_ffmpeg",
    "select_event_windows",
]
