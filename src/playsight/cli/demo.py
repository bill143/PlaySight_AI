"""Demo data generation for ``playsight seed-demo`` (CONTRACTS.md section 14).

Generates a deterministic synthetic match video (moving numbered rectangles on
a green field, ~20s at 640x360 / 15 fps) with OpenCV and seeds a demo club,
team, players, and match so the full pipeline can run with stub or real
engines.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.core.errors import ExternalServiceError
from playsight.core.logging import get_logger
from playsight.db.models import Club, Match, Player, Team

log = get_logger(__name__)

#: Default location of the generated demo video (CONTRACTS.md section 14).
DEMO_VIDEO_PATH = Path("data/demo/demo_match.mp4")

DEMO_CLUB_NAME = "Demo Club"
DEMO_CLUB_SLUG = "demo-club"
DEMO_TEAM_NAME = "Demo United"
DEMO_SPORT = "football"
DEMO_OPPONENT = "Demo Rivals"

#: (full_name, jersey_number, position) for the demo roster; the jersey
#: numbers match the numbers painted on the synthetic video rectangles.
DEMO_PLAYERS: tuple[tuple[str, int, str], ...] = (
    ("Alex Keeper", 1, "GK"),
    ("Billie Back", 2, "DF"),
    ("Casey Center", 5, "DF"),
    ("Dana Midfield", 7, "MF"),
    ("Evan Winger", 9, "FW"),
    ("Frankie Striker", 10, "FW"),
)

_FIELD_GREEN = (60, 140, 60)  # BGR
_LINE_WHITE = (235, 235, 235)
_TEAM_COLORS = ((60, 60, 200), (200, 90, 40))  # BGR: red-ish, blue-ish


def generate_demo_video(
    out_path: str | Path = DEMO_VIDEO_PATH,
    *,
    duration_s: float = 20.0,
    fps: float = 15.0,
    width: int = 640,
    height: int = 360,
    seed: int = 42,
) -> Path:
    """Generate the deterministic synthetic demo match video.

    Six numbered rectangles ("players", three per team color) move along
    seeded sinusoidal paths on a green field with a center line and circle.
    The same seed always produces the identical video.

    Args:
        out_path: Destination MP4 path (parent directories are created).
        duration_s: Video length in seconds (~20s per the contract).
        fps: Frames per second.
        width: Frame width in pixels.
        height: Frame height in pixels.
        seed: RNG seed for the motion parameters (deterministic output).

    Returns:
        The path of the written video.

    Raises:
        ExternalServiceError: The OpenCV video writer could not be opened.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    jerseys = [number for _name, number, _pos in DEMO_PLAYERS]
    box_w, box_h = 26, 52
    actors: list[dict[str, Any]] = []
    for index, jersey in enumerate(jerseys):
        actors.append(
            {
                "jersey": jersey,
                "color": _TEAM_COLORS[index % 2],
                "cx": float(rng.uniform(width * 0.15, width * 0.85)),
                "cy": float(rng.uniform(height * 0.2, height * 0.8)),
                "ax": float(rng.uniform(width * 0.08, width * 0.28)),
                "ay": float(rng.uniform(height * 0.08, height * 0.28)),
                "fx": float(rng.uniform(0.05, 0.18)),
                "fy": float(rng.uniform(0.05, 0.18)),
                "px": float(rng.uniform(0.0, 2.0 * math.pi)),
                "py": float(rng.uniform(0.0, 2.0 * math.pi)),
            }
        )

    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, fps, (width, height))
    if not writer.isOpened():
        writer.release()
        raise ExternalServiceError(
            f"OpenCV could not open a video writer at {out}", code="video_writer_failed"
        )

    total_frames = int(round(duration_s * fps))
    try:
        for frame_index in range(total_frames):
            t = frame_index / fps
            frame = _field_background(width, height)
            for actor in actors:
                x = actor["cx"] + actor["ax"] * math.sin(
                    2.0 * math.pi * actor["fx"] * t + actor["px"]
                )
                y = actor["cy"] + actor["ay"] * math.sin(
                    2.0 * math.pi * actor["fy"] * t + actor["py"]
                )
                _draw_player(frame, int(x), int(y), box_w, box_h, actor)
            writer.write(frame)
    finally:
        writer.release()

    log.info(
        "demo_video_generated",
        path=str(out),
        frames=total_frames,
        fps=fps,
        size=f"{width}x{height}",
        seed=seed,
    )
    return out


