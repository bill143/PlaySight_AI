"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger

log = get_logger(__name__)


class LocalStorage:
    """Object storage rooted at a local directory (``settings.storage.local_root``)."""

    def __init__(self, root: str | Path) -> None:
        """Create the backend, ensuring the root directory exists."""
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        """Map a storage key to a filesystem path, rejecting traversal outside root."""
        candidate = (self.root / key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValidationFailed(f"Invalid storage key: {key!r}")
        return candidate

    def put_file(self, local_path: str | Path, key: str) -> str:
        """Copy a local file into storage under ``key``; returns the key."""
        src = Path(local_path)
        if not src.is_file():
            raise NotFoundError(f"Local file not found: {src}")
        dest = self._path_for(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        log.debug("storage_put_file", key=key, size=dest.stat().st_size)
        return key

    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> str:
        """Write raw bytes under ``key`` (content_type ignored locally); returns the key."""
        dest = self._path_for(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        log.debug("storage_put_bytes", key=key, size=len(data), content_type=content_type)
        return key

    def open_stream(self, key: str) -> BinaryIO:
        """Open a binary read stream for ``key`` (caller must close it)."""
        path = self._path_for(key)
        if not path.is_file():
            raise NotFoundError(f"Storage key not found: {key}")
        return path.open("rb")

    def download_to(self, key: str, local_path: str | Path) -> Path:
        """Copy the object under ``key`` to ``local_path``; returns the path."""
        src = self._path_for(key)
        if not src.is_file():
            raise NotFoundError(f"Storage key not found: {key}")
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return dest

    def exists(self, key: str) -> bool:
        """Return whether a file exists under ``key``."""
        return self._path_for(key).is_file()

    def url_for(self, key: str) -> str | None:
        """Local backend exposes no URLs; always returns None."""
        return None

    def delete(self, key: str) -> None:
        """Delete the file under ``key`` if present (no-op otherwise)."""
        path = self._path_for(key)
        if path.is_file():
            path.unlink()
            log.debug("storage_delete", key=key)
