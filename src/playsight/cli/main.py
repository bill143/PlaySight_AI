"""PlaySight Typer CLI (CONTRACTS.md section 14) — console script ``playsight``.

Every command works without Docker: SQLite database, local object storage, and
eager in-process jobs (the default whenever redis is unreachable).
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from playsight.cli.demo import DEMO_VIDEO_PATH, generate_demo_video, seed_demo_data
from playsight.config.settings import get_settings
from playsight.db.models import Artifact, Club, Match, ProcessingJob, Team
from playsight.db.session import SessionLocal, get_engine, init_db
from playsight.jobs import dispatch_job

app = typer.Typer(
    name="playsight",
    help="PlaySight AI — multi-sport video analytics and club operations.",
    no_args_is_help=True,
)
export_app = typer.Typer(help="Export match reports and audio summaries.", no_args_is_help=True)
youtube_app = typer.Typer(
    help="YouTube OAuth and (rights-confirmed) uploads.", no_args_is_help=True
)
serve_app = typer.Typer(help="Run the API server or a Celery worker.", no_args_is_help=True)
app.add_typer(export_app, name="export")
app.add_typer(youtube_app, name="youtube")
app.add_typer(serve_app, name="serve")

console = Console()
err_console = Console(stderr=True)

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
_VALID_PRIVACY = ("private", "unlisted", "public")
_DEFAULT_EXPORT_DIR = Path("exports")

COPYRIGHT_MESSAGE = (
    "Upload aborted: publishing requires explicit confirmation that you own or have "
    "licensed ALL rights to this footage, including any music and audio. If you have "
    "the rights, re-run with --confirm-rights. Uploads always default to 'private'."
)


def main() -> None:
    """Console-script entry point for the ``playsight`` command."""
    app()


# --- Shared helpers -------------------------------------------------------------------


def _open_session() -> Session:
    """Return a new DB session bound to the process engine."""
    get_engine()
    return SessionLocal()


def _slugify(value: str) -> str:
    """Turn an arbitrary name into a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "club"


def _redis_available(url: str) -> bool:
    """Return whether redis at ``url`` answers a PING within ~1 second."""
    if not url:
        return False
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        return False


def _apply_eager_mode(eager: bool | None) -> None:
    """Default to eager in-process jobs unless a reachable redis (or --no-eager) says otherwise."""
    if eager is False:
        return
    settings = get_settings()
    if eager or not _redis_available(settings.redis_url):
        os.environ["PLAYSIGHT_EAGER_JOBS"] = "1"


def _ensure_club(db: Session, club_ref: str | None) -> Club:
    """Resolve ``--club`` (id or slug) to a Club row, creating one when needed."""
    if club_ref:
        club = db.get(Club, club_ref)
        if club is None:
            club = db.execute(select(Club).where(Club.slug == club_ref)).scalars().first()
        if club is None:
            club = Club(name=club_ref, slug=_slugify(club_ref))
            db.add(club)
            db.commit()
            console.print(f"Created club [bold]{club.name}[/] ({club.id})")
        return club
    club = db.execute(select(Club).order_by(Club.created_at)).scalars().first()
    if club is None:
        club = Club(name="Default Club", slug="default-club")
        db.add(club)
        db.commit()
        console.print(f"Created club [bold]{club.name}[/] ({club.id})")
    return club


def _ensure_team(db: Session, club: Club) -> Team:
    """Return the club's first team, creating a default one when none exists."""
    team = (
        db.execute(select(Team).where(Team.club_id == club.id).order_by(Team.name))
        .scalars()
        .first()
    )
    if team is None:
        team = Team(club_id=club.id, name="Default Team", sport="football")
        db.add(team)
        db.commit()
        console.print(f"Created team [bold]{team.name}[/] ({team.id})")
    return team


