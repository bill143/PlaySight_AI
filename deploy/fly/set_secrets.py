"""Set production secrets on playsight-api and playsight-worker (idempotent).

Values come from deploy/.secrets/deploy.env; they are passed to `flyctl secrets
set --stage` via argv (never echoed, never logged). `--stage` avoids triggering
a deploy before the first image exists.
"""

from __future__ import annotations

import sys

from flylib import load_env, run_fly

API_APP = "playsight-api"
WORKER_APP = "playsight-worker"


def build_secrets(env: dict[str, str]) -> dict[str, str]:
    required = [
        "PG_USER", "PG_PASSWORD", "PG_HOST", "PG_PORT", "PG_DB",
        "UPSTASH_REDIS_URL", "PROD_JWT_SECRET",
        "TIGRIS_AWS_ACCESS_KEY_ID", "TIGRIS_AWS_SECRET_ACCESS_KEY",
        "TIGRIS_BUCKET_NAME", "TIGRIS_AWS_ENDPOINT_URL_S3",
    ]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise SystemExit(f"deploy.env missing required keys: {missing}")
    db_url = (
        f"postgresql+psycopg2://{env['PG_USER']}:{env['PG_PASSWORD']}"
        f"@{env['PG_HOST']}:{env['PG_PORT']}/{env['PG_DB']}"
    )
    return {
        "PLAYSIGHT_ENV": "prod",
        "PLAYSIGHT_DATABASE_URL": db_url,
        "PLAYSIGHT_REDIS_URL": env["UPSTASH_REDIS_URL"],
        "PLAYSIGHT_STORAGE__BACKEND": "s3",
        "PLAYSIGHT_STORAGE__S3_ENDPOINT": env["TIGRIS_AWS_ENDPOINT_URL_S3"],
        "PLAYSIGHT_STORAGE__S3_BUCKET": env["TIGRIS_BUCKET_NAME"],
        "PLAYSIGHT_STORAGE__S3_ACCESS_KEY": env["TIGRIS_AWS_ACCESS_KEY_ID"],
        "PLAYSIGHT_STORAGE__S3_SECRET_KEY": env["TIGRIS_AWS_SECRET_ACCESS_KEY"],
        "PLAYSIGHT_STORAGE__S3_REGION": env.get("TIGRIS_AWS_REGION", "auto"),
        "PLAYSIGHT_AUTH__SECRET_KEY": env["PROD_JWT_SECRET"],
        # Placeholder until the Vercel dashboard URL exists (orchestrator patches).
        "PLAYSIGHT_CORS_ORIGINS": env.get("DASHBOARD_ORIGIN", "http://localhost:3000"),
    }


def main() -> None:
    env = load_env()
    secrets = build_secrets(env)
    pairs = [f"{k}={v}" for k, v in secrets.items()]
    for app in (API_APP, WORKER_APP):
        proc = run_fly(["secrets", "set", "--stage", "-a", app] + pairs, quiet=True)
        print(f"$ flyctl secrets set --stage -a {app} <{len(pairs)} keys>")
        if proc.returncode != 0:
            # stderr may echo values on parse errors — filter to be safe.
            safe = "\n".join(
                ln for ln in (proc.stderr or "").splitlines()
                if not any(v in ln for v in secrets.values())
            )
            print(safe, file=sys.stderr)
            raise SystemExit(f"secrets set failed for {app}")
        print(f"[ok] secrets staged on {app}")


if __name__ == "__main__":
    main()
