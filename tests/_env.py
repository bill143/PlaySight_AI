"""Test environment bootstrap.

This module MUST be imported before any ``playsight`` module so that the
process-wide cached settings (``playsight.config.settings.get_settings``) pick
up the test configuration:

- ``env=test`` (eager in-process jobs, bootstrap open only for the first club)
- a session-scoped tmp SQLite database file
- local object storage rooted in a tmp directory
- an empty redis URL (health checks skip redis; dispatch is eager)
- no YAML config layer (``PLAYSIGHT_CONFIG`` points at a missing file)

``tests/conftest.py`` imports this module at the top of its third-party import
block, i.e. before the ``playsight`` first-party imports run.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

#: Session-scoped root for every test-generated file (removed at exit).
TEST_ROOT = Path(tempfile.mkdtemp(prefix="playsight_tests_")).resolve()

#: Local object-storage root (``settings.storage.local_root``).
STORAGE_ROOT = TEST_ROOT / "storage"

#: Working directory the test session chdirs into (holds ``outputs/`` etc.).
WORK_DIR = TEST_ROOT / "workdir"

#: Cache directory for session-scoped media fixtures (synthetic video).
MEDIA_DIR = TEST_ROOT / "media"

#: SQLite database file backing the session-scoped engine.
DB_PATH = TEST_ROOT / "playsight_test.db"

for _directory in (STORAGE_ROOT, WORK_DIR, MEDIA_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

os.environ["PLAYSIGHT_ENV"] = "test"
os.environ["PLAYSIGHT_EAGER_JOBS"] = "1"
os.environ["PLAYSIGHT_DATABASE_URL"] = "sqlite:///" + DB_PATH.as_posix()
os.environ["PLAYSIGHT_REDIS_URL"] = ""
os.environ["PLAYSIGHT_STORAGE__BACKEND"] = "local"
os.environ["PLAYSIGHT_STORAGE__LOCAL_ROOT"] = str(STORAGE_ROOT)
os.environ["PLAYSIGHT_CONFIG"] = str(TEST_ROOT / "missing-config.yaml")


def _cleanup() -> None:
    """Best-effort removal of the tmp test root at interpreter exit."""
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


atexit.register(_cleanup)
