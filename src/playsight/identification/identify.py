"""Track identification orchestration: OCR voting + appearance Re-ID fallback.

``method`` semantics per CONTRACTS.md:

- ``"ocr"``     — a REAL OCR engine (EasyOCR) read the number.
- ``"reid"``    — appearance-based assignment (cluster merge with a resolved
  track), or a deterministic stub-derived number when the ``[cv]`` extra is
  not installed. Never claims OCR provenance.
- ``"unresolved"`` — no confident estimate; ``jersey_number`` is None.

``player_id`` is left None here: mapping jersey numbers to roster players
requires DB access and belongs to the pipeline orchestrator.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from playsight.config.settings import Settings
from playsight.core.logging import get_logger
from playsight.core.types import IdentityResult
from playsight.identification.crops import MAX_CROPS_PER_TRACK, sample_track_crops
from playsight.identification.ocr import EasyOcrEngine, create_ocr
from playsight.identification.reid import (
    REID_SIMILARITY_THRESHOLD,
    cosine_similarity,
    hsv_embedding,
)


def identify_tracks(
    video_path: str | Path,
    tracks_df: pd.DataFrame,
    settings: Settings,
) -> list[IdentityResult]:
    """Estimate a jersey number (and confidence) for every track.

    Steps:

    1. Sample up to K=12 jersey-region crops per track from the video.
    2. Run the OCR engine (EasyOCR if installed, deterministic stub otherwise)
       with digit-only allowlist and confidence-weighted majority voting.
    3. Tracks unresolved by real OCR fall back to appearance Re-ID: HSV
       color-histogram embeddings are compared by cosine similarity and an
       unresolved track inherits the number of its most similar resolved track.
    4. Anything still without a confident estimate is returned as
       ``method="unresolved"``.

    No face recognition is used at any step. Results are estimates, never
    ground truth.

    Args:
        video_path: Local path of the source video (crops are sampled from it;
            when unreadable, identification degrades gracefully).
        tracks_df: Tracks dataframe with columns
            ``frame_index, t_s, track_id, x1, y1, x2, y2, confidence``.
        settings: Application settings (reserved for future tuning knobs).

    Returns:
        One :class:`IdentityResult` per distinct ``track_id``, sorted by
        track id. ``player_id`` is always None at this stage.
    """
    log = get_logger(__name__)
    if tracks_df.empty:
        log.info("identify_tracks_empty_input", video_path=str(video_path))
        return []

    track_ids = sorted(int(tid) for tid in tracks_df["track_id"].unique())
    crops = sample_track_crops(video_path, tracks_df, max_crops_per_track=MAX_CROPS_PER_TRACK)
    engine = create_ocr(settings)
    real_ocr = isinstance(engine, EasyOcrEngine)

    embeddings: dict[int, np.ndarray | None] = {
        tid: hsv_embedding(crops.get(tid, [])) for tid in track_ids
    }

    results: dict[int, IdentityResult] = {}
    resolved_ids: list[int] = []
    for tid in track_ids:
        number, confidence = engine.read_track(tid, crops.get(tid, []))
        if number is None:
            continue
        # Only a real OCR engine may claim method="ocr"; stub-derived numbers
        # are reported as "reid" (appearance-level trust at best).
        method = "ocr" if real_ocr else "reid"
        results[tid] = IdentityResult(
            track_id=tid,
            jersey_number=number,
            player_id=None,
            confidence=round(float(confidence), 4),
            method=method,
        )
        resolved_ids.append(tid)

    reid_merges = 0
    for tid in track_ids:
        if tid in results:
            continue
        merged = _merge_by_appearance(tid, resolved_ids, embeddings, results)
        if merged is not None:
            results[tid] = merged
            reid_merges += 1
        else:
            results[tid] = IdentityResult(
                track_id=tid,
                jersey_number=None,
                player_id=None,
                confidence=0.0,
                method="unresolved",
            )

    ordered = [results[tid] for tid in track_ids]
    log.info(
        "tracks_identified",
        video_path=str(video_path),
        engine=engine.name,
        tracks=len(track_ids),
        ocr_resolved=len(resolved_ids) if real_ocr else 0,
        stub_assigned=len(resolved_ids) if not real_ocr else 0,
        reid_merged=reid_merges,
        unresolved=sum(1 for r in ordered if r.method == "unresolved"),
    )
    return ordered


def _merge_by_appearance(
    track_id: int,
    resolved_ids: list[int],
    embeddings: dict[int, np.ndarray | None],
    results: dict[int, IdentityResult],
) -> IdentityResult | None:
    """Try to inherit an identity from the most similar resolved track.

    Args:
        track_id: The unresolved track.
        resolved_ids: Tracks already carrying a jersey number.
        embeddings: Per-track HSV embeddings (None when no crops were usable).
        results: Existing identity results for resolved tracks.

    Returns:
        A ``method="reid"`` result when the best cosine similarity reaches
        ``REID_SIMILARITY_THRESHOLD``, else None.
    """
    embedding = embeddings.get(track_id)
    if embedding is None:
        return None
    best_id: int | None = None
    best_similarity = 0.0
    for candidate in resolved_ids:
        candidate_embedding = embeddings.get(candidate)
        if candidate_embedding is None:
            continue
        similarity = cosine_similarity(embedding, candidate_embedding)
        if similarity > best_similarity:
            best_similarity = similarity
            best_id = candidate
    if best_id is None or best_similarity < REID_SIMILARITY_THRESHOLD:
        return None
    source = results[best_id]
    return IdentityResult(
        track_id=track_id,
        jersey_number=source.jersey_number,
        player_id=None,
        confidence=round(source.confidence * best_similarity, 4),
        method="reid",
    )
