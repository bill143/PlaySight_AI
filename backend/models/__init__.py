"""SQLAlchemy models package. Import order matters for relationship resolution."""

from __future__ import annotations

from backend.models.artifact import Artifact
from backend.models.base import Base
from backend.models.club import Club, Team
from backend.models.event import MatchEvent
from backend.models.match import Match, ProcessingJob, Video
from backend.models.player import Player, PlayerIdentity, PlayerTrack
from backend.models.publishing import PublishRecord
from backend.models.user import User

__all__ = [
    "Base",
    "Club",
    "Team",
    "User",
    "Match",
    "Video",
    "ProcessingJob",
    "Player",
    "PlayerTrack",
    "PlayerIdentity",
    "MatchEvent",
    "Artifact",
    "PublishRecord",
]
