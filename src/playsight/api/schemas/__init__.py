"""Pydantic v2 request/response models for the REST API (CONTRACTS.md section 12).

All read models set ``model_config = ConfigDict(from_attributes=True)`` so they
validate straight from ORM rows. Fields whose ORM column carries a ``_json``
suffix use ``validation_alias`` so the API exposes the clean name (e.g.
``result`` instead of ``result_json``).
"""

from playsight.api.schemas.artifacts import ArtifactRead
from playsight.api.schemas.auth import (
    ClubRead,
    LoginRequest,
    RefreshRequest,
    RegisterClubRequest,
    RegisterClubResponse,
    TokenResponse,
    UserRead,
)
from playsight.api.schemas.jobs import JobCreatedResponse, JobRead
from playsight.api.schemas.matches import (
    HighlightsRequest,
    MatchCreate,
    MatchEventRead,
    MatchRead,
    PlayerIdentityRead,
    PlayerStatsRead,
    VideoAssetRead,
    VideoSourceRequest,
)
from playsight.api.schemas.players import PlayerCreate, PlayerRead
from playsight.api.schemas.publish import PublishAccepted, PublishRequest, UploadRecordRead
from playsight.api.schemas.teams import TeamCreate, TeamRead

__all__ = [
    "ArtifactRead",
    "ClubRead",
    "HighlightsRequest",
    "JobCreatedResponse",
    "JobRead",
    "LoginRequest",
    "MatchCreate",
    "MatchEventRead",
    "MatchRead",
    "PlayerCreate",
    "PlayerIdentityRead",
    "PlayerRead",
    "PlayerStatsRead",
    "PublishAccepted",
    "PublishRequest",
    "RefreshRequest",
    "RegisterClubRequest",
    "RegisterClubResponse",
    "TeamCreate",
    "TeamRead",
    "TokenResponse",
    "UploadRecordRead",
    "UserRead",
    "VideoAssetRead",
    "VideoSourceRequest",
]
