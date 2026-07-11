"""Competition adapter protocol and registry.

Per CONTRACTS.md section 18, every adapter MUST declare ``rate_limit_per_minute``
and ``attribution``; the registry rejects adapters that omit either. Official /
licensed APIs are the preferred sources; scraping is out of scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from playsight.core.errors import ValidationFailed


@dataclass(frozen=True)
class FixtureRecord:
    """A fixture as returned by a competition adapter (transport shape)."""

    external_ref: str
    home_team: str
    away_team: str
    kickoff_at: datetime | None = None
    venue: str | None = None
    status: str = "scheduled"
    home_score: int | None = None
    away_score: int | None = None
    competition_name: str | None = None


@dataclass(frozen=True)
class StandingRecord:
    """A league-table row as returned by a competition adapter."""

    team_name: str
    position: int
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    competition_name: str | None = None
    season: str | None = None


@runtime_checkable
class CompetitionAdapter(Protocol):
    """Protocol every competition source adapter must satisfy.

    Attributes:
        key: Unique registry key (matches ``CompetitionSource.adapter_key``).
        rate_limit_per_minute: REQUIRED maximum upstream request rate; sync
            orchestration throttles against it (CONTRACTS.md section 18).
        attribution: REQUIRED human-readable source attribution, surfaced on
            every synced record and in the UI.
    """

    key: str
    rate_limit_per_minute: int
    attribution: str

    def fetch_fixtures(self, config: Mapping[str, Any]) -> list[FixtureRecord]:
        """Fetch fixtures for the given source configuration."""
        ...

    def fetch_standings(self, config: Mapping[str, Any]) -> list[StandingRecord]:
        """Fetch standings for the given source configuration."""
        ...


_REGISTRY: dict[str, CompetitionAdapter] = {}


def register_adapter(adapter: CompetitionAdapter) -> CompetitionAdapter:
    """Register an adapter instance under its ``key`` and return it.

    Raises:
        ValueError: If ``key``, ``rate_limit_per_minute`` or ``attribution`` is
            missing/empty (both metadata fields are contractually required), or
            the key is already taken by a different adapter instance.
    """
    for attr in ("key", "rate_limit_per_minute", "attribution"):
        if not getattr(adapter, attr, None):
            raise ValueError(f"Competition adapter must define a non-empty '{attr}'.")
    existing = _REGISTRY.get(adapter.key)
    if existing is not None and existing is not adapter:
        raise ValueError(f"Competition adapter key '{adapter.key}' is already registered.")
    _REGISTRY[adapter.key] = adapter
    return adapter


def get_adapter(key: str) -> CompetitionAdapter:
    """Return the registered adapter for ``key``.

    Raises:
        ValidationFailed: If no adapter is registered under ``key``.
    """
    adapter = _REGISTRY.get(key)
    if adapter is None:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise ValidationFailed(f"Unknown competition adapter '{key}'. Registered: {known}.")
    return adapter


def available_adapters() -> dict[str, CompetitionAdapter]:
    """Return a copy of the adapter registry keyed by adapter key."""
    return dict(_REGISTRY)
