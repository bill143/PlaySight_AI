"""Appearance Re-ID: HSV color-histogram embeddings + cosine similarity.

This is deliberately simple, deterministic, and biometric-free: embeddings
describe *kit colors* (hue/saturation of the jersey region), never faces or
bodies (CONTRACTS.md section 18).
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

#: HSV histogram bins: 16 hue x 8 saturation = 128-d embedding.
_HUE_BINS = 16
_SAT_BINS = 8

#: Cosine similarity at or above this merges an unresolved track into a
#: resolved one (embeddings are kit-color histograms, so be strict).
REID_SIMILARITY_THRESHOLD = 0.9


def hsv_embedding(crops: Sequence[np.ndarray]) -> np.ndarray | None:
    """Build an L2-normalized HSV color-histogram embedding for a track.

    Each crop contributes an L1-normalized 2D hue/saturation histogram; the
    track embedding is the mean histogram, L2-normalized so cosine similarity
    is a dot product.

    Args:
        crops: Jersey-region BGR crops sampled for the track.

    Returns:
        A 128-d float64 unit vector, or None when no usable crop exists.
    """
    histograms: list[np.ndarray] = []
    for crop in crops:
        if crop is None or crop.size == 0:
            continue
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [_HUE_BINS, _SAT_BINS], [0, 180, 0, 256])
        flat = hist.flatten().astype(np.float64)
        total = float(flat.sum())
        if total <= 0:
            continue
        histograms.append(flat / total)
    if not histograms:
        return None
    embedding = np.mean(np.stack(histograms), axis=0)
    norm = float(np.linalg.norm(embedding))
    if norm <= 0:
        return None
    return embedding / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two embeddings, clipped to ``[0, 1]``.

    Args:
        a: First embedding (any norm).
        b: Second embedding (any norm).

    Returns:
        Cosine similarity; 0.0 when either vector has zero norm.
    """
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    value = float(np.dot(a, b) / (norm_a * norm_b))
    return max(0.0, min(1.0, value))
