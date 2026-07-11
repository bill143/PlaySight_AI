"""Track identification: jersey-number OCR with appearance Re-ID fallback.

Public interface (CONTRACTS.md section 7):

- ``identify_tracks(video_path, tracks_df, settings) -> list[IdentityResult]``

Identification is jersey OCR (EasyOCR when the ``[cv]`` extra is installed)
plus HSV color-histogram appearance embeddings. **No face recognition is used
anywhere** (CONTRACTS.md section 18). Results are estimated identities,
confidence-scored — never ground truth.
"""

from playsight.core.types import IdentityResult
from playsight.identification.identify import identify_tracks
from playsight.identification.ocr import (
    EasyOcrEngine,
    OcrEngine,
    StubOcr,
    create_ocr,
    ocr_engine_name,
)

__all__ = [
    "EasyOcrEngine",
    "IdentityResult",
    "OcrEngine",
    "StubOcr",
    "create_ocr",
    "identify_tracks",
    "ocr_engine_name",
]
