"""Match summary JSON assembly (exact CONTRACTS.md section 9 shape)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from playsight.core.types import EventSpan, EventType, IdentityResult, PlayerStatsRow, VideoInfo
from playsight.reporting._util import event_type_value

__all__ = ["DEFAULT_ENGINE", "DEFAULT_LIMITATIONS", "build_match_summary"]

#: Engine metadata defaults -- honest about stub fallbacks (CONTRACTS.md section 2).
DEFAULT_ENGINE: dict[str, str] = {"detector": "stub", "tracker": "simple", "ocr": "stub"}

#: Standard limitations statements (CONTRACTS.md sections 8 and 18).
DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "Events are rule-based heuristic proxies computed from bounding-box tracks; "
    "they are confidence-scored estimates, not ground truth.",
    "Player identity is estimated from jersey OCR and appearance embeddings "
    "(confidence-scored); no biometric face recognition is used.",
    "Distance covered is a pixel-displacement proxy scaled by a nominal pitch "
    "calibration, not a calibrated measurement.",
    "Team assignment for turnovers uses spatial clustering of track positions "
    "and can be wrong for interleaved formations.",
)


def build_match_summary(
    match_id: str,
    video_info: VideoInfo,
    identities: Sequence[IdentityResult],
    events: Sequence[EventSpan],
    stats: Sequence[PlayerStatsRow],
    *,
    teams: Mapping[str, str] | None = None,
    engine: Mapping[str, str] | None = None,
    limitations: Sequence[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Assemble the ``match_summary.json`` payload (CONTRACTS.md section 9).

    Args:
        match_id: the ``matches.id`` this summary belongs to.
        video_info: probed video metadata (duration and fps are reported).
        identities: estimated identities; ``method != "unresolved"`` counts as
            identified.
        events: rule-based match events.
        stats: per-track stats rows (drive the ``players`` list).
        teams: optional ``{"home": ..., "away": ...}`` display names.
        engine: optional actual engine info, e.g. ``{"detector": "yolo",
            "tracker": "bytetrack", "ocr": "easyocr"}``; defaults to the honest
            stub values in :data:`DEFAULT_ENGINE`.
        limitations: optional replacement for :data:`DEFAULT_LIMITATIONS`.
        generated_at: timestamp override (tests); defaults to now (UTC).

    Returns:
        A JSON-serializable dict in the exact contracted shape. Unresolved
        players use the ``track_<track_id>`` id convention from section 9.
    """
    when = generated_at or datetime.now(UTC)
    events_by_type = {member.value: 0 for member in EventType}
    for event in events:
        key = event_type_value(event.event_type)
        events_by_type[key] = events_by_type.get(key, 0) + 1

    track_ids = {int(s.track_id) for s in stats} | {int(i.track_id) for i in identities}
    identified = sum(1 for identity in identities if identity.method != "unresolved")

    players = [
        {
            "player_id": row.player_id or f"track_{row.track_id}",
            "track_id": int(row.track_id),
            "jersey_number": row.jersey_number,
            "minutes_tracked": round(float(row.minutes_tracked), 2),
            "touches": int(row.touches),
            "confidence": round(float(row.avg_confidence), 3),
        }
        for row in sorted(stats, key=lambda s: (-s.minutes_tracked, s.track_id))
    ]

    engine_info = dict(DEFAULT_ENGINE)
    if engine:
        engine_info.update({str(key): str(value) for key, value in engine.items()})
    team_names = {
        "home": str(teams.get("home", "Home")) if teams else "Home",
        "away": str(teams.get("away", "Away")) if teams else "Away",
    }

    return {
        "match_id": match_id,
        "generated_at": when.isoformat(),
        "video": {
            "duration_s": round(float(video_info.duration_s), 3),
            "fps": round(float(video_info.fps), 3),
        },
        "teams": team_names,
        "counts": {"tracks": len(track_ids), "identified": identified, "events": len(events)},
        "events_by_type": events_by_type,
        "players": players,
        "engine": engine_info,
        "limitations": list(limitations) if limitations is not None else list(DEFAULT_LIMITATIONS),
    }
