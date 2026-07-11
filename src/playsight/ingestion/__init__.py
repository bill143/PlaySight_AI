"""Video ingestion: probing, object-storage registration, and frame iteration.

Public interface (CONTRACTS.md section 7):

- ``probe_video(path) -> VideoInfo``
- ``ingest_video(path, match_id, storage, db) -> VideoAsset``
- ``iter_frames(path, stride, max_frames)`` yielding ``(frame_index, t_s, frame_bgr)``
"""

from playsight.core.types import VideoInfo
from playsight.ingestion.frames import iter_frames
from playsight.ingestion.ingest import ingest_video
from playsight.ingestion.probe import probe_video

__all__ = ["VideoInfo", "ingest_video", "iter_frames", "probe_video"]
