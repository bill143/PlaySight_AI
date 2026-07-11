"""Local object-storage backend tests (put/get/stream/exists/url/delete)."""

from __future__ import annotations

from pathlib import Path

import pytest

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.storage import LocalStorage, ObjectStorage, get_storage


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "store")


class TestLocalStorage:
    def test_put_bytes_and_open_stream(self, storage: LocalStorage) -> None:
        key = storage.put_bytes(b"hello world", "matches/m1/summary.json")
        assert key == "matches/m1/summary.json"
        with storage.open_stream(key) as stream:
            assert stream.read() == b"hello world"

    def test_put_file_and_download_to(self, storage: LocalStorage, tmp_path: Path) -> None:
        source = tmp_path / "source.bin"
        source.write_bytes(b"\x00\x01\x02payload")
        key = storage.put_file(source, "matches/m1/source.bin")
        target = tmp_path / "nested" / "downloaded.bin"
        result = storage.download_to(key, target)
        assert result == target
        assert target.read_bytes() == b"\x00\x01\x02payload"

    def test_exists(self, storage: LocalStorage) -> None:
        assert storage.exists("matches/m1/x.txt") is False
        storage.put_bytes(b"x", "matches/m1/x.txt")
        assert storage.exists("matches/m1/x.txt") is True

    def test_url_for_returns_none(self, storage: LocalStorage) -> None:
        storage.put_bytes(b"x", "k")
        assert storage.url_for("k") is None

    def test_delete_and_delete_missing_is_noop(self, storage: LocalStorage) -> None:
        storage.put_bytes(b"x", "gone.txt")
        storage.delete("gone.txt")
        assert storage.exists("gone.txt") is False
        storage.delete("never-existed.txt")  # must not raise

    def test_open_stream_missing_key_raises(self, storage: LocalStorage) -> None:
        with pytest.raises(NotFoundError):
            storage.open_stream("missing/key.bin")

    def test_download_missing_key_raises(self, storage: LocalStorage, tmp_path: Path) -> None:
        with pytest.raises(NotFoundError):
            storage.download_to("missing/key.bin", tmp_path / "out.bin")

    def test_put_file_missing_source_raises(self, storage: LocalStorage, tmp_path: Path) -> None:
        with pytest.raises(NotFoundError):
            storage.put_file(tmp_path / "does-not-exist.bin", "k")

    def test_path_traversal_rejected(self, storage: LocalStorage) -> None:
        with pytest.raises(ValidationFailed):
            storage.put_bytes(b"evil", "../outside.txt")

    def test_overwrite_replaces_content(self, storage: LocalStorage) -> None:
        storage.put_bytes(b"one", "k.txt")
        storage.put_bytes(b"two", "k.txt")
        with storage.open_stream("k.txt") as stream:
            assert stream.read() == b"two"


class TestStorageFactory:
    def test_get_storage_returns_local_backend(self) -> None:
        backend = get_storage()
        assert isinstance(backend, LocalStorage)
        assert isinstance(backend, ObjectStorage)

    def test_factory_uses_configured_root(self) -> None:
        backend = get_storage()
        assert isinstance(backend, LocalStorage)
        backend.put_bytes(b"factory", "factory-check.txt")
        assert (backend.root / "factory-check.txt").read_bytes() == b"factory"
