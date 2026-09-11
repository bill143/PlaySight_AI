"""Day-2 ops posture checks for the Fly.io deployment.

1. Postgres backup posture: unmanaged Fly Postgres has NO managed backup
   service -- protection comes from automatic daily VOLUME SNAPSHOTS
   (5-day retention by default). This script lists the playsight-db volume
   and its snapshots so the honest posture is verifiable on record.
2. Structured logs: pulls recent API logs and confirms JSON log lines with
   correlation ids are present.

Read-only; safe to rerun. Output: deploy/fly/ops_result.json (no secrets).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flylib import run_fly  # noqa: E402

RESULT_FILE = Path(__file__).resolve().parent / "ops_result.json"


def check_pg_snapshots() -> dict[str, Any]:
    out: dict[str, Any] = {"volumes": [], "snapshots": {}}
    proc = run_fly(["volumes", "list", "-a", "playsight-db", "--json"], timeout=60)
    volumes = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else []
    for vol in volumes:
        vol_id = vol.get("id") or vol.get("ID")
        out["volumes"].append(
            {
                "id": vol_id,
                "size_gb": vol.get("size_gb") or vol.get("SizeGb"),
                "snapshot_retention": vol.get("snapshot_retention") or vol.get("SnapshotRetention"),
                "auto_backup_enabled": vol.get("auto_backup_enabled"),
            }
        )
        snap = run_fly(["volumes", "snapshots", "list", str(vol_id), "--json"], timeout=60)
        try:
            rows = json.loads(snap.stdout) if snap.stdout.strip() else []
        except json.JSONDecodeError:
            rows = []
        out["snapshots"][str(vol_id)] = [
            {
                "id": s.get("id"),
                "created_at": s.get("created_at") or s.get("CreatedAt"),
                "size": s.get("size") or s.get("Size"),
                "status": s.get("status"),
            }
            for s in rows
        ]
    return out


def check_structured_logs() -> dict[str, Any]:
    proc = run_fly(["logs", "-a", "playsight-api", "--no-tail"], timeout=90)
    text = (proc.stdout or "") + (proc.stderr or "")
    lines = text.splitlines()
    json_lines = 0
    correlation_hits = 0
    sample = ""
    for line in lines:
        m = re.search(r"\{.*\}", line)
        if not m:
            continue
        try:
            payload = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        json_lines += 1
        if "correlation_id" in payload:
            correlation_hits += 1
            if not sample:
                redacted = {
                    k: payload[k]
                    for k in ("event", "correlation_id", "method", "path", "status_code")
                    if k in payload
                }
                sample = json.dumps(redacted)
    return {
        "total_lines": len(lines),
        "json_log_lines": json_lines,
        "lines_with_correlation_id": correlation_hits,
        "sample": sample,
    }


def main() -> int:
    results = {
        "postgres_backup_posture": check_pg_snapshots(),
        "structured_logs": check_structured_logs(),
    }
    vols = results["postgres_backup_posture"]["volumes"]
    snaps = results["postgres_backup_posture"]["snapshots"]
    has_snapshots = any(snaps.get(str(v["id"])) for v in vols)
    logs_ok = results["structured_logs"]["lines_with_correlation_id"] > 0
    results["summary"] = {
        "pg_volume_count": len(vols),
        "pg_daily_snapshots_present": has_snapshots,
        "structured_logs_with_correlation_ids": logs_ok,
    }
    RESULT_FILE.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    print(f"details -> {RESULT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
