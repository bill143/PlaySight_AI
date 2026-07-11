"""Competition source adapters: protocol, registry, and implementations.

Importing this package registers the built-in adapters (currently ``demo``).
Third-party adapters call ``register_adapter`` themselves; ``rate_limit_per_minute``
and ``attribution`` are mandatory (CONTRACTS.md section 18).
"""

from playsight.modules.competition.adapters.base import (
    CompetitionAdapter,
    FixtureRecord,
    StandingRecord,
    available_adapters,
    get_adapter,
    register_adapter,
)
from playsight.modules.competition.adapters.demo import DemoCompetitionAdapter

__all__ = [
    "CompetitionAdapter",
    "DemoCompetitionAdapter",
    "FixtureRecord",
    "StandingRecord",
    "available_adapters",
    "get_adapter",
    "register_adapter",
]
