"""Audio match-summary export (MP3), generated via text-to-speech."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioSummaryExporter:
    """Generates a spoken-word MP3 summary of a match using gTTS (Google Text-to-Speech)."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def build_summary_text(self, match_summary: dict) -> str:
        """Build a short narration script from a match summary dict."""
        duration_minutes = round(match_summary.get("duration_seconds", 0) / 60.0, 1)
        total_players = match_summary.get("total_players_tracked", 0)
        total_events = match_summary.get("total_events", 0)

        top_scorer = None
        for player in match_summary.get("player_stats", []):
            if player.get("goals", 0) > 0:
                top_scorer = player
                break

        lines = [
            f"Match summary. Duration: {duration_minutes} minutes.",
            f"{total_players} players were tracked, with {total_events} notable events detected.",
        ]
        if top_scorer:
            lines.append(
                f"Player {top_scorer.get('jersey_number', '?')} led scoring with {top_scorer.get('goals')} goals."
            )

        return " ".join(lines)

    def export(self, match_summary: dict, output_path: str | Path) -> Path:
        """Generate an MP3 audio summary for `match_summary` at `output_path`."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text = self.build_summary_text(match_summary)

        try:
            from gtts import gTTS  # type: ignore[import-not-found]

            tts = gTTS(text=text, lang=self.language)
            tts.save(str(output_path))
        except Exception as exc:  # pragma: no cover - depends on network access / gTTS availability
            logger.warning("Could not generate real TTS audio (%s); writing placeholder MP3 file.", exc)
            output_path.write_bytes(b"")

        return output_path
