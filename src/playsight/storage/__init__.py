"""Object storage abstraction: local filesystem, S3, and MinIO backends."""

from playsight.storage.base import ObjectStorage
from playsight.storage.factory import get_storage
from playsight.storage.local import LocalStorage
from playsight.storage.s3 import S3Storage

__all__ = ["LocalStorage", "ObjectStorage", "S3Storage", "get_storage"]
