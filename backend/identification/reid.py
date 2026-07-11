"""Re-ID embedding extraction and similarity matching for player identification."""

from __future__ import annotations

import numpy as np


class ReIDEmbedder:
    """Extracts an appearance embedding for a player crop.

    In production this would wrap a trained Re-ID CNN (e.g. OSNet). For the
    MVP we use a deterministic, dependency-free color-histogram embedding so
    the rest of the identification pipeline (similarity matching, identity
    resolution) can be built and tested end-to-end without a GPU.
    """

    def __init__(self, embedding_size: int = 32) -> None:
        self.embedding_size = embedding_size

    def extract(self, crop: np.ndarray) -> np.ndarray:
        """Compute a normalized color-histogram embedding for an image crop."""
        if crop.size == 0:
            return np.zeros(self.embedding_size, dtype=np.float32)

        channels = crop.shape[2] if crop.ndim == 3 else 1
        bins_per_channel = max(1, self.embedding_size // max(channels, 1))
        histograms = []

        for c in range(channels):
            channel_data = crop[..., c] if crop.ndim == 3 else crop
            hist, _ = np.histogram(channel_data, bins=bins_per_channel, range=(0, 255))
            histograms.append(hist.astype(np.float32))

        embedding = np.concatenate(histograms)[: self.embedding_size]
        if embedding.shape[0] < self.embedding_size:
            embedding = np.pad(embedding, (0, self.embedding_size - embedding.shape[0]))

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class ReIDMatcher:
    """Matches new embeddings against a gallery of known player embeddings."""

    def __init__(self, similarity_threshold: float = 0.75) -> None:
        self.similarity_threshold = similarity_threshold
        self._gallery: dict[str, np.ndarray] = {}

    def register(self, identity_key: str, embedding: np.ndarray) -> None:
        """Add or update a gallery entry for a known identity."""
        self._gallery[identity_key] = embedding

    def match(self, embedding: np.ndarray) -> tuple[str | None, float]:
        """Find the best-matching gallery identity for `embedding`, if any."""
        best_key: str | None = None
        best_score = 0.0

        for key, gallery_embedding in self._gallery.items():
            score = cosine_similarity(embedding, gallery_embedding)
            if score > best_score:
                best_score = score
                best_key = key

        if best_score >= self.similarity_threshold:
            return best_key, best_score
        return None, best_score
