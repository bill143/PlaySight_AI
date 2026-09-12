"""Create a club + admin user in the PRODUCTION database (operator tool).

Bootstrap self-registration is closed in prod by design; this is the sanctioned
path for adding a new club. Opens a temporary `flyctl proxy` tunnel to
playsight-db, inserts Club/User/UserRole rows using the app's own hashing, and
appends the generated credentials to deploy/.secrets/deploy.env (never printed).

Usage (repo root):
  .venv/Scripts/python.exe deploy/fly/create_admin.py "Club Name" "Full Name" email@example.com
Idempotent: an existing email aborts with a clear message (no silent overwrite).
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "deploy" / ".secrets" / "deploy.env"
PROXY_PORT = 15432
API_URL = "https://playsight-api.fly.dev"


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
    for c in (
        Path(local) / "Microsoft/WinGet/Links/flyctl.exe",
        Path(local)
        / "Microsoft/WinGet/Packages/Fly-io.flyctl_Microsoft.Winget.Source_8wekyb3d8bbwe/flyctl.exe",
    ):
        if c.exists():
            return str(c)
    return "flyctl"


def wait_port(port: int, timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(2)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(1)
    raise RuntimeError(f"proxy port {port} never opened")


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit('usage: create_admin.py "Club Name" "Full Name" email')
    club_name, full_name, email = sys.argv[1], sys.argv[2], sys.argv[3].lower()

    env = read_env()
    token = env.get("FLY_API_TOKEN", "")
    pg_password = env.get("PG_PASSWORD", "")
    pg_db = env.get("PG_DB", "postgres")
    if not token or not pg_password:
        sys.exit("FLY_API_TOKEN / PG_PASSWORD missing from deploy.env")

    proxy = subprocess.Popen(
        [find_flyctl(), "proxy", f"{PROXY_PORT}:5432", "-a", "playsight-db"],
        env=dict(os.environ, FLY_API_TOKEN=token, NO_COLOR="1"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_port(PROXY_PORT)
        os.environ["PLAYSIGHT_DATABASE_URL"] = (
            f"postgresql+psycopg2://postgres:{pg_password}@127.0.0.1:{PROXY_PORT}/{pg_db}"
        )

        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session

        from playsight.auth.rbac import Role
        from playsight.auth.security import hash_password
        from playsight.db.models import Club, User, UserRole

        engine = create_engine(os.environ["PLAYSIGHT_DATABASE_URL"], pool_pre_ping=True)
        password = secrets.token_urlsafe(18)
        slug_base = "".join(c if c.isalnum() else "-" for c in club_name.lower()).strip("-")

        with Session(engine) as db:
            if db.scalar(select(User).where(User.email == email)):
                sys.exit(f"ABORT: a user with email {email} already exists — no changes made")
            slug = slug_base
            n = 2
            while db.scalar(select(Club).where(Club.slug == slug)):
                slug = f"{slug_base}-{n}"
                n += 1
            club = Club(name=club_name, slug=slug, settings_json={})
            db.add(club)
            db.flush()
            user = User(
                club_id=club.id,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role=Role.ADMIN.value, club_id=club.id))
            db.commit()
            print(f"created club '{club_name}' (slug={slug}) with admin {email}")

        with ENV_FILE.open("a") as f:
            f.write(f"NEW_ADMIN_EMAIL={email}\nNEW_ADMIN_PASSWORD={password}\n")
        print("credentials appended to deploy/.secrets/deploy.env (NEW_ADMIN_*)")
    finally:
        proxy.terminate()

    # Verify through the PUBLIC api that login works.
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{API_URL}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "playsight-ops"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        ok = r.status == 200 and b"access_token" in r.read()
    print(f"public login verification: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