def _ensure_match(db: Session, match_id: str | None, club_ref: str | None, video: Path) -> Match:
    """Return the referenced match, creating it (and its club/team) when needed."""
    if match_id:
        match = db.get(Match, match_id)
        if match is not None:
            return match
    club = _ensure_club(db, club_ref)
    team = _ensure_team(db, club)
    match = Match(
        club_id=club.id,
        team_id=team.id,
        opponent=f"Unknown opponent ({video.stem})",
        sport=team.sport,
    )
    if match_id:
        match.id = match_id
    db.add(match)
    db.commit()
    console.print(f"Created match [bold]{match.id}[/] for video {video.name}")
    return match


def _create_job(db: Session, match: Match, kind: str, params: dict | None = None) -> ProcessingJob:
    """Persist a queued ``processing_jobs`` row and return it."""
    job = ProcessingJob(
        club_id=match.club_id,
        match_id=match.id,
        kind=kind,
        params_json=dict(params or {}),
    )
    db.add(job)
    db.commit()
    return job


def _watch_job(db: Session, job_id: str, description: str) -> ProcessingJob:
    """Dispatch a job in a background thread and render live progress until terminal.

    Works for both eager mode (dispatch blocks in the thread while we poll the
    job row) and worker mode (dispatch returns immediately; a Celery worker
    updates the row).
    """
    holder: dict[str, BaseException] = {}

    def _dispatch() -> None:
        session = _open_session()
        try:
            job_row = session.get(ProcessingJob, job_id)
            if job_row is not None:
                dispatch_job(session, job_row)
        except BaseException as exc:  # surfaced to the main thread below
            holder["error"] = exc
        finally:
            session.close()

    thread = threading.Thread(target=_dispatch, name=f"dispatch-{job_id[:8]}", daemon=True)
    thread.start()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress_ui:
        task = progress_ui.add_task(description, total=1.0)
        while True:
            job = db.get(ProcessingJob, job_id)
            if job is None:  # pragma: no cover - row deleted externally
                break
            db.refresh(job)
            progress_ui.update(task, completed=float(job.progress or 0.0))
            if job.status in _TERMINAL_STATUSES:
                if job.status == "succeeded":
                    progress_ui.update(task, completed=1.0)
                break
            if "error" in holder:
                break
            time.sleep(0.3)

    thread.join(timeout=5.0)
    job = db.get(ProcessingJob, job_id)
    assert job is not None
    db.refresh(job)
    if "error" in holder and job.status not in _TERMINAL_STATUSES:
        exc = holder["error"]
        err_console.print(f"[red]Dispatch failed:[/] {type(exc).__name__}: {exc}")
    return job


def _print_artifact_paths(job: ProcessingJob) -> None:
    """Print the artifact paths recorded in a succeeded job's result."""
    result = job.result_json or {}
    paths = result.get("artifact_paths") or {}
    if not paths and result.get("path"):
        paths = {str(result.get("kind", "artifact")): str(result["path"])}
    if not paths:
        return
    table = Table(title="Artifacts", show_lines=False)
    table.add_column("Kind", style="cyan", no_wrap=True)
    table.add_column("Path")
    for kind in sorted(paths):
        table.add_row(kind, str(paths[kind]))
    console.print(table)


def _report_job_outcome(job: ProcessingJob) -> bool:
    """Print a job's terminal outcome; returns True on success."""
    if job.status == "succeeded":
        counts = (job.result_json or {}).get("counts")
        suffix = f" · {counts}" if counts else ""
        console.print(f"[green]Job {job.id} succeeded[/]{suffix}")
        _print_artifact_paths(job)
        return True
    err_console.print(f"[red]Job {job.id} {job.status}[/]: {job.error or 'no error recorded'}")
    return False


