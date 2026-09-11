"""Shared Render REST API helper for PlaySight deploy scripts.

Reads secrets from deploy/.secrets/deploy.env at runtime. NEVER prints secret
values; API errors are printed with bodies (Render error bodies do not echo
auth headers). All scripts in this directory are committed for reproducibility.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

API_BASE = "https://api.render.com/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_FILE = REPO_ROOT / "deploy" / ".secrets" / "deploy.env"
STATE_FILE = Path(__file__).resolve().parent / "state.json"

REGION = "oregon"
REPO_URL = "https://github.com/bill143/PlaySight_AI"
BRANCH = "main"


def load_env() -> dict[str, str]:
    """Parse deploy.env (KEY=VALUE lines, # comments) into a dict."""
    env: dict[str, str] = {}
    if not SECRETS_FILE.exists():
        sys.exit(f"missing secrets file: {SECRETS_FILE}")
    for raw in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def append_secret(key: str, value: str) -> None:
    """Append KEY=VALUE to deploy.env if the key is absent or empty."""
    env = load_env()
    if env.get(key):
        return
    with SECRETS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{key}={value}\n")


def session() -> requests.Session:
    env = load_env()
    key = env.get("RENDER_API_KEY")
    if not key:
        sys.exit("RENDER_API_KEY missing in deploy.env")
    ses = requests.Session()
    ses.headers.update(
        {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    )
    return ses


def owner_id() -> str:
    oid = load_env().get("RENDER_OWNER_ID")
    if not oid:
        sys.exit("RENDER_OWNER_ID missing in deploy.env")
    return oid


def api(
    ses: requests.Session,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    ok: tuple[int, ...] = (200, 201),
) -> Any:
    resp = ses.request(
        method,
        f"{API_BASE}{path}",
        json=payload,
        params=params,
        timeout=60,
    )
    if resp.status_code not in ok:
        raise RuntimeError(
            f"{method} {path} -> {resp.status_code}: {resp.text[:2000]}"
        )
    if resp.text:
        return resp.json()
    return None


def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
