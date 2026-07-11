"""S3-compatible storage backend (AWS S3 or MinIO via endpoint override)."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, BinaryIO, cast

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from playsight.config.settings import Settings
from playsight.core.errors import ExternalServiceError, NotFoundError
from playsight.core.logging import get_logger

log = get_logger(__name__)

_PRESIGNED_URL_TTL_S = 3600


class S3Storage:
    """Object storage backed by S3/MinIO (``settings.storage.backend == "s3"``)."""

    def __init__(self, settings: Settings) -> None:
        """Create the backend from settings (endpoint override enables MinIO)."""
        cfg = settings.storage
        self.bucket = cfg.s3_bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint or None,
            aws_access_key_id=cfg.s3_access_key,
            aws_secret_access_key=cfg.s3_secret_key,
            region_name=cfg.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """Create the configured bucket when it does not exist yet."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status not in (301, 403, 404):
                raise ExternalServiceError(f"S3 head_bucket failed: {exc}") from exc
        try:
            self._client.create_bucket(Bucket=self.bucket)
            log.info("storage_bucket_created", bucket=self.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise ExternalServiceError(f"S3 create_bucket failed: {exc}") from exc

    @staticmethod
    def _guess_content_type(name: str) -> str:
        return mimetypes.guess_type(name)[0] or "application/octet-stream"

    def put_file(self, local_path: str | Path, key: str) -> str:
        """Upload a local file under ``key``; returns the key."""
        src = Path(local_path)
        if not src.is_file():
            raise NotFoundError(f"Local file not found: {src}")
        try:
            self._client.upload_file(
                str(src),
                self.bucket,
                key,
                ExtraArgs={"ContentType": self._guess_content_type(src.name)},
            )
        except ClientError as exc:
            raise ExternalServiceError(f"S3 upload failed for {key}: {exc}") from exc
        log.debug("storage_put_file", key=key, bucket=self.bucket)
        return key

    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> str:
        """Store raw bytes under ``key``; returns the key."""
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type or self._guess_content_type(key),
            )
        except ClientError as exc:
            raise ExternalServiceError(f"S3 put_object failed for {key}: {exc}") from exc
        log.debug("storage_put_bytes", key=key, size=len(data))
        return key

    def open_stream(self, key: str) -> BinaryIO:
        """Return a binary read stream (botocore StreamingBody) for ``key``."""
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise NotFoundError(f"Storage key not found: {key}") from exc
            raise ExternalServiceError(f"S3 get_object failed for {key}: {exc}") from exc
        return cast(BinaryIO, obj["Body"])

    def download_to(self, key: str, local_path: str | Path) -> Path:
        """Download ``key`` to ``local_path``; returns the path."""
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self.bucket, key, str(dest))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise NotFoundError(f"Storage key not found: {key}") from exc
            raise ExternalServiceError(f"S3 download failed for {key}: {exc}") from exc
        return dest

    def exists(self, key: str) -> bool:
        """Return whether an object exists under ``key``."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise ExternalServiceError(f"S3 head_object failed for {key}: {exc}") from exc

    def url_for(self, key: str) -> str | None:
        """Return a presigned GET URL for ``key`` (1 hour TTL)."""
        try:
            return cast(
                str,
                self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=_PRESIGNED_URL_TTL_S,
                ),
            )
        except ClientError as exc:
            raise ExternalServiceError(f"S3 presign failed for {key}: {exc}") from exc

    def delete(self, key: str) -> None:
        """Delete the object under ``key`` (S3 delete is idempotent)."""
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise ExternalServiceError(f"S3 delete failed for {key}: {exc}") from exc
        log.debug("storage_delete", key=key)
