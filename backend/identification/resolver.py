"""Identity resolution pipeline: maps tracker output to canonical player identities.

Combines jersey-number OCR (primary signal) with Re-ID embedding similarity
(secondary signal, used when OCR is inconclusive or to keep identities
consistent across occlusions) to resolve each track to a stable player
identity for the whole match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backend.identification.ocr import JerseyOCR
from backend.identification.reid import ReIDEmbedder, ReIDMatcher


@dataclass
class TrackObservation:
    """A single frame's observation of a track, used for identity resolution."""

    track_id: int
    crop: np.ndarray


@dataclass
class ResolvedIdentity:
    """The resolved identity for a track after aggregating all its observations."""

    track_id: int
    jersey_number: int | None
    confidence: float
    resolution_method: str
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(1, dtype=np.float32))


class IdentityResolver:
    """Aggregates per-frame OCR/Re-ID signals into one identity per track."""

    def __init__(self, ocr: JerseyOCR | None = None, embedder: ReIDEmbedder | None = None, matcher: ReIDMatcher | None = None) -> None:
        self.ocr = ocr or JerseyOCR()
        self.embedder = embedder or ReIDEmbedder()
        self.matcher = matcher or ReIDMatcher()
        self._track_votes: dict[int, dict[int, list[float]]] = {}
        self._track_embeddings: dict[int, list[np.ndarray]] = {}

    def observe(self, track_id: int, crop: np.ndarray) -> None:
        """Record one observation (crop) of a track from a single video frame."""
        number, conf = self.ocr.detect_jersey_number(crop)
        if number is not None:
            self._track_votes.setdefault(track_id, {}).setdefault(number, []).append(conf)

        embedding = self.embedder.extract(crop)
        self._track_embeddings.setdefault(track_id, []).append(embedding)

    def resolve(self, track_id: int) -> ResolvedIdentity:
        """Resolve the final identity for a track from all recorded observations."""
        votes = self._track_votes.get(track_id, {})
        embeddings = self._track_embeddings.get(track_id, [])
        avg_embedding = (
            np.mean(np.stack(embeddings), axis=0) if embeddings else np.zeros(self.embedder.embedding_size, dtype=np.float32)
        )

        if votes:
            best_number = max(votes, key=lambda n: (len(votes[n]), sum(votes[n])))
            confidences = votes[best_number]
            confidence = sum(confidences) / len(confidences)
            return ResolvedIdentity(
                track_id=track_id,
                jersey_number=best_number,
                confidence=round(confidence, 4),
                resolution_method="ocr",
                embedding=avg_embedding,
            )

        matched_key, score = self.matcher.match(avg_embedding)
        if matched_key is not None:
            try:
                jersey_number = int(matched_key)
            except ValueError:
                jersey_number = None
            return ResolvedIdentity(
                track_id=track_id,
                jersey_number=jersey_number,
                confidence=round(score, 4),
                resolution_method="reid",
                embedding=avg_embedding,
            )

        return ResolvedIdentity(
            track_id=track_id,
            jersey_number=None,
            confidence=0.0,
            resolution_method="unresolved",
            embedding=avg_embedding,
        )

    def resolve_all(self) -> list[ResolvedIdentity]:
        """Resolve identities for every track observed so far."""
        return [self.resolve(track_id) for track_id in self._track_votes.keys() | self._track_embeddings.keys()]
