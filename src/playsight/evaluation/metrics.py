"""Offline metrics: detection PR, track continuity, and identification accuracy.

Ground-truth format (CSV):

- Required columns: ``frame_index, x1, y1, x2, y2`` (absolute pixels).
- Optional column ``gt_id`` (a stable ground-truth identity per box) enables
  id-switch / fragmentation metrics.

Identification labels format (CSV): columns ``track_id, jersey_number``.

All functions are pure and CI-safe (no video decoding, no ``[cv]`` extra).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.core.types import IdentityResult
from playsight.tracking.simple import iou_matrix

_BOX_COLUMNS = ["x1", "y1", "x2", "y2"]
_GT_REQUIRED_COLUMNS = {"frame_index", "x1", "y1", "x2", "y2"}


def detection_precision_recall(
    pred_df: pd.DataFrame,
    gt_df: pd.DataFrame,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute detection precision/recall against ground-truth boxes.

    Per frame, predictions (highest confidence first when a ``confidence``
    column exists) are greedily matched to unmatched ground-truth boxes at
    ``iou >= iou_threshold``. Matched pairs are true positives; leftover
    predictions are false positives; leftover ground truth are false negatives.

    Args:
        pred_df: Predicted boxes with columns ``frame_index, x1, y1, x2, y2``
            (optionally ``confidence``); a tracks dataframe works directly.
        gt_df: Ground-truth boxes with columns ``frame_index, x1, y1, x2, y2``.
        iou_threshold: Minimum IOU for a prediction to count as a match.

    Returns:
        Dict with ``precision, recall, f1, tp, fp, fn, iou_threshold``.
    """
    tp = fp = fn = 0
    pred_frames = set(pred_df["frame_index"].unique()) if not pred_df.empty else set()
    gt_frames = set(gt_df["frame_index"].unique()) if not gt_df.empty else set()
    for frame_index in sorted(pred_frames | gt_frames):
        preds = pred_df[pred_df["frame_index"] == frame_index] if not pred_df.empty else pred_df
        gts = gt_df[gt_df["frame_index"] == frame_index] if not gt_df.empty else gt_df
        if not preds.empty and "confidence" in preds.columns:
            preds = preds.sort_values("confidence", ascending=False)
        matched = _greedy_match_count(
            preds[_BOX_COLUMNS].to_numpy(dtype=np.float64) if not preds.empty else None,
            gts[_BOX_COLUMNS].to_numpy(dtype=np.float64) if not gts.empty else None,
            iou_threshold,
        )
        tp += matched
        fp += (0 if preds.empty else len(preds)) - matched
        fn += (0 if gts.empty else len(gts)) - matched

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou_threshold": iou_threshold,
    }


