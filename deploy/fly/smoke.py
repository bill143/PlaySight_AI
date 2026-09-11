"""Production smoke test against the PUBLIC Fly.io deployment.

Exercises the full pipeline over https://playsight-api.fly.dev:
bootstrap club -> team/players/match -> upload demo video -> process ->
poll job -> download artifacts (summary/CSV/annotated video/player PDF) ->
export audio + highlights -> tenancy isolation (second club sees 404).

Idempotent: admin credentials are generated once and persisted ONLY into
deploy/.secrets/deploy.env (ADMIN_EMAIL / ADMIN_PASSWORD, CLUB2_EMAIL /
CLUB2_PASSWORD); reruns log in instead of re-registering. Each run creates
a fresh team + match, which is side-effect-safe.

Results (no secrets) are written to deploy/fly/smoke_result.json.
"""

from __future__ import annotations

import json
import secrets as pysecrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

try:  # Use the OS certificate store (Windows corporate roots break certifi).
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - fallback to certifi bundle
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flylib import REPO_ROOT, load_env, run_fly, save_env_keys  # noqa: E402

# Windows consoles/redirects default to cp1252; worker logs are UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://playsight-api.fly.dev/api/v1"
DEMO_VIDEO = REPO_ROOT / "data" / "demo" / "demo_match.mp4"
PERSON_VIDEO = REPO_ROOT / "data" / "demo" / "smoke_person_match.mp4"
PERSON_STILL = REPO_ROOT / "data" / "demo" / "smoke_person_still.jpg"
RESULT_FILE = Path(__file__).resolve().parent / "smoke_result.json"
DOWNLOAD_DIR = REPO_ROOT / "outputs" / "smoke_downloads"

ANALYZE_TIMEOUT_S = 45 * 60
EXPORT_TIMEOUT_S = 20 * 60
POLL_INTERVAL_S = 15
QUEUED_STALL_S = 5 * 60

RESULTS: dict[str, Any] = {"checks": {}, "engines": None, "artifacts": {}}


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS["checks"][name] = {"ok": bool(ok), "detail": detail}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def save_results() -> None:
    RESULT_FILE.write_text(json.dumps(RESULTS, indent=2, default=str) + "\n", encoding="utf-8")


def api(
    method: str,
    path: str,
    token: str | None = None,
    expect: int | tuple[int, ...] = 200,
    **kwargs: Any,
) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.request(method, f"{BASE}{path}", headers=headers, timeout=120, **kwargs)
    expected = (expect,) if isinstance(expect, int) else expect
    if resp.status_code not in expected:
        raise RuntimeError(
            f"{method} {path} -> {resp.status_code} (expected {expected}): {resp.text[:500]}"
        )
    return resp


def ensure_demo_video() -> None:
    """Regenerate the synthetic demo clip if absent (kept for parity checks)."""
    if DEMO_VIDEO.exists() and DEMO_VIDEO.stat().st_size > 0:
        return
    print("demo video missing; regenerating via playsight seed-demo ...")
    playsight = REPO_ROOT / ".venv" / "Scripts" / "playsight"
    subprocess.run([str(playsight), "seed-demo"], cwd=str(REPO_ROOT), check=True, timeout=600)
    if not DEMO_VIDEO.exists():
        raise RuntimeError("seed-demo did not produce data/demo/demo_match.mp4")


