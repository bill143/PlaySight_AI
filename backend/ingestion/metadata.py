"""Match metadata parsing and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MatchMetadata:
    """Normalized metadata describing a match, used throughout the pipeline."""

    title: str = ""
    sport: str = "football"
    home_team: str = ""
    away_team: str = ""
    match_date: str = ""
    club_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sport": self.sport,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "match_date": self.match_date,
            "club_id": self.club_id,
            "extra": self.extra,
        }


def parse_metadata(raw: str | bytes | dict[str, Any]) -> MatchMetadata:
    """Parse metadata supplied as a JSON string/bytes or already-decoded dict."""
    if isinstance(raw, (str, bytes)):
        data = json.loads(raw)
    else:
        data = dict(raw)

    known_fields = {"title", "sport", "home_team", "away_team", "match_date", "club_id"}
    extra = {k: v for k, v in data.items() if k not in known_fields}

    return MatchMetadata(
        title=data.get("title", ""),
        sport=data.get("sport", "football"),
        home_team=data.get("home_team", ""),
        away_team=data.get("away_team", ""),
        match_date=data.get("match_date", ""),
        club_id=data.get("club_id"),
        extra=extra,
    )


def load_metadata_file(path: str | Path) -> MatchMetadata:
    """Load and parse a metadata JSON file from disk."""
    return parse_metadata(Path(path).read_text(encoding="utf-8"))
