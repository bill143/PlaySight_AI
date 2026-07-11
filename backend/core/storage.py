"""S3-compatible object storage client (works with AWS S3 or MinIO)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.core.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """Thin wrapper around boto3 S3 client for uploads/downloads/presigned URLs."""

    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
            config=BotoConfig(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not already exist. Safe to call repeatedly."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError as exc:  # pragma: no cover - defensive
                logger.warning("Could not create bucket %s: %s", self.bucket, exc)

    def upload_file(self, local_path: str | Path, key: str) -> str:
        """Upload a local file to storage under `key`, return the object key."""
        self.client.upload_file(str(local_path), self.bucket, key)
        return key

    def download_file(self, key: str, local_path: str | Path) -> Path:
        """Download an object to a local path, returning that path."""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(local_path))
        return local_path

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for downloading an object."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_object(self, key: str) -> None:
        """Delete an object from storage. Ignores missing objects."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:  # pragma: no cover - defensive
            logger.warning("Could not delete object %s: %s", key, exc)

    def object_exists(self, key: str) -> bool:
        """Check whether an object exists in the bucket."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


@lru_cache
def get_storage_client() -> StorageClient:
    """Return a cached StorageClient instance."""
    return StorageClient()