def ensure_person_video() -> Path:
    """Build a smoke video that real YOLO can detect people in.

    The synthetic seed-demo video contains no persons, so real engines
    (correctly) find zero tracks and the pipeline emits no identities,
    player PDFs, or highlight targets. To exercise those paths against the
    REAL yolo/bytetrack engines, we pan across a person-bearing still image
    pulled from the worker image's own installed ultralytics test assets
    (site-packages/ultralytics/assets/bus.jpg -- ships with the package,
    no external download).
    """
    if PERSON_VIDEO.exists() and PERSON_VIDEO.stat().st_size > 0:
        return PERSON_VIDEO

    if not PERSON_STILL.exists():
        # flyctl `ssh console -C` strips quotes via shellword parsing, so a
        # remote python -c payload is not viable; sftp get needs no quoting.
        remote = "/usr/local/lib/python3.12/site-packages/ultralytics/assets/bus.jpg"
        PERSON_STILL.parent.mkdir(parents=True, exist_ok=True)
        proc = run_fly(
            ["ssh", "sftp", "get", remote, str(PERSON_STILL), "-a", "playsight-worker"],
            timeout=180,
            quiet=True,
        )
        if not PERSON_STILL.exists() or PERSON_STILL.stat().st_size == 0:
            raise RuntimeError(
                f"asset fetch failed rc={proc.returncode}: "
                f"{(proc.stdout or '') + (proc.stderr or '')}"[-300:]
            )

    import cv2  # local dev dependency; only needed when (re)building the clip
    import numpy as np

    img = cv2.imread(str(PERSON_STILL))
    if img is None:
        raise RuntimeError(f"could not read {PERSON_STILL}")
    fps, seconds, w, h = 25, 12, 1280, 720
    scale = max(w / img.shape[1], h / img.shape[0]) * 1.15
    big = cv2.resize(img, (int(img.shape[1] * scale), int(img.shape[0] * scale)))
    max_dx = big.shape[1] - w
    max_dy = big.shape[0] - h
    writer = cv2.VideoWriter(str(PERSON_VIDEO), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    total = fps * seconds
    for i in range(total):
        t = i / max(total - 1, 1)
        dx = int(max_dx * (0.5 + 0.5 * np.sin(2 * np.pi * t)))
        dy = int(max_dy * (0.5 + 0.5 * np.cos(2 * np.pi * t)))
        writer.write(big[dy : dy + h, dx : dx + w])
    writer.release()
    if not PERSON_VIDEO.exists() or PERSON_VIDEO.stat().st_size == 0:
        raise RuntimeError("failed to render smoke_person_match.mp4")
    print(f"built {PERSON_VIDEO.name}: {PERSON_VIDEO.stat().st_size} bytes")
    return PERSON_VIDEO


def bootstrap_admin() -> str:
    """Register the first club (or log in on rerun). Returns an access token."""
    env = load_env()
    email = env.get("ADMIN_EMAIL") or "playsight-admin@oneillcontractors.com"
    password = env.get("ADMIN_PASSWORD") or pysecrets.token_urlsafe(24)

    resp = requests.post(
        f"{BASE}/auth/register-club",
        json={
            "club_name": "ONeill Contractors FC",
            "email": email,
            "password": password,
            "full_name": "PlaySight Admin",
        },
        timeout=60,
    )
    if resp.status_code == 201:
        save_env_keys({"ADMIN_EMAIL": email, "ADMIN_PASSWORD": password})
        check("bootstrap.register_club", True, "club registered (bootstrap open, first club)")
        return str(resp.json()["access_token"])

    # Bootstrap closed (club already exists from a prior run) -> log in.
    if not env.get("ADMIN_PASSWORD"):
        raise RuntimeError(
            f"register-club returned {resp.status_code} and no stored ADMIN_PASSWORD "
            f"exists for login: {resp.text[:300]}"
        )
    login = api("POST", "/auth/login", json={"email": email, "password": password})
    check("bootstrap.register_club", True, f"rerun: register -> {resp.status_code}, login OK")
    return str(login.json()["access_token"])


def create_fixture(token: str) -> tuple[str, str]:
    """Create team + players + match. Returns (team_id, match_id)."""
    team = api(
        "POST",
        "/teams",
        token,
        expect=201,
        json={"name": f"Smoke Team {int(time.time())}", "sport": "soccer"},
    ).json()
    for i, name in enumerate(["Alex Carter", "Jordan Reyes", "Sam Okafor"], start=1):
        api(
            "POST",
            "/players",
            token,
            expect=201,
            json={"team_id": team["id"], "full_name": name, "jersey_number": i},
        )
    match = api(
        "POST",
        "/matches",
        token,
        expect=201,
        json={
            "team_id": team["id"],
            "opponent": "Smoke Opponent",
            "sport": "soccer",
            "period_config": {"periods": 2, "period_minutes": 45},
        },
    ).json()
    check("fixture.team_players_match", True, f"team={team['id']} match={match['id']}")
    return team["id"], match["id"]


def upload_video(token: str, match_id: str, video: Path) -> str:
    with video.open("rb") as fh:
        asset = api(
            "POST",
            f"/matches/{match_id}/videos",
            token,
            expect=201,
            files={"file": (video.name, fh, "video/mp4")},
        ).json()
    ok = asset.get("status") == "ready" and asset.get("duration_s", 0) > 0
    check("upload.video", ok, f"asset={asset['id']} duration={asset.get('duration_s')}s")
    return str(asset["id"])


def worker_logs_snapshot(lines: int = 40) -> str:
    proc = run_fly(["logs", "-a", "playsight-worker", "--no-tail"], timeout=60, quiet=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return "\n".join(out.splitlines()[-lines:])


def poll_job(token: str, job_id: str, label: str, timeout_s: int) -> dict[str, Any]:
    """Poll /jobs/{id} until succeeded/failed. Diagnose stalls via worker logs."""
    started = time.monotonic()
    last_status = ""
    queued_since = time.monotonic()
    while True:
        job = api("GET", f"/jobs/{job_id}", token).json()
        status = job["status"]
        if status != last_status:
            print(f"  job {job_id} [{label}]: {status} progress={job.get('progress')}")
            last_status = status
            if status != "queued":
                queued_since = 0.0
        if status == "succeeded":
            return job
        if status == "failed":
            print(worker_logs_snapshot())
            raise RuntimeError(f"job {job_id} [{label}] FAILED: {job.get('error')}")
        if status == "queued" and queued_since and time.monotonic() - queued_since > QUEUED_STALL_S:
            print(f"  job stalled in 'queued' > {QUEUED_STALL_S}s; recent worker logs:")
            print(worker_logs_snapshot())
            queued_since = time.monotonic()  # keep waiting, re-snapshot later
        if time.monotonic() - started > timeout_s:
            print(worker_logs_snapshot())
            raise RuntimeError(f"job {job_id} [{label}] timed out after {timeout_s}s")
        time.sleep(POLL_INTERVAL_S)


def download_artifact(token: str, artifact: dict[str, Any]) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOWNLOAD_DIR / artifact["filename"]
    resp = api("GET", f"/artifacts/{artifact['id']}/download", token, stream=True)
    with dest.open("wb") as out:
        for chunk in resp.iter_content(chunk_size=65536):
            out.write(chunk)
    return dest


def verify_artifacts(token: str, match_id: str) -> None:
    artifacts = api("GET", "/artifacts", token, params={"match_id": match_id, "limit": 100}).json()
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for a in artifacts:
        by_kind.setdefault(a["kind"], []).append(a)
    RESULTS["artifacts"]["kinds"] = sorted(by_kind)

    # match_summary.json -- shape + engines
    summary_art = by_kind.get("match_summary", [None])[0]
    if summary_art:
        path = download_artifact(token, summary_art)
        summary = json.loads(path.read_text(encoding="utf-8"))
        engines = summary.get("engine") or {}
        RESULTS["engines"] = engines
        shape_ok = all(k in summary for k in ("match_id", "engine")) and path.stat().st_size > 0
        check("artifact.match_summary", shape_ok, f"{path.stat().st_size} bytes engines={engines}")
        real = (
            engines.get("detector") == "yolo"
            and engines.get("tracker") == "bytetrack"
            and engines.get("ocr") == "easyocr"
        )
        check("engines.real_cv", real, f"detector/tracker/ocr = {engines}")
    else:
        check("artifact.match_summary", False, "no match_summary artifact")

    # player_stats CSV
    stats_art = by_kind.get("player_stats", [None])[0]
    if stats_art:
        path = download_artifact(token, stats_art)
        text = path.read_text(encoding="utf-8", errors="replace")
        check(
            "artifact.player_stats_csv",
            path.stat().st_size > 0 and "," in text.splitlines()[0],
            f"{path.stat().st_size} bytes",
        )
    else:
        check("artifact.player_stats_csv", False, "no player_stats artifact")

    # annotated video
    vid_art = by_kind.get("annotated_video", [None])[0]
    if vid_art:
        path = download_artifact(token, vid_art)
        check("artifact.annotated_video", path.stat().st_size > 0, f"{path.stat().st_size} bytes")
    else:
        check("artifact.annotated_video", False, "no annotated_video artifact")

    # one player PDF (%PDF magic)
    pdf_art = by_kind.get("player_report_pdf", [None])[0]
    if pdf_art:
        path = download_artifact(token, pdf_art)
        magic = path.read_bytes()[:5]
        check(
            "artifact.player_pdf",
            magic.startswith(b"%PDF"),
            f"{path.stat().st_size} bytes magic={magic!r}",
        )
    else:
        check("artifact.player_pdf", False, "no player_report_pdf artifact")


def run_exports(token: str, match_id: str) -> None:
    # audio export
    job = api("POST", f"/matches/{match_id}/export/audio", token, expect=202).json()
    poll_job(token, job["job_id"], "export_audio", EXPORT_TIMEOUT_S)
    audio = api(
        "GET", "/artifacts", token, params={"match_id": match_id, "kind": "match_audio"}
    ).json()
    if audio:
        path = download_artifact(token, audio[0])
        check("artifact.match_audio", path.stat().st_size > 0, f"{path.stat().st_size} bytes")
    else:
        check("artifact.match_audio", False, "no match_audio artifact after export job")

    # highlights: target the first identity from stats
    stats = api("GET", f"/matches/{match_id}/stats", token).json()
    if not stats:
        check("artifact.player_highlights", False, "no player stats/identities to target")
        return
    payload: dict[str, Any]
    if stats[0].get("identity"):
        payload = {"player_identity_id": stats[0]["identity"]["id"]}
    else:
        payload = {"player_identity_id": stats[0]["player_identity_id"]}
    job = api("POST", f"/matches/{match_id}/highlights", token, expect=202, json=payload).json()
    poll_job(token, job["job_id"], "highlights", EXPORT_TIMEOUT_S)
    reels = api(
        "GET", "/artifacts", token, params={"match_id": match_id, "kind": "player_highlights"}
    ).json()
    if reels:
        path = download_artifact(token, reels[0])
        check("artifact.player_highlights", path.stat().st_size > 0, f"{path.stat().st_size} bytes")
    else:
        check("artifact.player_highlights", False, "no player_highlights artifact")


CLUB2_SEED_TEMPLATE = """
from playsight.db.session import get_engine, session_scope
from playsight.db.models import Club, User, UserRole
from playsight.auth.security import hash_password
get_engine()
with session_scope() as db:
    club = db.query(Club).filter(Club.slug == "smoke-club-two").one_or_none()
    if club is None:
        club = Club(name="Smoke Club Two", slug="smoke-club-two", settings_json={})
        db.add(club)
        db.flush()
    user = db.query(User).filter(User.email == "EMAIL").one_or_none()
    if user is None:
        user = User(club_id=club.id, email="EMAIL",
                    hashed_password=hash_password("PASSWORD"),
                    full_name="Smoke Tenant Two", is_active=True)
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role="admin", club_id=club.id))
    print("CLUB2_OK", club.id, user.id)
"""


def ensure_club2() -> tuple[str, str]:
    """Create a second club + admin directly in the prod DB via fly ssh.

    Prod bootstrap is single-club by design (register-club answers 403 once a
    club exists), so tenancy needs a DB-level seed executed inside the API
    container. Idempotent; credentials only in deploy.env.
    """
    env = load_env()
    email = env.get("CLUB2_EMAIL") or "playsight-club2@oneillcontractors.com"
    password = env.get("CLUB2_PASSWORD") or pysecrets.token_urlsafe(24)
    save_env_keys({"CLUB2_EMAIL": email, "CLUB2_PASSWORD": password})

    # flyctl `ssh console -C` strips quotes (shellword parsing), so ship the
    # script via sftp put and run it by path (no quoting needed). quiet=True:
    # the script embeds the password and must never be echoed or logged.
    script = CLUB2_SEED_TEMPLATE.replace("EMAIL", email).replace("PASSWORD", password)
    local = Path(tempfile.gettempdir()) / "playsight_seed_club2.py"
    local.write_text(script, encoding="utf-8")
    remote = "/tmp/playsight_seed_club2.py"
    try:
        run_fly(  # clear any leftover from an aborted run; sftp put won't overwrite
            ["ssh", "console", "-a", "playsight-api", "-C", f"rm -f {remote}"],
            timeout=60,
            quiet=True,
        )
        run_fly(
            ["ssh", "sftp", "put", str(local), remote, "-a", "playsight-api"],
            timeout=120,
            quiet=True,
        )
        proc = run_fly(
            ["ssh", "console", "-a", "playsight-api", "-C", f"python {remote}"],
            timeout=120,
            quiet=True,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if "CLUB2_OK" not in out:
            raise RuntimeError(f"club2 seed failed rc={proc.returncode}: {out[-500:]}")
    finally:
        run_fly(
            ["ssh", "console", "-a", "playsight-api", "-C", f"rm -f {remote}"],
            timeout=60,
            quiet=True,
        )
        local.unlink(missing_ok=True)
    return email, password


def verify_tenancy(match_id: str, artifact_token: str) -> None:
    # register-club must be closed in prod once a club exists
    resp = requests.post(
        f"{BASE}/auth/register-club",
        json={
            "club_name": "Should Be Closed",
            "email": "closed@example.com",
            "password": "x" * 12,
            "full_name": "Nobody",
        },
        timeout=60,
    )
    check("tenancy.bootstrap_closed", resp.status_code == 403, f"register -> {resp.status_code}")

    email, password = ensure_club2()
    login = api("POST", "/auth/login", json={"email": email, "password": password})
    token2 = login.json()["access_token"]

    resp = requests.get(
        f"{BASE}/matches/{match_id}",
        headers={"Authorization": f"Bearer {token2}"},
        timeout=60,
    )
    check(
        "tenancy.cross_club_match_404", resp.status_code == 404, f"GET match -> {resp.status_code}"
    )

    arts = api(
        "GET", "/artifacts", artifact_token, params={"match_id": match_id, "limit": 1}
    ).json()
    if arts:
        resp = requests.get(
            f"{BASE}/artifacts/{arts[0]['id']}/download",
            headers={"Authorization": f"Bearer {token2}"},
            timeout=60,
        )
        check(
            "tenancy.cross_club_artifact_404",
            resp.status_code == 404,
            f"GET artifact download -> {resp.status_code}",
        )


def main() -> int:
    print(f"SMOKE against {BASE}")
    ok = True
    try:
        live = requests.get(f"{BASE}/health/live", timeout=30)
        check("health.live", live.status_code == 200, live.text[:100])
        # /ready probes Upstash with a 1s socket timeout; isolated errors are
        # transient (documented in DEPLOY_LOG) -- retry before judging.
        attempts = 0
        while True:
            attempts += 1
            ready = requests.get(f"{BASE}/health/ready", timeout=30)
            if ready.status_code == 200 or attempts >= 3:
                break
            time.sleep(10)
        check("health.ready", ready.status_code == 200, f"attempts={attempts} {ready.text[:150]}")

        ensure_demo_video()
        video = ensure_person_video()
        token = bootstrap_admin()
        _team_id, match_id = create_fixture(token)
        RESULTS["match_id"] = match_id
        upload_video(token, match_id, video)

        job = api("POST", f"/matches/{match_id}/process", token, expect=202).json()
        analyze = poll_job(token, job["job_id"], "analyze", ANALYZE_TIMEOUT_S)
        check("pipeline.analyze_succeeded", True, f"job={analyze['id']}")

        verify_artifacts(token, match_id)
        run_exports(token, match_id)
        verify_tenancy(match_id, token)
    except Exception as exc:  # noqa: BLE001 - top-level smoke harness reporting
        check("smoke.unhandled", False, str(exc)[:500])
        ok = False

    ok = ok and all(c["ok"] for c in RESULTS["checks"].values())
    RESULTS["passed"] = ok
    save_results()
    print(f"SMOKE RESULT: {'PASS' if ok else 'FAIL'} -> {RESULT_FILE}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
