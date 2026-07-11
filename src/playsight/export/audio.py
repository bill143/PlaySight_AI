"""Audio match summary export (CONTRACTS.md section 7).

Composes a natural-language narration script from the ``match_summary`` dict
(section 9 shape) and synthesizes it to MP3 through a chain of fallbacks:

1. ``gTTS`` — best quality, requires network.
2. ``pyttsx3`` — offline OS voices; wav output converted to MP3 via ffmpeg.
3. Deterministic tone-sequence MP3 rendered with ffmpeg's ``sine`` filter.
4. A minimal silent MP3 written from canonical frame bytes (absolute last
   resort so the artifact always exists).

The plain-text transcript is always written next to the MP3 as
``<out_path>.txt``. Missing TTS engines never raise; the engine actually used
is logged and recorded in the metadata dict.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from playsight.core.logging import get_logger
from playsight.highlights.ffmpeg_util import ffmpeg_available, run_ffmpeg

#: Spoken singular/plural phrases for the event taxonomy (CONTRACTS.md section 8).
_EVENT_PHRASES: dict[str, tuple[str, str]] = {
    "touch": ("touch", "touches"),
    "pass": ("pass", "passes"),
    "tackle": ("tackle", "tackles"),
    "shot_attempt": ("shot attempt", "shot attempts"),
    "turnover": ("turnover", "turnovers"),
    "scoring_event": ("scoring event", "scoring events"),
}

#: Deterministic chime (frequency Hz, duration s) for the tone-sequence fallback.
_TONE_SEQUENCE: tuple[tuple[float, float], ...] = (
    (523.25, 0.3),
    (659.25, 0.3),
    (783.99, 0.3),
    (1046.5, 0.45),
)

#: One silent MPEG-1 Layer III frame (44.1 kHz, 128 kbps, joint stereo, 417 bytes).
_SILENT_MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413

#: Samples per MPEG-1 Layer III frame (used to size the silent fallback).
_SAMPLES_PER_FRAME = 1152


def build_narration(summary: dict) -> str:
    """Compose a natural-language narration script from a match summary dict.

    Tolerates missing keys in ``summary`` (CONTRACTS.md section 9 shape) and
    always ends with an honesty disclaimer about heuristic statistics.

    Args:
        summary: The ``match_summary.json`` dict.

    Returns:
        A speakable, single-paragraph narration script.
    """
    teams = summary.get("teams") or {}
    home = str(teams.get("home") or "the home team")
    away = str(teams.get("away") or "the away team")
    video = summary.get("video") or {}
    counts = summary.get("counts") or {}
    events_by_type = summary.get("events_by_type") or {}
    players = summary.get("players") or []

    sentences = ["Welcome to your PlaySight match summary.", f"{home} versus {away}."]

    duration_s = float(video.get("duration_s") or 0.0)
    if duration_s > 0:
        sentences.append(f"The analyzed footage runs {_speak_duration(duration_s)}.")

    tracks = int(counts.get("tracks") or 0)
    identified = int(counts.get("identified") or 0)
    n_events = int(counts.get("events") or 0)
    sentences.append(
        f"The vision system followed {tracks} player track{'s' if tracks != 1 else ''}, "
        f"resolved {identified} identit{'ies' if identified != 1 else 'y'}, "
        f"and flagged {n_events} notable moment{'s' if n_events != 1 else ''}."
    )

    breakdown = [
        _event_phrase(event_type, int(count or 0))
        for event_type, count in events_by_type.items()
        if int(count or 0) > 0
    ]
    if breakdown:
        sentences.append(f"Event breakdown: {_join_clauses(breakdown)}.")

    top_players = sorted(
        (p for p in players if isinstance(p, dict) and int(p.get("touches") or 0) > 0),
        key=lambda p: int(p.get("touches") or 0),
        reverse=True,
    )[:3]
    for player in top_players:
        jersey = player.get("jersey_number")
        who = f"Number {jersey}" if jersey is not None else f"Track {player.get('track_id')}"
        touches = int(player.get("touches") or 0)
        minutes = float(player.get("minutes_tracked") or 0.0)
        sentences.append(
            f"{who} recorded {touches} touch{'es' if touches != 1 else ''} "
            f"across {_speak_duration(minutes * 60.0)} tracked."
        )

    sentences.append(
        "All figures are automated estimates produced by video tracking heuristics "
        "and are not official match statistics."
    )
    return " ".join(sentences)


def render_audio_summary(summary: dict, out_path: str | Path) -> Path:
    """Render the audio match summary MP3 and transcript; return the MP3 path.

    Contract wrapper (CONTRACTS.md section 7). Use
    :func:`render_audio_summary_detailed` when the caller needs to know which
    TTS engine produced the audio.

    Args:
        summary: The ``match_summary.json`` dict.
        out_path: Destination MP3 path (``match_summary_audio.mp3``,
            section 9); the transcript is written to ``<out_path>.txt``.

    Returns:
        The path to the written MP3 (== ``out_path``).
    """
    meta = render_audio_summary_detailed(summary, out_path)
    return Path(meta["path"])


def render_audio_summary_detailed(summary: dict, out_path: str | Path) -> dict[str, Any]:
    """Render the audio match summary and return metadata about how it was made.

    Never raises on missing TTS engines: the fallback chain is
    gTTS -> pyttsx3 -> ffmpeg tone sequence -> embedded silent MP3 frames,
    and the transcript ``<out_path>.txt`` is always written first.

    Args:
        summary: The ``match_summary.json`` dict.
        out_path: Destination MP3 path.

    Returns:
        Metadata dict: ``{"path", "transcript_path", "engine", "characters"}``
        where ``engine`` is ``"gtts" | "pyttsx3" | "tone" | "silence"``.
    """
    log = get_logger(__name__)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    text = build_narration(summary)
    transcript_path = Path(str(out) + ".txt")
    transcript_path.write_text(text, encoding="utf-8")

    if _try_gtts(text, out, log):
        engine = "gtts"
    elif _try_pyttsx3(text, out, log):
        engine = "pyttsx3"
    elif _try_tone_sequence(out, log):
        engine = "tone"
    else:
        _write_silent_mp3(out)
        engine = "silence"

    log.info(
        "audio_summary_rendered",
        engine=engine,
        path=str(out),
        transcript_path=str(transcript_path),
        characters=len(text),
    )
    return {
        "path": str(out),
        "transcript_path": str(transcript_path),
        "engine": engine,
        "characters": len(text),
    }


def _speak_duration(seconds: float) -> str:
    """Render a duration in speakable form, e.g. ``"12 minutes and 30 seconds"``."""
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    minute_part = f"{minutes} minute{'s' if minutes != 1 else ''}"
    second_part = f"{secs} second{'s' if secs != 1 else ''}"
    if minutes and secs:
        return f"{minute_part} and {second_part}"
    if minutes:
        return minute_part
    return second_part


def _event_phrase(event_type: str, count: int) -> str:
    """Render an event count in speakable form, e.g. ``"3 shot attempts"``."""
    spoken = event_type.replace("_", " ")
    singular, plural = _EVENT_PHRASES.get(event_type, (spoken, spoken + "s"))
    return f"{count} {singular if count == 1 else plural}"


def _join_clauses(parts: list[str]) -> str:
    """Join clauses with commas and a final ``and`` (Oxford comma style)."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _try_gtts(text: str, out: Path, log: Any) -> bool:
    """Attempt gTTS synthesis (network); return True on success."""
    try:
        from gtts import gTTS  # optional at runtime; needs network

        gTTS(text=text, lang="en").save(str(out))
    except Exception as exc:
        log.warning("tts_gtts_unavailable", error=str(exc))
        out.unlink(missing_ok=True)
        return False
    if out.is_file() and out.stat().st_size > 0:
        return True
    out.unlink(missing_ok=True)
    return False


