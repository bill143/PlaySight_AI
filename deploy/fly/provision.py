"""Idempotent Fly.io resource provisioner for PlaySight_AI.

Creates (skipping anything that already exists):
  1. Fly Postgres cluster  `playsight-db`   (unmanaged, shared-cpu-1x, 3 GB volume)
  2. Upstash Redis         `playsight-redis` (no eviction; fallback: redis:7 fly app)
  3. Fly apps              `playsight-api`, `playsight-worker`
  4. Tigris object storage bucket `playsight` (associated with playsight-api)

Credentials printed once by flyctl are parsed and written ONLY to
deploy/.secrets/deploy.env (gitignored). Nothing secret is echoed.
"""

from __future__ import annotations

import re
import sys

from flylib import (
    ORG,
    REGION,
    app_exists,
    load_env,
    load_state,
    run_fly,
    save_env_keys,
    save_state,
)

PG_APP = "playsight-db"
REDIS_NAME = "playsight-redis"
API_APP = "playsight-api"
WORKER_APP = "playsight-worker"
BUCKET = "playsight"


def provision_postgres(state: dict) -> None:
    if state.get("postgres", {}).get("created") or app_exists(PG_APP):
        print(f"[skip] postgres {PG_APP} already exists")
        state.setdefault("postgres", {})["created"] = True
        return
    proc = run_fly(
        [
            "postgres", "create",
            "--name", PG_APP,
            "--org", ORG,
            "--region", REGION,
            "--initial-cluster-size", "1",
            "--vm-size", "shared-cpu-1x",
            "--volume-size", "3",
        ],
        timeout=1200,
    )
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        # Do not print raw output blindly — it may contain the password line.
        safe = "\n".join(
            ln for ln in out.splitlines() if "password" not in ln.lower()
        )
        print(safe, file=sys.stderr)
        raise SystemExit("postgres create failed")

    def grab(pattern: str) -> str:
        m = re.search(pattern, out, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else ""

    username = grab(r"^\s*Username:\s*(\S+)")
    password = grab(r"^\s*Password:\s*(\S+)")
    hostname = grab(r"^\s*Hostname:\s*(\S+)")
    proxy_port = grab(r"^\s*Proxy port:\s*(\S+)") or "5432"
    conn = grab(r"Connection string:\s*(\S+)")
    if not (username and password):
        raise SystemExit("could not parse postgres credentials from create output")
    # Internal host: prefer what the connection string reports (flycast proxy).
    host = hostname or f"{PG_APP}.flycast"
    m = re.search(r"@([^:/]+):(\d+)", conn)
    if m:
        host, proxy_port = m.group(1), m.group(2)
    save_env_keys(
        {
            "PG_USER": username,
            "PG_PASSWORD": password,
            "PG_HOST": host,
            "PG_PORT": proxy_port,
            "PG_DB": "postgres",  # default db — decision logged in DEPLOY_LOG
            "PG_CONN_STRING": conn,
        }
    )
    state["postgres"] = {
        "created": True,
        "app": PG_APP,
        "host": host,
        "port": proxy_port,
        "db": "postgres",
    }
    save_state(state)
    print(f"[ok] postgres {PG_APP} created; creds saved to deploy.env (host {host}:{proxy_port})")


def provision_redis(state: dict) -> None:
    env = load_env()
    if state.get("redis", {}).get("created") and env.get("UPSTASH_REDIS_URL"):
        print(f"[skip] redis {REDIS_NAME} already provisioned")
        return
    # Check for an existing Upstash db first.
    lst = run_fly(["redis", "list"], quiet=True)
    exists = REDIS_NAME in (lst.stdout or "")
    out = ""
    if not exists:
        proc = run_fly(
            [
                "redis", "create",
                "--name", REDIS_NAME,
                "--org", ORG,
                "--region", REGION,
                "--disable-eviction",
                "--no-replicas",
            ],
            timeout=600,
        )
        out = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0:
            safe = "\n".join(ln for ln in out.splitlines() if "redis://" not in ln)
            print(safe, file=sys.stderr)
            state.setdefault("redis", {})["create_error"] = True
            save_state(state)
            raise SystemExit("redis create failed (fallback: run provision with redis app image)")
    m = re.search(r"(redis://\S+)", out)
    url = m.group(1).strip().rstrip(",") if m else ""
    if not url:
        # Fetch from status (private URL).
        st = run_fly(["redis", "status", REDIS_NAME], quiet=True)
        m = re.search(r"(redis://\S+)", st.stdout or "")
        url = m.group(1).strip().rstrip(",") if m else ""
    if not url:
        raise SystemExit("could not determine Upstash redis private URL")
    save_env_keys({"UPSTASH_REDIS_URL": url})
    state["redis"] = {"created": True, "name": REDIS_NAME, "kind": "upstash"}
    save_state(state)
    print(f"[ok] redis {REDIS_NAME} ready; URL saved to deploy.env")


def provision_apps(state: dict) -> None:
    for app in (API_APP, WORKER_APP):
        if app_exists(app):
            print(f"[skip] app {app} already exists")
            continue
        run_fly(["apps", "create", app, "--org", ORG], check=True)
        print(f"[ok] app {app} created")
    state["apps"] = {"api": API_APP, "worker": WORKER_APP}
    save_state(state)


def provision_storage(state: dict) -> None:
    env = load_env()
    if state.get("tigris", {}).get("created") and env.get("TIGRIS_AWS_SECRET_ACCESS_KEY"):
        print("[skip] tigris bucket already provisioned")
        return
    proc = run_fly(
        ["storage", "create", "-n", BUCKET, "-o", ORG, "-a", API_APP, "-y"],
        timeout=600,
    )
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        safe = "\n".join(ln for ln in out.splitlines() if "SECRET" not in ln.upper() or ":" not in ln)
        print(safe, file=sys.stderr)
        raise SystemExit("storage create failed")

    def grab(key: str) -> str:
        m = re.search(rf"{key}[:=]\s*(\S+)", out)
        return m.group(1).strip() if m else ""

    keys = {
        "TIGRIS_AWS_ACCESS_KEY_ID": grab("AWS_ACCESS_KEY_ID"),
        "TIGRIS_AWS_SECRET_ACCESS_KEY": grab("AWS_SECRET_ACCESS_KEY"),
        "TIGRIS_BUCKET_NAME": grab("BUCKET_NAME") or BUCKET,
        "TIGRIS_AWS_ENDPOINT_URL_S3": grab("AWS_ENDPOINT_URL_S3") or "https://fly.storage.tigris.dev",
        "TIGRIS_AWS_REGION": grab("AWS_REGION") or "auto",
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        raise SystemExit(f"storage create output missing: {missing}")
    save_env_keys(keys)
    state["tigris"] = {"created": True, "bucket": keys["TIGRIS_BUCKET_NAME"]}
    save_state(state)
    print(f"[ok] tigris bucket {keys['TIGRIS_BUCKET_NAME']} created; keys saved to deploy.env")


def main() -> None:
    state = load_state()
    provision_postgres(state)
    provision_redis(state)
    provision_apps(state)
    provision_storage(state)
    print("PROVISION COMPLETE")


if __name__ == "__main__":
    main()
