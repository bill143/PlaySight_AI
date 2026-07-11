"""Unit tests for the ingestion package."""

from __future__ import annotations

import json

import pytest

from backend.ingestion.metadata import MatchMetadata, load_metadata_file, parse_metadata
from backend.ingestion.validator import VideoValidator


class TestVideoValidator:
    def test_validate_upload_accepts_valid_mp4(self) -> None:
        validator = VideoValidator()
        result = validator.validate_upload("match.mp4", size_bytes=1024)
        assert result.is_valid
        assert result.errors == []

    def test_validate_upload_rejects_bad_extension(self) -> None:
        validator = VideoValidator()
        result = validator.validate_upload("match.txt", size_bytes=1024)
        assert not result.is_valid
        assert any("extension" in e for e in result.errors)

    def test_validate_upload_rejects_empty_file(self) -> None:
        validator = VideoValidator()
        result = validator.validate_upload("match.mp4", size_bytes=0)
        assert not result.is_valid

    def test_validate_upload_rejects_oversized_file(self) -> None:
        validator = VideoValidator(max_size_bytes=100)
        result = validator.validate_upload("match.mp4", size_bytes=200)
        assert not result.is_valid

    def test_validate_path_missing_file(self, tmp_path) -> None:
        validator = VideoValidator()
        result = validator.validate_path(tmp_path / "missing.mp4")
        assert not result.is_valid

    def test_validate_path_existing_file(self, tmp_path) -> None:
        video_file = tmp_path / "clip.mp4"
        video_file.write_bytes(b"fake-video-bytes")
        validator = VideoValidator()
        result = validator.validate_path(video_file)
        assert result.is_valid

    def test_raise_if_invalid_raises_value_error(self) -> None:
        validator = VideoValidator()
        result = validator.validate_upload("match.txt", size_bytes=10)
        with pytest.raises(ValueError):
            result.raise_if_invalid()


class TestMetadataParsing:
    def test_parse_metadata_from_dict(self) -> None:
        metadata = parse_metadata({"title": "Finals", "home_team": "A", "away_team": "B"})
        assert isinstance(metadata, MatchMetadata)
        assert metadata.title == "Finals"
        assert metadata.home_team == "A"

    def test_parse_metadata_from_json_string(self) -> None:
        raw = json.dumps({"title": "Semis", "sport": "basketball", "custom_field": 42})
        metadata = parse_metadata(raw)
        assert metadata.title == "Semis"
        assert metadata.sport == "basketball"
        assert metadata.extra == {"custom_field": 42}

    def test_load_metadata_file(self, tmp_path) -> None:
        metadata_file = tmp_path / "meta.json"
        metadata_file.write_text(json.dumps({"title": "Cup Final"}), encoding="utf-8")
        metadata = load_metadata_file(metadata_file)
        assert metadata.title == "Cup Final"

    def test_metadata_defaults(self) -> None:
        metadata = parse_metadata({})
        assert metadata.sport == "football"
        assert metadata.title == ""
