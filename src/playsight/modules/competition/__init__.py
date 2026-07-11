"""Competition module: fixtures/standings sync adapters (feature flag ``competition``)."""

from playsight.modules.competition.service import CompetitionService
from playsight.modules.competition.sync import SyncResult, compute_change_hash, sync_competition

__all__ = ["CompetitionService", "SyncResult", "compute_change_hash", "sync_competition"]