def _try_pyttsx3(text: str, out: Path, log: Any) -> bool:
    """Attempt offline pyttsx3 synthesis (wav -> MP3 via ffmpeg); return True on success."""
    if not ffmpeg_available():
        log.warning("tts_pyttsx3_skipped", detail="ffmpeg required to convert wav output to mp3")
        return False
    try:
        import pyttsx3  # optional dependency, not in core install
    except Exception as exc:
        log.warning("tts_pyttsx3_unavailable", error=str(exc))
        return False
    with tempfile.TemporaryDirectory(prefix="playsight_tts_") as tmp:
        wav_path = Path(tmp) / "narration.wav"
        try:
            engine = pyttsx3.init()
            engine.save_to_file(text, str(wav_path))
            engine.runAndWait()
        except Exception as exc:
            log.warning("tts_pyttsx3_failed", error=str(exc))
            return False
        if not wav_path.is_file() or wav_path.stat().st_size == 0:
            log.warning("tts_pyttsx3_failed", detail="engine produced no wav output")
            return False
        try:
            run_ffmpeg(
                ["-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "4", str(out)],
                log,
            )
        except Exception as exc:
            log.warning("tts_pyttsx3_mp3_convert_failed", error=str(exc))
            out.unlink(missing_ok=True)
            return False
    return out.is_file() and out.stat().st_size > 0


def _try_tone_sequence(out: Path, log: Any) -> bool:
    """Render the deterministic tone-sequence MP3 via ffmpeg; return True on success."""
    if not ffmpeg_available():
        log.warning("tts_tone_skipped", detail="ffmpeg unavailable")
        return False
    args: list[str] = []
    for frequency, duration in _TONE_SEQUENCE:
        args += ["-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={duration}"]
    inputs = "".join(f"[{i}:a]" for i in range(len(_TONE_SEQUENCE)))
    args += [
        "-filter_complex",
        f"{inputs}concat=n={len(_TONE_SEQUENCE)}:v=0:a=1[out]",
        "-map",
        "[out]",
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "4",
        str(out),
    ]
    try:
        run_ffmpeg(args, log)
    except Exception as exc:
        log.warning("tts_tone_failed", error=str(exc))
        out.unlink(missing_ok=True)
        return False
    return out.is_file() and out.stat().st_size > 0


def _write_silent_mp3(out: Path, seconds: float = 1.0) -> None:
    """Write a minimal valid silent MP3 from canonical frame bytes (last resort)."""
    frame_count = max(1, int(seconds * 44100 / _SAMPLES_PER_FRAME))
    out.write_bytes(_SILENT_MP3_FRAME * frame_count)