def _process_single(
    video: Path, match_id: str | None, club: str | None, eager: bool | None
) -> bool:
    """Create/reuse a match, run the analyze job for one video; returns success."""
    if not video.is_file():
        err_console.print(f"[red]Video not found:[/] {video}")
        return False
    _apply_eager_mode(eager)
    init_db()
    db = _open_session()
    try:
        match = _ensure_match(db, match_id, club, video)
        job = _create_job(db, match, "analyze", params={"video_path": str(video.resolve())})
        console.print(f"Match [bold]{match.id}[/] · job [bold]{job.id}[/] · {video.name}")
        job = _watch_job(db, job.id, f"Analyzing {video.name}")
        return _report_job_outcome(job)
    finally:
        db.close()


def _run_match_job(match_id: str, kind: str, params: dict, eager: bool | None) -> bool:
    """Create and run one non-analysis job against an existing match."""
    _apply_eager_mode(eager)
    init_db()
    db = _open_session()
    try:
        match = db.get(Match, match_id)
        if match is None:
            err_console.print(f"[red]Match not found:[/] {match_id}")
            return False
        job = _create_job(db, match, kind, params=params)
        console.print(f"Match [bold]{match.id}[/] · job [bold]{job.id}[/] · kind={kind}")
        job = _watch_job(db, job.id, f"Running {kind} for match {match_id[:8]}…")
        return _report_job_outcome(job)
    finally:
        db.close()


# --- Commands -------------------------------------------------------------------------


@app.command("init-db")
def init_db_command() -> None:
    """Create all database tables (SQLite/Postgres) for local bootstrap."""
    init_db()
    console.print("[green]Database initialized.[/]")


@app.command("seed-demo")
def seed_demo(
    out: Annotated[Path, typer.Option("--out", help="Demo video output path.")] = DEMO_VIDEO_PATH,
    force: Annotated[
        bool, typer.Option("--force", help="Regenerate the demo video even if it exists.")
    ] = False,
) -> None:
    """Generate the synthetic demo video and seed a demo club/team/players/match."""
    init_db()
    if out.is_file() and not force:
        console.print(f"Demo video already exists at [bold]{out}[/] (use --force to regenerate).")
    else:
        console.print("Generating synthetic demo video (~20s, 640x360 @ 15fps)…")
        generate_demo_video(out)
        console.print(f"Demo video written to [bold]{out}[/]")

    db = _open_session()
    try:
        ids = seed_demo_data(db)
    finally:
        db.close()

    table = Table(title="Demo entities")
    table.add_column("Entity", style="cyan", no_wrap=True)
    table.add_column("Id")
    table.add_row("club", ids["club_id"])
    table.add_row("team", ids["team_id"])
    table.add_row("match", ids["match_id"])
    for jersey, player_id in sorted(ids["player_ids"].items()):
        table.add_row(f"player #{jersey}", player_id)
    console.print(table)
    console.print(f"Next: [bold]playsight process {out} --match-id {ids['match_id']}[/]")


@app.command()
def process(
    video: Annotated[Path, typer.Argument(help="Path to a match video (.mp4/.mov).")],
    match_id: Annotated[
        str | None, typer.Option("--match-id", help="Existing match id (created when missing).")
    ] = None,
    club: Annotated[
        str | None, typer.Option("--club", help="Club id or slug (created when missing).")
    ] = None,
    eager: Annotated[
        bool | None,
        typer.Option(
            "--eager/--no-eager",
            help="Force eager in-process execution (default: eager unless redis is reachable).",
        ),
    ] = None,
) -> None:
    """Process a single match video end-to-end (detect, track, identify, report)."""
    if not _process_single(video, match_id, club, eager):
        raise typer.Exit(code=1)


