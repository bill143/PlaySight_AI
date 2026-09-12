"""Deploy the PlaySight dashboard to Fly.io and lock API CORS to its origin.

Idempotent: safe to re-run. Reads FLY_API_TOKEN from deploy/.secrets/deploy.env;
never prints secret values. Run from repo root:  python deploy/fly/deploy_dashboard.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "deploy" / ".secrets" / "deploy.env"
APP = "playsight-dashboard"
API_APP = "playsight-api"
ORG = "personal"  # Fly org slug for the Billy_AI personal org (billy_ai is only the display alias)
API_URL = "https://playsight-api.fly.dev"
DASH_URL = f"https://{APP}.fly.dev"


def read_env() -> dict[str, str]:
    vals: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def find_flyctl() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local) / "Microsoft/WinGet/Links/flyctl.exe",
        Path(local)
        / "Microsoft/WinGet/Packages/Fly-io.flyctl_Microsoft.Winget.Source_8wekyb3d8bbwe/flyctl.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "flyctl"


FLYCTL = find_flyctl()
TOKEN = read_env().get("FLY_API_TOKEN", "")
if not TOKEN.startswith("FlyV1"):
    sys.exit("FLY_API_TOKEN missing from deploy/.secrets/deploy.env")
FLY_ENV = dict(os.environ, FLY_API_TOKEN=TOKEN, NO_COLOR="1")


def fly(*args: str, timeout: int = 1800, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"$ flyctl {' '.join(args)}", flush=True)
    p = subprocess.run(
        [FLYCTL, *args], env=FLY_ENV, cwd=ROOT, capture_output=True, text=True, timeout=timeout
    )
    tail = (p.stdout + p.stderr).strip().splitlines()[-12:]
    print("\n".join(tail), flush=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"flyctl {' '.join(args[:2])} failed rc={p.returncode}")
    return p


def http_get(url: str, timeout: int = 30) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "playsight-deploy"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


def main() -> None:
    apps = fly("apps", "list", "-o", ORG, "--json", check=False)
    existing = {a.get("Name") or a.get("name") for a in json.loads(apps.stdout or "[]")}
    if APP not in existing:
        fly("apps", "create", APP, "-o", ORG)
    else:
        print(f"{APP} already exists — redeploying")

    deploy_args = [
        "deploy",
        "dashboard",
        "-c",
        str(ROOT / "deploy" / "fly" / "dashboard.fly.toml"),
        "--dockerfile",
        str(ROOT / "docker" / "Dockerfile.dashboard"),
        "--build-arg",
        f"NEXT_PUBLIC_API_URL={API_URL}",
        "--remote-only",
        "--ha=false",
        "--yes",
    ]
    try:
        fly(*deploy_args)
    except RuntimeError:
        # Depot builder TLS/handshake failures observed on this network; the classic
        # remote builder uses a different connection path.
        print("depot builder failed — retrying with --depot=false")
        fly(*deploy_args, "--depot=false")

    for attempt in range(12):
        try:
            status, _, body = http_get(DASH_URL)
            if status == 200:
                print(f"dashboard 200 OK ({len(body)} bytes)")
                break
        except Exception as exc:  # noqa: BLE001 - poll loop
            print(f"poll {attempt + 1}: {exc}")
        time.sleep(10)
    else:
        raise RuntimeError("dashboard never returned 200")

    # Lock API CORS to the dashboard origin (keep localhost for local dev).
    fly(
        "secrets",
        "set",
        f"PLAYSIGHT_CORS_ORIGINS={DASH_URL},http://localhost:3000",
        "-a",
        API_APP,
    )

    # Wait for the API to roll, then verify CORS preflight.
    time.sleep(20)
    for attempt in range(12):
        try:
            req = urllib.request.Request(
                f"{API_URL}/api/v1/health/live",
                method="OPTIONS",
                headers={
                    "Origin": DASH_URL,
                    "Access-Control-Request-Method": "GET",
                    "User-Agent": "playsight-deploy",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                allow = r.headers.get("access-control-allow-origin", "")
            print(f"CORS allow-origin: {allow or '(missing)'}")
            if allow == DASH_URL:
                break
        except Exception as exc:  # noqa: BLE001 - poll loop
            print(f"cors poll {attempt + 1}: {exc}")
        time.sleep(10)
    else:
        raise RuntimeError("CORS allow-origin never reflected the dashboard origin")

    # The CORS secret update rolls the API machine; tolerate the brief 503 window.
    for attempt in range(12):
        try:
            status, _, _ = http_get(f"{API_URL}/api/v1/health/ready")
            print(f"api ready: {status}")
            break
        except Exception as exc:  # noqa: BLE001 - poll loop
            print(f"ready poll {attempt + 1}: {exc}")
            time.sleep(10)
    else:
        raise RuntimeError("api /health/ready did not recover after CORS update")
    print(f"DONE: {DASH_URL}")


if __name__ == "__main__":
    main()
