"""Video file validation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GiB


@dataclass
class ValidationResult:
    """Outcome of validating a candidate video file."""

    is_valid: bool
    errors: list[str]

    def raise_if_invalid(self) -> None:
        """Raise ValueError with combined errors if validation failed."""
        if not self.is_valid:
            raise ValueError("; ".join(self.errors))


class VideoValidator:
    """Validates uploaded video files before they enter the processing pipeline."""

    def __init__(self, allowed_extensions: set[str] | None = None, max_size_bytes: int = MAX_FILE_SIZE_BYTES) -> None:
        self.allowed_extensions = allowed_extensions or ALLOWED_EXTENSIONS
        self.max_size_bytes = max_size_bytes

    def validate_path(self, path: str | Path) -> ValidationResult:
        """Validate a video file already present on disk."""
        errors: list[str] = []
        file_path = Path(path)

        if not file_path.exists():
            errors.append(f"File does not exist: {file_path}")
            return ValidationResult(is_valid=False, errors=errors)

        if file_path.suffix.lower() not in self.allowed_extensions:
            errors.append(
                f"Unsupported extension '{file_path.suffix}'. Allowed: {sorted(self.allowed_extensions)}"
            )

        size = file_path.stat().st_size
        if size == 0:
            errors.append("File is empty")
        elif size > self.max_size_bytes:
            errors.append(f"File exceeds maximum size of {self.max_size_bytes} bytes (got {size})")

        return ValidationResult(is_valid=not errors, errors=errors)

    def validate_upload(self, filename: str, size_bytes: int) -> ValidationResult:
        """Validate an in-flight upload before it is written to disk/storage."""
        errors: list[str] = []
        suffix = Path(filename).suffix.lower()

        if suffix not in self.allowed_extensions:
            errors.append(f"Unsupported extension '{suffix}'. Allowed: {sorted(self.allowed_extensions)}")
        if size_bytes <= 0:
            errors.append("Upload is empty")
        elif size_bytes > self.max_size_bytes:
            errors.append(f"Upload exceeds maximum size of {self.max_size_bytes} bytes (got {size_bytes})")

        return ValidationResult(is_valid=not errors, errors=errors)
