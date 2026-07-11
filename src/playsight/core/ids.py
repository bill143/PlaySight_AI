"""ID generation helpers."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a new 32-character uuid4 hex string (canonical DB primary key)."""
    return uuid.uuid4().hex
