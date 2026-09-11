"""Shared helpers for the Fly.io provisioning scripts.

Secrets are read from deploy/.secrets/deploy.env at runtime and are NEVER
printed. State (resource ids/names only, no secrets) lives in
deploy/fly/state.json so every script is idempotent and re-runnable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_ENV = REPO_ROOT / "deploy" / ".secrets" / "deploy.env"
STATE_FILE = Path(__file__).resolve().parent / "state.json"

FLYCTL = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
    r"\Fly-io.flyctl_Microsoft.Winget.Source_8wekyb3d8bbwe\flyctl.exe"
)
ORG = "personal"  # `flyctl orgs list` reports slug `personal` for Billy_AI
REGION = "ord"


def load_env() -> dict[str, str]:
    """Parse deploy.env into a dict (values never logged)."""
    env: dict[str, str] = {}
    for line in SECRETS_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def save_env_keys(pairs: dict[str, str]) -> None:
    """Append/overwrite keys in deploy.env idempotently (values never printed)."""
    existing = SECRETS_ENV.read_text(encoding="utf-8").splitlines()
    keys = set(pairs)
    kept = [ln for ln in existing if ln.split("=", 1)[0].strip() not in keys]
    while kept and not kept[-1].strip():
        kept.pop()
    lines = kept + [f"{k}={v}" for k, v in sorted(pairs.items())]
    SECRETS_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fly_env() -> dict[str, str]:
    env = dict(os.environ)
    token = load_env().get("FLY_API_TOKEN", "")
    if not token:
        print("FATAL: FLY_API_TOKEN missing from deploy.env", file=sys.stderr)
        sys.exit(2)
    env["FLY_API_TOKEN"] = token
    env["NO_COLOR"] = "1"
    return env


def run_fly(
    args: list[str],
    *,
    timeout: int = 600,
    check: bool = False,
    quiet: bool = False,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run flyctl with the token in the environment. Never echoes the token."""
    cmd = [FLYCTL] + args
    if not quiet:
        print(f"$ flyctl {' '.join(args)}")
    proc = subprocess.run(
        cmd,
        env=fly_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # flyctl emits UTF-8; Windows default cp1252 chokes
        timeout=timeout,
        cwd=str(cwd or REPO_ROOT),
    )
    if check and proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"flyctl {' '.join(args[:2])} failed rc={proc.returncode}")
    return proc


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def app_exists(name: str) -> bool:
    proc = run_fly(["apps", "list", "--json"], quiet=True)
    if proc.returncode != 0:
        return False
    try:
        apps = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    return any(a.get("Name") == name or a.get("name") == name for a in apps)