@app.command("process-folder")
def process_folder(
    directory: Annotated[Path, typer.Argument(help="Directory containing *.mp4/*.mov videos.")],
    club: Annotated[
        str | None, typer.Option("--club", help="Club id or slug (created when missing).")
    ] = None,
    eager: Annotated[
        bool | None,
        typer.Option("--eager/--no-eager", help="Force eager in-process execution."),
    ] = None,
) -> None:
    """Process every *.mp4 / *.mov video in a folder (one match per file)."""
    if not directory.is_dir():
        err_console.print(f"[red]Not a directory:[/] {directory}")
        raise typer.Exit(code=1)
    videos = sorted({*directory.glob("*.mp4"), *directory.glob("*.mov")})
    if not videos:
        err_console.print(f"[red]No *.mp4 or *.mov files found in[/] {directory}")
        raise typer.Exit(code=1)

    console.print(f"Processing {len(videos)} video(s) from {directory}")
    failures = 0
    for video in videos:
        if not _process_single(video, None, club, eager):
            failures += 1
    if failures:
        err_console.print(f"[red]{failures}/{len(videos)} video(s) failed.[/]")
        raise typer.Exit(code=1)
    console.print(f"[green]All {len(videos)} video(s) processed.[/]")


@app.command()
def highlights(
    match_id: Annotated[str, typer.Argument(help="Match id to build highlights for.")],
    player: Annotated[
        str,
        typer.Option(
            "--player",
            help="player_identities row id, a numeric track id, or 'track_<n>'.",
        ),
    ],
    eager: Annotated[
        bool | None,
        typer.Option("--eager/--no-eager", help="Force eager in-process execution."),
    ] = None,
) -> None:
    """Build a per-player highlight reel from the match's detected events."""
    ref = player.strip()
    params: dict[str, object]
    if ref.startswith("track_") and ref[len("track_") :].isdigit():
        params = {"track_id": int(ref[len("track_") :])}
    elif ref.isdigit():
        params = {"track_id": int(ref)}
    else:
        params = {"player_identity_id": ref}
    if not _run_match_job(match_id, "highlights", params, eager):
        raise typer.Exit(code=1)


@export_app.command("report")
def export_report(
    match_id: Annotated[str, typer.Argument(help="Match id whose report to export.")],
    format: Annotated[
        str, typer.Option("--format", help="Report format: 'csv' or 'json'.")
    ] = "csv",
    out: Annotated[
        Path, typer.Option("--out", help="Destination directory for the exported files.")
    ] = _DEFAULT_EXPORT_DIR,
) -> None:
    """Export match report artifacts (stats/identities CSV or summary/report JSON)."""
    kinds_by_format = {
        "csv": ("player_stats", "player_identities"),
        "json": ("match_summary", "player_report_json"),
    }
    if format not in kinds_by_format:
        raise typer.BadParameter("--format must be 'csv' or 'json'")

    init_db()
    db = _open_session()
    try:
        match = db.get(Match, match_id)
        if match is None:
            err_console.print(f"[red]Match not found:[/] {match_id}")
            raise typer.Exit(code=1)
        stmt = select(Artifact).where(
            Artifact.match_id == match_id, Artifact.kind.in_(kinds_by_format[format])
        )
        artifacts = db.execute(stmt).scalars().all()
    finally:
        db.close()

    if not artifacts:
        err_console.print(
            f"[red]No report artifacts for match {match_id}.[/] "
            "Run [bold]playsight process VIDEO --match-id …[/] first."
        )
        raise typer.Exit(code=1)

    from playsight.storage import get_storage

    storage = get_storage(get_settings())
    out.mkdir(parents=True, exist_ok=True)
    table = Table(title=f"Exported {format.upper()} report for match {match_id}")
    table.add_column("Kind", style="cyan", no_wrap=True)
    table.add_column("File")
    for artifact in artifacts:
        dest = out / artifact.filename
        storage.download_to(artifact.storage_key, dest)
        table.add_row(artifact.kind, str(dest))
    console.print(table)


@export_app.command("audio")
def export_audio(
    match_id: Annotated[str, typer.Argument(help="Match id to narrate.")],
    eager: Annotated[
        bool | None,
        typer.Option("--eager/--no-eager", help="Force eager in-process execution."),
    ] = None,
) -> None:
    """Render the spoken audio match summary MP3 (requires a processed match)."""
    if not _run_match_job(match_id, "export_audio", {}, eager):
        raise typer.Exit(code=1)


