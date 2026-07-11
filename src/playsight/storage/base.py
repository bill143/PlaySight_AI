"""Object storage abstraction (local filesystem / S3 / MinIO)."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class ObjectStorage(Protocol):
    """Protocol implemented by every storage backend.

    Keys are POSIX-style relative paths, e.g. ``matches/<match_id>/<filename>``.
    """

    def put_file(self, local_path: str | Path, key: str) -> str:
        """Upload a local file under ``key``; returns the key."""
        ...

    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> str:
        """Store raw bytes under ``key`` (with optional content type); returns the key."""
        ...

    def open_stream(self, key: str) -> BinaryIO:
        """Open a binary read stream for ``key`` (caller must close it)."""
        ...

    def download_to(self, key: str, local_path: str | Path) -> Path:
        """Download ``key`` to a local path (parent dirs created); returns the path."""
        ...

    def exists(self, key: str) -> bool:
        """Return whether an object exists under ``key``."""
        ...

    def url_for(self, key: str) -> str | None:
        """Return a fetchable URL for ``key`` if the backend supports it, else None."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object under ``key`` (no-op when it does not exist)."""
        ...
