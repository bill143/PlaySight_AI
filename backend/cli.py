"""Command-line interface for PlaySight AI operations.

Usage examples:
    python backend/cli.py process-video data/samples/match1.mp4
    python backend/cli.py process-folder data/samples/
    python backend/cli.py export-reports --format csv,json --match-id <id>
    python backend/cli.py generate-highlights --player-id <id> --match-id <id>
    python backend/cli.py export-audio --match-id <id>
    python backend/cli.py upload-youtube --match-id <id> --privacy private
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from backend.core.config import settings
from backend.export.audio_export import AudioSummaryExporter
from backend.export.data_export import DataExporter, ExportFormat
from backend.highlights.merger import ClipMerger
from backend.pipeline.processor import MatchProcessor


@click.group()
def cli() -> None:
    """PlaySight AI command-line tools."""


@cli.command("process-video")
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--output-dir", default=None, help="Directory to write pipeline outputs to.")
@click.option("--match-id", default=None, help="Match identifier to associate with outputs.")
@click.option("--metadata", default="{}", help="JSON string of match metadata.")
def process_video(video_path: str, output_dir: str | None, match_id: str | None, metadata: str) -> None:
    """Run the full analytics pipeline on a single video file."""
    match_id = match_id or Path(video_path).stem
    output_dir = output_dir or str(Path(settings.OUTPUT_DIR) / match_id)

    processor = MatchProcessor()
    result = processor.process_match(
        video_path=video_path,
        metadata=json.loads(metadata),
        output_dir=output_dir,
        match_id=match_id,
        progress_callback=lambda progress, stage: click.echo(f"[{progress:>3}%] {stage}"),
    )

    click.echo(f"Done. Outputs written to: {result.output_dir}")


@cli.command("process-folder")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
@click.option("--output-dir", default=None, help="Base directory to write pipeline outputs to.")
@click.option("--extensions", default=".mp4,.mov,.avi,.mkv", help="Comma-separated list of video extensions to process.")
def process_folder(folder_path: str, output_dir: str | None, extensions: str) -> None:
    """Run the full analytics pipeline on every video file in a folder."""
    exts = {e.strip().lower() for e in extensions.split(",")}
    processor = MatchProcessor()

    videos = sorted(p for p in Path(folder_path).iterdir() if p.suffix.lower() in exts)
    if not videos:
        click.echo("No matching video files found.")
        return

    for video_path in videos:
        match_id = video_path.stem
        match_output_dir = Path(output_dir) / match_id if output_dir else Path(settings.OUTPUT_DIR) / match_id
        click.echo(f"Processing {video_path} -> {match_output_dir}")
        processor.process_match(video_path=str(video_path), metadata={}, output_dir=match_output_dir, match_id=match_id)

    click.echo(f"Processed {len(videos)} video(s).")


@cli.command("export-reports")
@click.option("--format", "formats", default="csv,json", help="Comma-separated export formats: csv,json,parquet.")
@click.option("--match-id", required=True, help="Match identifier whose player_stats.csv should be re-exported.")
def export_reports(formats: str, match_id: str) -> None:
    """Re-export a match's player statistics into one or more formats."""
    import pandas as pd

    output_dir = Path(settings.OUTPUT_DIR) / match_id
    stats_csv = output_dir / "player_stats.csv"
    if not stats_csv.exists():
        raise click.ClickException(f"No player_stats.csv found at {stats_csv}. Run process-video first.")

    records = pd.read_csv(stats_csv).to_dict(orient="records")
    valid_formats: list[ExportFormat] = [f.strip() for f in formats.split(",") if f.strip() in ("csv", "json", "parquet")]  # type: ignore[misc]

    exporter = DataExporter()
    exported = exporter.export_multi(records, output_dir, base_name="player_stats_export", formats=valid_formats)
    for fmt, path in exported.items():
        click.echo(f"Exported {fmt} -> {path}")


@cli.command("generate-highlights")
@click.option("--player-id", "track_id", required=True, help="Track/player identifier to generate highlights for.")
@click.option("--match-id", required=True, help="Match identifier.")
def generate_highlights(track_id: str, match_id: str) -> None:
    """Merge previously extracted event clips into a single highlight reel for a player."""
    output_dir = Path(settings.OUTPUT_DIR) / match_id
    clips_dir = output_dir / "_clips" / track_id
    clip_paths = sorted(clips_dir.glob("*.mp4")) if clips_dir.exists() else []

    if not clip_paths:
        raise click.ClickException(f"No clips found for player/track {track_id} in match {match_id}.")

    merger = ClipMerger()
    highlight_path = output_dir / f"player_highlights_{track_id}.mp4"
    merger.merge(clip_paths, highlight_path)
    click.echo(f"Highlight reel written to: {highlight_path}")


@cli.command("export-audio")
@click.option("--match-id", required=True, help="Match identifier whose match_summary.json should be narrated.")
def export_audio(match_id: str) -> None:
    """Generate an MP3 audio summary from a match's match_summary.json."""
    output_dir = Path(settings.OUTPUT_DIR) / match_id
    summary_path = output_dir / "match_summary.json"
    if not summary_path.exists():
        raise click.ClickException(f"No match_summary.json found at {summary_path}. Run process-video first.")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    exporter = AudioSummaryExporter()
    audio_path = exporter.export(summary.get("summary", summary), output_dir / "match_summary_audio.mp3")
    click.echo(f"Audio summary written to: {audio_path}")


@cli.command("upload-youtube")
@click.option("--match-id", required=True, help="Match identifier whose annotated video should be uploaded.")
@click.option("--privacy", default="private", type=click.Choice(["private", "unlisted", "public"]))
@click.option("--title", default=None, help="Video title (defaults to the match id).")
def upload_youtube(match_id: str, privacy: str, title: str | None) -> None:
    """Upload a match's annotated video to YouTube."""
    from backend.integrations.youtube.models import YouTubeUploadRequest
    from backend.integrations.youtube.uploader import YouTubeUploader

    output_dir = Path(settings.OUTPUT_DIR) / match_id
    video_path = output_dir / "annotated_video.mp4"
    if not video_path.exists():
        raise click.ClickException(f"No annotated_video.mp4 found at {video_path}. Run process-video first.")

    uploader = YouTubeUploader()
    request = YouTubeUploadRequest(
        file_path=str(video_path),
        title=title or f"PlaySight AI - Match {match_id}",
        privacy_status=privacy,  # type: ignore[arg-type]
    )
    result = uploader.upload(account_key="default", request=request)

    if result.success:
        click.echo(f"Uploaded: {result.video_url}")
    else:
        raise click.ClickException(f"Upload failed: {result.error_message}")


if __name__ == "__main__":
    cli()