@youtube_app.command("auth")
def youtube_auth() -> None:
    """Run the Google OAuth2 consent flow and persist the YouTube token."""
    from playsight.integrations.youtube import YouTubeClient

    client = YouTubeClient(get_settings())
    token_path = client.run_local_auth()
    console.print(f"[green]YouTube authorization complete.[/] Token saved to {token_path}")


@youtube_app.command("upload")
def youtube_upload(
    artifact_path: Annotated[Path, typer.Argument(help="Local video file to upload.")],
    title: Annotated[str, typer.Option("--title", help="YouTube video title.")],
    description: Annotated[
        str, typer.Option("--description", help="YouTube video description.")
    ] = "",
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Video tag (repeatable).")] = None,
    category_id: Annotated[
        str, typer.Option("--category-id", help="YouTube category id (17 = Sports).")
    ] = "17",
    privacy: Annotated[
        str, typer.Option("--privacy", help="private | unlisted | public.")
    ] = "private",
    confirm_rights: Annotated[
        bool,
        typer.Option(
            "--confirm-rights",
            help="Confirm you own or have licensed all rights to this footage.",
        ),
    ] = False,
) -> None:
    """Upload a local video to YouTube (requires explicit rights confirmation)."""
    if not confirm_rights:
        err_console.print(f"[red]{COPYRIGHT_MESSAGE}[/]")
        raise typer.Exit(code=2)
    if privacy not in _VALID_PRIVACY:
        raise typer.BadParameter(f"--privacy must be one of {', '.join(_VALID_PRIVACY)}")
    if not artifact_path.is_file():
        err_console.print(f"[red]File not found:[/] {artifact_path}")
        raise typer.Exit(code=1)

    from playsight.integrations.youtube import YouTubeClient

    client = YouTubeClient(get_settings())
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress_ui:
        task = progress_ui.add_task(f"Uploading {artifact_path.name}", total=1.0)
        result = client.upload_video(
            artifact_path,
            title=title,
            description=description,
            tags=list(tag or []),
            category_id=category_id,
            privacy=privacy,
            progress_cb=lambda value: progress_ui.update(task, completed=value),
        )
        progress_ui.update(task, completed=1.0)
    console.print(
        f"[green]Upload complete.[/] video_id={result.video_id} privacy={privacy}\n{result.url}"
    )


@serve_app.command("api")
def serve_api(
    host: Annotated[str, typer.Option("--host", help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Bind port.")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Auto-reload on code changes.")] = False,
) -> None:
    """Run the FastAPI application with uvicorn."""
    import uvicorn

    init_db()
    console.print(f"Serving API at http://{host}:{port} (docs at /docs)")
    uvicorn.run("playsight.api.main:app", host=host, port=port, reload=reload)


@serve_app.command("worker")
def serve_worker(
    loglevel: Annotated[str, typer.Option("--loglevel", help="Celery log level.")] = "INFO",
    concurrency: Annotated[
        int | None, typer.Option("--concurrency", help="Worker process/thread count.")
    ] = None,
    pool: Annotated[
        str | None,
        typer.Option("--pool", help="Celery pool ('solo' default on Windows, else prefork)."),
    ] = None,
) -> None:
    """Run a Celery worker consuming PlaySight jobs (requires redis)."""
    from playsight.jobs import app as celery_app

    init_db()
    resolved_pool = pool or ("solo" if sys.platform == "win32" else "prefork")
    argv = ["worker", f"--loglevel={loglevel}", f"--pool={resolved_pool}"]
    if concurrency is not None:
        argv.append(f"--concurrency={concurrency}")
    console.print(f"Starting Celery worker (pool={resolved_pool})…")
    celery_app.worker_main(argv=argv)


if __name__ == "__main__":  # pragma: no cover
    main()
