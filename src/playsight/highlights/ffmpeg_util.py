"""Shared ffmpeg helpers for highlight building and media export.

Resolution order for the ffmpeg executable (CONTRACTS.md section 2: prefer
system ffmpeg, fall back to the static binary shipped with ``imageio-ffmpeg``):

1. ``ffmpeg`` found on the system ``PATH``.
2. ``imageio_ffmpeg.get_ffmpeg_exe()``.

All ffmpeg invocations in the codebase go through :func:`run_ffmpeg`, which
captures stderr and converts non-zero exits into ``ExternalServiceError`` with
a readable stderr tail.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from playsight.core.errors import ExternalServiceError
from playsight.core.logging import get_logger

#: Maximum number of stderr characters included in error messages/logs.
_STDERR_TAIL_CHARS = 2000


def resolve_ffmpeg() -> str | None:
    """Return the path to an ffmpeg executable, or ``None`` when unavailable.

    Prefers a system ``ffmpeg`` on ``PATH``; falls back to the static binary
    provided by the ``imageio-ffmpeg`` package.
    """
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None


def ffmpeg_available() -> bool:
    """Return ``True`` when an ffmpeg executable can be resolved."""
    return resolve_ffmpeg() is not None


def run_ffmpeg(
    args: Sequence[str | Path],
    log: Any = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg with ``args`` appended to a safe base invocation.

    The base invocation is ``ffmpeg -hide_banner -nostdin -y`` so callers only
    supply input/output/filter arguments. stdout and stderr are captured.

    Args:
        args: ffmpeg arguments (everything after the executable name).
        log: A structlog logger; a module logger is used when ``None``.
        check: When ``True`` (default), raise ``ExternalServiceError`` on a
            non-zero exit code, including a tail of stderr in the message.

    Returns:
        The completed process (with ``stdout``/``stderr`` as text).

    Raises:
        ExternalServiceError: If no ffmpeg executable can be resolved
            (code ``ffmpeg_not_found``), if the process cannot be spawned
            (code ``ffmpeg_exec_failed``), or — when ``check`` is set — if
            ffmpeg exits non-zero (code ``ffmpeg_failed``).
    """
    logger = log if log is not None else get_logger(__name__)
    exe = resolve_ffmpeg()
    if exe is None:
        raise ExternalServiceError(
            "ffmpeg executable not found: install ffmpeg on PATH or the imageio-ffmpeg package",
            code="ffmpeg_not_found",
        )
    cmd = [exe, "-hide_banner", "-nostdin", "-y", *[str(a) for a in args]]
    logger.debug("ffmpeg_run", ffmpeg_args=cmd[1:])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ExternalServiceError(
            f"failed to execute ffmpeg at {exe}: {exc}", code="ffmpeg_exec_failed"
        ) from exc
    if check and proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-_STDERR_TAIL_CHARS:]
        logger.error(
            "ffmpeg_failed",
            returncode=proc.returncode,
            ffmpeg_args=cmd[1:],
            stderr_tail=stderr_tail,
        )
        raise ExternalServiceError(
            f"ffmpeg exited with code {proc.returncode}: {stderr_tail or 'no stderr output'}",
            code="ffmpeg_failed",
        )
    return proc
