"""Unit tests for the identification package."""

from __future__ import annotations

import numpy as np

from backend.identification.ocr import JerseyOCR
from backend.identification.reid import ReIDEmbedder, ReIDMatcher, cosine_similarity
from backend.identification.resolver import IdentityResolver


class TestJerseyOCR:
    def test_stub_mode_returns_deterministic_result(self, sample_frame: np.ndarray) -> None:
        ocr = JerseyOCR(force_stub=True)
        number1, conf1 = ocr.detect_jersey_number(sample_frame)
        number2, conf2 = ocr.detect_jersey_number(sample_frame)
        assert number1 == number2
        assert conf1 == conf2
        assert number1 is not None
        assert 1 <= number1 <= 99

    def test_empty_crop_returns_none(self) -> None:
        ocr = JerseyOCR(force_stub=True)
        number, confidence = ocr.detect_jersey_number(np.zeros((0, 0, 3), dtype=np.uint8))
        assert number is None
        assert confidence == 0.0

    def test_backend_is_stub_when_forced(self) -> None:
        ocr = JerseyOCR(force_stub=True)
        assert ocr.backend == "stub"


class TestReIDEmbedder:
    def test_extract_returns_normalized_vector(self, sample_frame: np.ndarray) -> None:
        embedder = ReIDEmbedder(embedding_size=16)
        embedding = embedder.extract(sample_frame)
        assert embedding.shape == (16,)
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 1e-5 or norm == 0.0

    def test_extract_empty_crop_returns_zeros(self) -> None:
        embedder = ReIDEmbedder(embedding_size=8)
        embedding = embedder.extract(np.zeros((0, 0, 3), dtype=np.uint8))
        assert np.all(embedding == 0)

    def test_cosine_similarity_identical_vectors(self) -> None:
        vec = np.array([1.0, 2.0, 3.0])
        assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-9

    def test_cosine_similarity_zero_vector(self) -> None:
        assert cosine_similarity(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 0.0


class TestReIDMatcher:
    def test_match_above_threshold(self) -> None:
        matcher = ReIDMatcher(similarity_threshold=0.5)
        embedding = np.array([1.0, 0.0, 0.0])
        matcher.register("player_7", embedding)
        matched_key, score = matcher.match(embedding)
        assert matched_key == "player_7"
        assert score > 0.9

    def test_no_match_below_threshold(self) -> None:
        matcher = ReIDMatcher(similarity_threshold=0.99)
        matcher.register("player_7", np.array([1.0, 0.0, 0.0]))
        matched_key, _score = matcher.match(np.array([0.0, 1.0, 0.0]))
        assert matched_key is None


class TestIdentityResolver:
    def test_resolve_uses_ocr_when_available(self, sample_frame: np.ndarray) -> None:
        resolver = IdentityResolver(ocr=JerseyOCR(force_stub=True))
        resolver.observe(track_id=1, crop=sample_frame)
        resolver.observe(track_id=1, crop=sample_frame)

        identity = resolver.resolve(track_id=1)
        assert identity.resolution_method == "ocr"
        assert identity.jersey_number is not None
        assert identity.confidence > 0

    def test_resolve_unobserved_track_is_unresolved(self) -> None:
        resolver = IdentityResolver()
        identity = resolver.resolve(track_id=999)
        assert identity.resolution_method == "unresolved"
        assert identity.jersey_number is None

    def test_resolve_all_returns_all_tracks(self, sample_frame: np.ndarray) -> None:
        resolver = IdentityResolver(ocr=JerseyOCR(force_stub=True))
        resolver.observe(track_id=1, crop=sample_frame)
        resolver.observe(track_id=2, crop=sample_frame)

        identities = resolver.resolve_all()
        assert {i.track_id for i in identities} == {1, 2}
