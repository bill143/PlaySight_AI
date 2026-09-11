"""Verify the Fly.io backend deployment.

Checks:
  1. https://playsight-api.fly.dev/api/v1/health/live  -> 200
  2. https://playsight-api.fly.dev/api/v1/health/ready -> 200, db+redis "ok"
  3. playsight-worker logs contain the Celery ready banner
  4. flyctl status for both apps shows started machines
"""

from __future__ import annotations

import json
import sys
import urllib.request

from flylib import run_fly

API_BASE = "https://playsight-api.fly.dev"


def http_get(url: str, timeout: int = 20) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        return e.code, e.read().decode()
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main() -> None:
    failures: list[str] = []

    code, body = http_get(f"{API_BASE}/api/v1/health/live")
    print(f"live: {code} {body[:200]}")
    if code != 200:
        failures.append(f"health/live returned {code}")

    code, body = http_get(f"{API_BASE}/api/v1/health/ready")
    print(f"ready: {code} {body[:300]}")
    ok = False
    if code == 200:
        try:
            data = json.loads(body)
            checks = data.get("checks", {})
            ok = checks.get("database") == "ok" and checks.get("redis") == "ok"
        except json.JSONDecodeError:
            pass
    if not ok:
        failures.append(f"health/ready not ok (status {code})")

    try:
        logs = run_fly(
            ["logs", "-a", "playsight-worker", "--no-tail"], quiet=True, timeout=120
        )
        text = (logs.stdout or "") + (logs.stderr or "")
    except Exception as exc:  # noqa: BLE001 — logs may hang if no machine exists
        text = ""
        print(f"worker logs fetch failed: {exc}")
    if "celery@" in text and "ready" in text:
        print("worker: celery ready banner found")
    else:
        failures.append("worker logs: celery ready banner not found")

    for app in ("playsight-api", "playsight-worker"):
        st = run_fly(["status", "-a", app], quiet=True, timeout=120)
        started = "started" in (st.stdout or "")
        print(f"status {app}: {'started' if started else 'NOT started'}")
        if not started:
            failures.append(f"{app} has no started machine")

    if failures:
        print("VERIFY FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("VERIFY PASS")


if __name__ == "__main__":
    main()
