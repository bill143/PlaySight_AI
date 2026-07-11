"""Jersey-number OCR engines: EasyOCR (lazy, ``[cv]`` extra) and a deterministic stub."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import cv2
import numpy as np

from playsight.config.settings import Settings
from playsight.core.logging import get_logger

#: Jersey numbers are 1..99 (one or two digits).
_MIN_JERSEY = 1
_MAX_JERSEY = 99

#: Crops are upscaled so their height is at least this many pixels before OCR.
_OCR_MIN_HEIGHT = 64


@runtime_checkable
class OcrEngine(Protocol):
    """Structural interface for jersey-number readers.

    Attributes:
        name: Engine name reported in artifact metadata (``"easyocr"`` / ``"stub"``).
    """

    name: str

    def read_track(self, track_id: int, crops: Sequence[np.ndarray]) -> tuple[int | None, float]:
        """Estimate the jersey number for one track from its sampled crops.

        Args:
            track_id: The track id (used by the stub for determinism).
            crops: Jersey-region BGR crops sampled for the track.

        Returns:
            ``(jersey_number, confidence)`` — number is None when unreadable.
        """
        ...


class EasyOcrEngine:
    """EasyOCR digit reader with weighted majority voting (``name == "easyocr"``).

    The ``easyocr`` package is imported lazily on first use. Reads are
    restricted to a digits-only allowlist; per-crop candidates vote for a
    jersey number weighted by their OCR confidence.
    """

    name = "easyocr"

    def __init__(
        self, min_crop_confidence: float = 0.2, min_track_confidence: float = 0.25
    ) -> None:
        """Create an EasyOCR engine.

        Args:
            min_crop_confidence: Per-crop OCR results below this are discarded.
            min_track_confidence: Final voted confidence below this yields None.
        """
        self.min_crop_confidence = min_crop_confidence
        self.min_track_confidence = min_track_confidence
        self._reader: Any = None

    def _ensure_reader(self) -> Any:
        """Create the EasyOCR reader on first use (heavy import, model load)."""
        if self._reader is None:
            import easyocr  # heavy import: lazy by contract

            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            get_logger(__name__).info("easyocr_reader_loaded", languages=["en"])
        return self._reader

    def read_track(self, track_id: int, crops: Sequence[np.ndarray]) -> tuple[int | None, float]:
        """Vote a jersey number for one track from OCR over its crops.

        Each crop contributes digit candidates weighted by OCR confidence.
        The winning number's confidence is
        ``vote_share * mean_confidence_of_winning_votes``.

        Args:
            track_id: The track id (unused; kept for interface parity).
            crops: Jersey-region BGR crops for the track.

        Returns:
            ``(jersey_number, confidence)``; ``(None, 0.0)`` when no readable
            digits pass the confidence thresholds.
        """
        if not crops:
            return None, 0.0
        reader = self._ensure_reader()
        votes: dict[int, list[float]] = {}
        for crop in crops:
            prepared = _prepare_for_ocr(crop)
            if prepared is None:
                continue
            try:
                results = reader.readtext(
                    prepared, allowlist="0123456789", detail=1, paragraph=False
                )
            except Exception as exc:
                get_logger(__name__).warning("easyocr_read_failed", error=str(exc))
                continue
            for _bbox, text, raw_conf in results:
                candidate = str(text).strip()
                conf = float(raw_conf)
                if not candidate.isdigit() or conf < self.min_crop_confidence:
                    continue
                number = int(candidate)
                if _MIN_JERSEY <= number <= _MAX_JERSEY:
                    votes.setdefault(number, []).append(conf)

        if not votes:
            return None, 0.0
        total_weight = sum(sum(confs) for confs in votes.values())
        # Deterministic winner: highest total weight, lowest number on ties.
        number, confs = max(votes.items(), key=lambda item: (sum(item[1]), -item[0]))
        vote_share = sum(confs) / total_weight if total_weight > 0 else 0.0
        confidence = round(vote_share * (sum(confs) / len(confs)), 4)
        if confidence < self.min_track_confidence:
            return None, 0.0
        return number, confidence


class StubOcr:
    """Deterministic stand-in OCR engine (``name == "stub"``).

    Derives a stable fake jersey number from the track id so the pipeline runs
    end-to-end without the ``[cv]`` extra. Its output is never marked
    ``method="ocr"`` — see ``identify_tracks``.
    """

    name = "stub"

    #: Fixed confidence assigned to stub-derived numbers (honestly low).
    confidence = 0.4

    def read_track(self, track_id: int, crops: Sequence[np.ndarray]) -> tuple[int | None, float]:
        """Return a stable fake jersey number derived from ``track_id``.

        Args:
            track_id: The track id (the only input the stub uses).
            crops: Ignored.

        Returns:
            ``(number, confidence)`` with number in 1..99, injective for up to
            99 distinct track ids (7 is coprime with 99).
        """
        number = (track_id * 7) % 99 + 1
        return number, self.confidence


def _prepare_for_ocr(crop: np.ndarray | None) -> np.ndarray | None:
    """Upscale small crops so digit strokes are readable; None when degenerate."""
    if crop is None or crop.size == 0:
        return None
    height = int(crop.shape[0])
    if height <= 0 or int(crop.shape[1]) <= 0:
        return None
    if height >= _OCR_MIN_HEIGHT:
        return crop
    scale = _OCR_MIN_HEIGHT / float(height)
    return cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _easyocr_available() -> bool:
    """Return whether the easyocr package is importable (without importing it)."""
    try:
        return importlib.util.find_spec("easyocr") is not None
    except (ImportError, ValueError):  # pragma: no cover - broken partial installs
        return False


def ocr_engine_name(settings: Settings | None = None) -> str:
    """Return the OCR engine name that ``create_ocr`` would pick (no heavy imports).

    Args:
        settings: Unused today; accepted for factory symmetry.

    Returns:
        ``"easyocr"`` when the ``[cv]`` extra is installed, else ``"stub"``.
    """
    return "easyocr" if _easyocr_available() else "stub"


def create_ocr(settings: Settings | None = None) -> OcrEngine:
    """Create the best available OCR engine and log the choice.

    Args:
        settings: Unused today; accepted so callers pass application settings
            uniformly across factories.

    Returns:
        An :class:`EasyOcrEngine` when the ``[cv]`` extra is installed,
        otherwise a deterministic :class:`StubOcr`.
    """
    log = get_logger(__name__)
    engine: OcrEngine
    if _easyocr_available():
        engine = EasyOcrEngine()
        log.info("ocr_engine_selected", engine="easyocr")
    else:
        engine = StubOcr()
        log.info("ocr_engine_selected", engine="stub", reason="easyocr not installed ([cv] extra)")
    return engine
