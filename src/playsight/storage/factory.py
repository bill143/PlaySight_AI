"""Storage backend factory."""

from __future__ import annotations

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import ValidationFailed
from playsight.storage.base import ObjectStorage
from playsight.storage.local import LocalStorage
from playsight.storage.s3 import S3Storage


def get_storage(settings: Settings | None = None) -> ObjectStorage:
    """Return the configured object storage backend.

    Args:
        settings: Optional explicit settings; defaults to the cached
            process-wide settings.

    Raises:
        ValidationFailed: For an unknown ``storage.backend`` value.
    """
    settings = settings or get_settings()
    backend = settings.storage.backend.lower()
    if backend == "local":
        return LocalStorage(settings.storage.local_root)
    if backend == "s3":
        storage = S3Storage(settings)
        storage.ensure_bucket()
        return storage
    raise ValidationFailed(f"Unknown storage backend: {settings.storage.backend!r}")
