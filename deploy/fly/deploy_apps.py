"""Deploy playsight-api and/or playsight-worker on Fly.io (remote builder).

Usage:  python deploy/fly/deploy_apps.py [api|worker|all]

Runs `flyctl deploy` from the repo root with -c deploy/fly/<app>.fly.toml and
--dockerfile docker/Dockerfile.<app> so the build context is the repo root.
The worker torch image can take 10-25 minutes on the remote builder.
"""

from __future__ import annotations

import sys

from flylib import REPO_ROOT, run_fly

TARGETS = {
    "api": ("deploy/fly/api.fly.toml", "docker/Dockerfile.api"),
    "worker": ("deploy/fly/worker.fly.toml", "docker/Dockerfile.worker"),
}


def deploy(name: str) -> None:
    config, dockerfile = TARGETS[name]
    proc = run_fly(
        [
            "deploy",
            "-c", config,
            "--dockerfile", dockerfile,
            "--remote-only",
            # depot.dev builder fails TLS verification from this network
            # (x509: unknown authority) — use the classic Fly remote builder.
            "--depot=false",
            "--ha=false",
            "--yes",
            "--wait-timeout", "10m",
        ],
        timeout=3600,
        cwd=REPO_ROOT,
    )
    tail = "\n".join(
        ((proc.stdout or "") + "\n" + (proc.stderr or "")).splitlines()[-40:]
    )
    print(tail)
    if proc.returncode != 0:
        raise SystemExit(f"deploy failed for {name} (rc={proc.returncode})")
    print(f"[ok] {name} deployed")


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(TARGETS) if which == "all" else [which]
    for n in names:
        deploy(n)


if __name__ == "__main__":
    main()