def _field_background(width: int, height: int) -> np.ndarray:
    """Return a green field frame with a center line and circle."""
    frame = np.full((height, width, 3), _FIELD_GREEN, dtype=np.uint8)
    cv2.rectangle(frame, (8, 8), (width - 9, height - 9), _LINE_WHITE, 2)
    cv2.line(frame, (width // 2, 8), (width // 2, height - 9), _LINE_WHITE, 2)
    cv2.circle(frame, (width // 2, height // 2), min(width, height) // 8, _LINE_WHITE, 2)
    return frame


def _draw_player(
    frame: np.ndarray, x: int, y: int, box_w: int, box_h: int, actor: dict[str, Any]
) -> None:
    """Draw one numbered player rectangle centered at ``(x, y)``, clamped in-frame."""
    height, width = frame.shape[:2]
    x = int(np.clip(x, box_w // 2 + 2, width - box_w // 2 - 2))
    y = int(np.clip(y, box_h // 2 + 2, height - box_h // 2 - 2))
    x1, y1 = x - box_w // 2, y - box_h // 2
    x2, y2 = x + box_w // 2, y + box_h // 2
    cv2.rectangle(frame, (x1, y1), (x2, y2), actor["color"], thickness=-1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (245, 245, 245), thickness=1)
    label = str(actor["jersey"])
    text_size, _base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    tx = x - text_size[0] // 2
    ty = y + text_size[1] // 2
    cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def seed_demo_data(db: Session) -> dict[str, Any]:
    """Create (or reuse) the demo club, team, and roster, and create a new match.

    Club/team/players are looked up by their natural keys so repeated runs do
    not duplicate them; a fresh match is created on every call.

    Args:
        db: Database session (committed by this function).

    Returns:
        ``{"club_id", "team_id", "match_id", "player_ids": {jersey: id}}``.
    """
    club = db.execute(select(Club).where(Club.slug == DEMO_CLUB_SLUG)).scalars().first()
    if club is None:
        club = Club(name=DEMO_CLUB_NAME, slug=DEMO_CLUB_SLUG)
        db.add(club)
        db.flush()

    team = (
        db.execute(select(Team).where(Team.club_id == club.id, Team.name == DEMO_TEAM_NAME))
        .scalars()
        .first()
    )
    if team is None:
        team = Team(club_id=club.id, name=DEMO_TEAM_NAME, sport=DEMO_SPORT, age_group="open")
        db.add(team)
        db.flush()

    player_ids: dict[int, str] = {}
    for full_name, jersey, position in DEMO_PLAYERS:
        player = (
            db.execute(
                select(Player).where(Player.team_id == team.id, Player.jersey_number == jersey)
            )
            .scalars()
            .first()
        )
        if player is None:
            player = Player(
                club_id=club.id,
                team_id=team.id,
                full_name=full_name,
                jersey_number=jersey,
                position=position,
            )
            db.add(player)
            db.flush()
        player_ids[jersey] = player.id

    match = Match(
        club_id=club.id,
        team_id=team.id,
        opponent=DEMO_OPPONENT,
        sport=DEMO_SPORT,
        venue="Demo Arena",
    )
    db.add(match)
    db.commit()

    log.info(
        "demo_data_seeded",
        club_id=club.id,
        team_id=team.id,
        match_id=match.id,
        players=len(player_ids),
    )
    return {
        "club_id": club.id,
        "team_id": team.id,
        "match_id": match.id,
        "player_ids": player_ids,
    }
