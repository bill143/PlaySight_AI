"""Small shared helpers for the reporting package (private)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


def event_type_value(event_type: object) -> str:
    """Return the plain string value for an event type (str or EventType enum)."""
    return str(event_type.value) if isinstance(event_type, Enum) else str(event_type)


def format_clock(seconds: float) -> str:
    """Format a time offset in seconds as an ``MM:SS`` match-clock string."""
    total = max(0, int(round(float(seconds))))
    return f"{total // 60:02d}:{total % 60:02d}"


def ensure_out_dir(out_dir: Path | str) -> Path:
    """Return ``out_dir`` as a :class:`Path`, creating it (and parents) if needed."""
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