def count_id_switches(
    tracks_df: pd.DataFrame,
    gt_df: pd.DataFrame,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Count identity switches and fragmentations against labeled ground truth.

    Per frame, ground-truth boxes are greedily matched to track boxes by IOU.
    An **id switch** is counted when a ground-truth identity's matched
    ``track_id`` differs from the previous track it was matched to. A
    **fragmentation** is counted every time a ground-truth identity resumes
    being matched after one or more unmatched frames.

    Args:
        tracks_df: Tracks dataframe (contract columns).
        gt_df: Ground truth with columns
            ``frame_index, gt_id, x1, y1, x2, y2``.
        iou_threshold: Minimum IOU for a ground-truth box to match a track box.

    Returns:
        Dict with ``id_switches, fragmentations, gt_ids, matched_frames,
        gt_boxes, iou_threshold``.

    Raises:
        ValidationFailed: ``gt_df`` has no ``gt_id`` column.
    """
    if "gt_id" not in gt_df.columns:
        raise ValidationFailed("ground truth needs a gt_id column for id-switch metrics")

    last_track: dict[Any, int] = {}
    matched_previous_frame: dict[Any, bool] = {}
    seen_once: set[Any] = set()
    id_switches = 0
    fragmentations = 0
    matched_frames = 0

    for frame_index in sorted(gt_df["frame_index"].unique()):
        gts = gt_df[gt_df["frame_index"] == frame_index]
        tracks = (
            tracks_df[tracks_df["frame_index"] == frame_index] if not tracks_df.empty else tracks_df
        )
        assignments = _greedy_match_pairs(
            gts[_BOX_COLUMNS].to_numpy(dtype=np.float64),
            tracks[_BOX_COLUMNS].to_numpy(dtype=np.float64) if not tracks.empty else None,
            iou_threshold,
        )
        track_ids = tracks["track_id"].to_list() if not tracks.empty else []
        gt_ids = gts["gt_id"].to_list()
        matched_now: set[Any] = set()
        for gt_pos, track_pos in assignments:
            gt_id = gt_ids[gt_pos]
            track_id = int(track_ids[track_pos])
            matched_now.add(gt_id)
            matched_frames += 1
            previous = last_track.get(gt_id)
            if previous is not None and previous != track_id:
                id_switches += 1
            if gt_id in seen_once and not matched_previous_frame.get(gt_id, False):
                fragmentations += 1
            last_track[gt_id] = track_id
            seen_once.add(gt_id)
        for gt_id in gt_ids:
            matched_previous_frame[gt_id] = gt_id in matched_now

    return {
        "id_switches": id_switches,
        "fragmentations": fragmentations,
        "gt_ids": int(gt_df["gt_id"].nunique()),
        "matched_frames": matched_frames,
        "gt_boxes": int(len(gt_df)),
        "iou_threshold": iou_threshold,
    }


def track_summary(tracks_df: pd.DataFrame) -> dict[str, Any]:
    """Summarize a tracks dataframe without ground truth.

    ``gap_count`` counts, per track, the times consecutive observations are
    further apart than the inferred frame stride (i.e. the track blinked out).

    Args:
        tracks_df: Tracks dataframe (contract columns).

    Returns:
        Dict with ``tracks, boxes, frames, mean_track_length,
        inferred_stride, gap_count``.
    """
    if tracks_df.empty:
        return {
            "tracks": 0,
            "boxes": 0,
            "frames": 0,
            "mean_track_length": 0.0,
            "inferred_stride": 1,
            "gap_count": 0,
        }

    frames = np.sort(tracks_df["frame_index"].unique())
    diffs = np.diff(frames)
    stride = int(diffs[diffs > 0].min()) if diffs.size and (diffs > 0).any() else 1

    gap_count = 0
    lengths: list[int] = []
    for _tid, group in tracks_df.groupby("track_id"):
        track_frames = np.sort(group["frame_index"].unique())
        lengths.append(int(track_frames.size))
        track_diffs = np.diff(track_frames)
        gap_count += int((track_diffs > stride).sum())

    return {
        "tracks": int(tracks_df["track_id"].nunique()),
        "boxes": int(len(tracks_df)),
        "frames": int(frames.size),
        "mean_track_length": round(float(np.mean(lengths)), 2) if lengths else 0.0,
        "inferred_stride": stride,
        "gap_count": gap_count,
    }


def identification_accuracy(
    identities: Sequence[IdentityResult],
    labels_path: str | Path,
) -> dict[str, Any]:
    """Score identification results against a labeled CSV.

    Args:
        identities: Identity results (one per track).
        labels_path: CSV with columns ``track_id, jersey_number`` giving the
            true jersey number per track.

    Returns:
        Dict with ``labeled, resolved, correct, accuracy`` (correct over all
        labeled tracks — unresolved counts as wrong) and
        ``precision_resolved`` (correct over resolved-and-labeled tracks).

    Raises:
        NotFoundError: The labels file does not exist.
        ValidationFailed: The labels file lacks required columns.
    """
    path = Path(labels_path)
    if not path.is_file():
        raise NotFoundError(f"identification labels not found: {path}")
    labels = pd.read_csv(path)
    if not {"track_id", "jersey_number"}.issubset(labels.columns):
        raise ValidationFailed("labels csv must have columns: track_id, jersey_number")

    truth = {
        int(row["track_id"]): int(row["jersey_number"])
        for _, row in labels.iterrows()
        if pd.notna(row["jersey_number"])
    }
    predicted = {identity.track_id: identity.jersey_number for identity in identities}

    labeled = len(truth)
    resolved = 0
    correct = 0
    for track_id, true_number in truth.items():
        guess = predicted.get(track_id)
        if guess is None:
            continue
        resolved += 1
        if int(guess) == true_number:
            correct += 1

    return {
        "labeled": labeled,
        "resolved": resolved,
        "correct": correct,
        "accuracy": round(correct / labeled, 4) if labeled else 0.0,
        "precision_resolved": round(correct / resolved, 4) if resolved else 0.0,
    }


def evaluate_run(tracks_df: pd.DataFrame, gt_path: str | Path) -> dict[str, Any]:
    """Evaluate a pipeline run's tracks against a ground-truth CSV.

    Offline tooling: intended for engineers benchmarking detector/tracker
    quality on hand-labeled clips, not for the runtime pipeline.

    Args:
        tracks_df: Tracks dataframe (contract columns:
            ``frame_index, t_s, track_id, x1, y1, x2, y2, confidence``).
        gt_path: Ground-truth CSV path. Required columns
            ``frame_index, x1, y1, x2, y2``; optional ``gt_id`` enables
            id-switch / fragmentation metrics.

    Returns:
        Dict with keys ``tracks`` (unsupervised summary), ``detection``
        (precision/recall), and — when ``gt_id`` is present — ``tracking``
        (id switches / fragmentations), plus ``gt_path``.

    Raises:
        NotFoundError: The ground-truth file does not exist.
        ValidationFailed: The ground-truth file lacks required columns.
    """
    log = get_logger(__name__)
    path = Path(gt_path)
    if not path.is_file():
        raise NotFoundError(f"ground truth file not found: {path}")
    gt_df = pd.read_csv(path)
    missing = _GT_REQUIRED_COLUMNS - set(gt_df.columns)
    if missing:
        raise ValidationFailed(f"ground truth csv missing columns: {sorted(missing)}")

    report: dict[str, Any] = {
        "gt_path": str(path),
        "tracks": track_summary(tracks_df),
        "detection": detection_precision_recall(tracks_df, gt_df),
    }
    if "gt_id" in gt_df.columns:
        report["tracking"] = count_id_switches(tracks_df, gt_df)

    log.info(
        "evaluation_completed",
        gt_path=str(path),
        detection_f1=report["detection"]["f1"],
        has_tracking_metrics="tracking" in report,
    )
    return report


def _greedy_match_count(
    pred_boxes: np.ndarray | None,
    gt_boxes: np.ndarray | None,
    iou_threshold: float,
) -> int:
    """Count greedy one-to-one matches between prediction and GT boxes."""
    return len(_greedy_match_pairs(pred_boxes, gt_boxes, iou_threshold))


def _greedy_match_pairs(
    left_boxes: np.ndarray | None,
    right_boxes: np.ndarray | None,
    iou_threshold: float,
) -> list[tuple[int, int]]:
    """Greedily match rows of ``left_boxes`` to ``right_boxes`` by descending IOU.

    Args:
        left_boxes: Array ``(N, 4)`` or None/empty.
        right_boxes: Array ``(M, 4)`` or None/empty.
        iou_threshold: Minimum IOU to accept a pair.

    Returns:
        List of ``(left_index, right_index)`` pairs (each side used at most once),
        deterministic for identical inputs.
    """
    if left_boxes is None or right_boxes is None or len(left_boxes) == 0 or len(right_boxes) == 0:
        return []
    ious = iou_matrix(left_boxes, right_boxes)
    candidates = [
        (float(ious[li, ri]), li, ri)
        for li in range(ious.shape[0])
        for ri in range(ious.shape[1])
        if ious[li, ri] >= iou_threshold
    ]
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_left: set[int] = set()
    used_right: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _iou, li, ri in candidates:
        if li in used_left or ri in used_right:
            continue
        pairs.append((li, ri))
        used_left.add(li)
        used_right.add(ri)
    return pairs
