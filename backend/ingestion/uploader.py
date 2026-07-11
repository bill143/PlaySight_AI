"""Upload video files (and derived artifacts) to object storage."""

from __future__ import annotations

import uuid
from pathlib import Path

from backend.core.storage import StorageClient, get_storage_client


class VideoUploader:
    """Handles moving raw video uploads and generated artifacts into storage."""

    def __init__(self, storage_client: StorageClient | None = None) -> None:
        self.storage = storage_client or get_storage_client()

    def build_key(self, match_id: str, filename: str, prefix: str = "raw") -> str:
        """Build a namespaced storage key for a match-related file."""
        suffix = Path(filename).suffix
        unique = uuid.uuid4().hex[:8]
        return f"matches/{match_id}/{prefix}/{unique}_{Path(filename).stem}{suffix}"

    def upload_video(self, local_path: str | Path, match_id: str, original_filename: str) -> str:
        """Upload a raw video file for a match, returning its storage key."""
        key = self.build_key(match_id, original_filename, prefix="raw")
        self.storage.upload_file(local_path, key)
        return key

    def upload_artifact(self, local_path: str | Path, match_id: str, artifact_name: str) -> str:
        """Upload a generated artifact (report, highlight, export) for a match."""
        key = self.build_key(match_id, artifact_name, prefix="artifacts")
        self.storage.upload_file(local_path, key)
        return key
