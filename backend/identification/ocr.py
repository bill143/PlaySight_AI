"""Jersey number OCR: EasyOCR primary, Tesseract fallback, deterministic stub for tests."""

from __future__ import annotations

import logging
import re

import numpy as np

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when easyocr is installed
    import easyocr  # type: ignore[import-not-found]

    _EASYOCR_AVAILABLE = True
except ImportError:  # pragma: no cover
    easyocr = None  # type: ignore[assignment]
    _EASYOCR_AVAILABLE = False

try:  # pragma: no cover - exercised only when pytesseract is installed
    import pytesseract  # type: ignore[import-not-found]

    _TESSERACT_AVAILABLE = True
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    _TESSERACT_AVAILABLE = False

_NUMBER_PATTERN = re.compile(r"\d{1,2}")


class JerseyOCR:
    """Detects a player's jersey number from a cropped image region."""

    def __init__(self, languages: list[str] | None = None, force_stub: bool = False) -> None:
        self.languages = languages or ["en"]
        self.force_stub = force_stub
        self._reader = None

        if not self.force_stub and _EASYOCR_AVAILABLE:
            try:
                self._reader = easyocr.Reader(self.languages, gpu=False)  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to initialize EasyOCR reader: %s", exc)
                self._reader = None

    @property
    def backend(self) -> str:
        if self._reader is not None:
            return "easyocr"
        if not self.force_stub and _TESSERACT_AVAILABLE:
            return "tesseract"
        return "stub"

    def detect_jersey_number(self, crop: np.ndarray) -> tuple[int | None, float]:
        """Detect a jersey number in an image crop, returning (number, confidence)."""
        if self._reader is not None:
            return self._detect_with_easyocr(crop)
        if not self.force_stub and _TESSERACT_AVAILABLE:
            return self._detect_with_tesseract(crop)
        return self._detect_stub(crop)

    def _detect_with_easyocr(self, crop: np.ndarray) -> tuple[int | None, float]:  # pragma: no cover - requires easyocr
        results = self._reader.readtext(crop)  # type: ignore[union-attr]
        best_number: int | None = None
        best_conf = 0.0
        for _bbox, text, conf in results:
            match = _NUMBER_PATTERN.search(text)
            if match and conf > best_conf:
                best_number = int(match.group())
                best_conf = float(conf)
        return best_number, best_conf

    def _detect_with_tesseract(self, crop: np.ndarray) -> tuple[int | None, float]:  # pragma: no cover - requires tesseract
        text = pytesseract.image_to_string(crop, config="--psm 7 digits")  # type: ignore[union-attr]
        match = _NUMBER_PATTERN.search(text)
        if match:
            return int(match.group()), 0.6
        return None, 0.0

    def _detect_stub(self, crop: np.ndarray) -> tuple[int | None, float]:
        """Deterministic pseudo-detection derived from crop statistics.

        Useful for tests: produces a stable "jersey number" (1-99) derived
        from the mean pixel intensity of the crop, with a fixed confidence.
        """
        if crop.size == 0:
            return None, 0.0
        mean_intensity = float(np.mean(crop))
        number = int(mean_intensity) % 99 + 1
        return number, 0.5
