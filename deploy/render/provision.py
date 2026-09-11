"""Provision PlaySight production infrastructure on Render (Phase 2).

Creates, in region oregon (idempotent — skips anything already recorded in
state.json or found by name):
  1. Postgres  playsight-db     (basic_256mb)
  2. Key Value playsight-kv     (free; noeviction requested, fallback logged)
  3. Private   playsight-minio  (image minio/minio, 10 GB disk at /data)
  4. Web       playsight-api    (repo docker, Dockerfile.api, starter)
  5. Worker    playsight-worker (repo docker, Dockerfile.worker, standard)

Secret values (connection strings, generated credentials) never go to stdout.
Non-secret ids/urls are written to state.json.
"""

from __future__ import annotations

import secrets as pysecrets
import sys

from render_api import (
    BRANCH,
    REGION,
    REPO_URL,
    api,
    append_secret,
    load_env,
    load_state,
    owner_id,
    save_state,
    session,
)

MINIO_PORT = 9000
S3_BUCKET = "playsight"


def ensure_generated_secrets() -> dict[str, str]:
    append_secret("MINIO_ROOT_USER", "playsight-root")
    append_secret("MINIO_ROOT_PASSWORD", pysecrets.token_urlsafe(32))
    append_secret("PROD_JWT_SECRET", pysecrets.token_hex(32))
    env = load_env()
    return {
        "MINIO_ROOT_USER": env["MINIO_ROOT_USER"],
        "MINIO_ROOT_PASSWORD": env["MINIO_ROOT_PASSWORD"],
        "PROD_JWT_SECRET": env["PROD_JWT_SECRET"],
    }


def ensure_postgres(ses, state) -> str:
    if state.get("postgres_id"):
        return state["postgres_id"]
    body = {
        "name": "playsight-db",
        "ownerId": owner_id(),
        "plan": "basic_256mb",
        "region": REGION,
        "version": "16",
        "databaseName": "playsight",
        "databaseUser": "playsight",
    }
    detail = api(ses, "POST", "/postgres", body)
    pg = detail.get("postgresDetail") or detail
    state["postgres_id"] = pg["id"]
    save_state(state)
    print(f"postgres created: {pg['id']}")
    return pg["id"]


def ensure_keyvalue(ses, state) -> str:
    if state.get("keyvalue_id"):
        return state["keyvalue_id"]
    body = {
        "name": "playsight-kv",
        "ownerId": owner_id(),
        "plan": "free",
        "region": REGION,
        "maxmemoryPolicy": "noeviction",
    }
    try:
        detail = api(ses, "POST", "/key-value", body)
    except RuntimeError as exc:
        print(f"key-value with noeviction rejected ({exc}); retrying without")
        body.pop("maxmemoryPolicy")
        detail = api(ses, "POST", "/key-value", body)
        state["keyvalue_eviction_risk"] = True
    kv = detail.get("keyValueDetail") or detail
    state["keyvalue_id"] = kv["id"]
    state["keyvalue_policy"] = (kv.get("options") or {}).get(
        "maxmemoryPolicy", "unknown"
    )
    save_state(state)
    print(f"key-value created: {kv['id']} policy={state['keyvalue_policy']}")
    return kv["id"]


def get_pg_internal_url(ses, pg_id: str) -> str:
    info = api(ses, "GET", f"/postgres/{pg_id}/connection-info")
    url = info["internalConnectionString"]
    # SQLAlchemy 2 needs an explicit driver scheme.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def get_kv_internal_url(ses, kv_id: str) -> str:
    info = api(ses, "GET", f"/key-value/{kv_id}/connection-info")
    return info["internalConnectionString"]


def find_service_by_name(ses, name: str) -> str | None:
    rows = api(ses, "GET", "/services", params={"name": name, "limit": 20})
    for row in rows or []:
        svc = row.get("service") or row
        if svc.get("name") == name:
            return svc["id"]
    return None


def ensure_minio(ses, state, gen: dict[str, str]) -> str:
    if state.get("minio_id"):
        return state["minio_id"]
    existing = find_service_by_name(ses, "playsight-minio")
    if existing:
        state["minio_id"] = existing
        save_state(state)
        return existing
    body = {
        "type": "private_service",
        "name": "playsight-minio",
        "ownerId": owner_id(),
        "autoDeploy": "yes",
        "image": {
            "ownerId": owner_id(),
            "imagePath": "docker.io/minio/minio:latest",
        },
        "envVars": [
            {"key": "MINIO_ROOT_USER", "value": gen["MINIO_ROOT_USER"]},
            {"key": "MINIO_ROOT_PASSWORD", "value": gen["MINIO_ROOT_PASSWORD"]},
        ],
        "serviceDetails": {
            "runtime": "image",
            "plan": "starter",
            "region": REGION,
            "envSpecificDetails": {"dockerCommand": "minio server /data"},
            "disk": {"name": "minio-data", "mountPath": "/data", "sizeGB": 10},
        },
    }
    res = api(ses, "POST", "/services", body)
    svc = res["service"]
    state["minio_id"] = svc["id"]
    save_state(state)
    print(f"minio created: {svc['id']}")
    return svc["id"]


def app_env_vars(gen: dict[str, str], db_url: str, kv_url: str) -> list[dict]:
    return [
        {"key": "PLAYSIGHT_ENV", "value": "prod"},
        {"key": "PLAYSIGHT_DATABASE_URL", "value": db_url},
        {"key": "PLAYSIGHT_REDIS_URL", "value": kv_url},
        {"key": "PLAYSIGHT_STORAGE__BACKEND", "value": "s3"},
        {
            "key": "PLAYSIGHT_STORAGE__S3_ENDPOINT",
            "value": f"http://playsight-minio:{MINIO_PORT}",
        },
        {"key": "PLAYSIGHT_STORAGE__S3_BUCKET", "value": S3_BUCKET},
        {
            "key": "PLAYSIGHT_STORAGE__S3_ACCESS_KEY",
            "value": gen["MINIO_ROOT_USER"],
        },
        {
            "key": "PLAYSIGHT_STORAGE__S3_SECRET_KEY",
            "value": gen["MINIO_ROOT_PASSWORD"],
        },
        {"key": "PLAYSIGHT_AUTH__SECRET_KEY", "value": gen["PROD_JWT_SECRET"]},
        {"key": "PLAYSIGHT_CORS_ORIGINS", "value": "http://localhost:3000"},
    ]


def ensure_repo_service(
    ses,
    state,
    state_key: str,
    name: str,
    svc_type: str,
    dockerfile: str,
    plan: str,
    env_vars: list[dict],
    health_check: str | None = None,
) -> str:
    if state.get(state_key):
        return state[state_key]
    existing = find_service_by_name(ses, name)
    if existing:
        state[state_key] = existing
        save_state(state)
        return existing
    details: dict = {
        "runtime": "docker",
        "plan": plan,
        "region": REGION,
        "envSpecificDetails": {
            "dockerfilePath": dockerfile,
            "dockerContext": ".",
        },
    }
    if health_check:
        details["healthCheckPath"] = health_check
    body = {
        "type": svc_type,
        "name": name,
        "ownerId": owner_id(),
        "repo": REPO_URL,
        "branch": BRANCH,
        "autoDeploy": "yes",
        "envVars": env_vars,
        "serviceDetails": details,
    }
    res = api(ses, "POST", "/services", body)
    svc = res["service"]
    state[state_key] = svc["id"]
    url = (svc.get("serviceDetails") or {}).get("url")
    if url:
        state[f"{state_key}_url"] = url
    save_state(state)
    print(f"{name} created: {svc['id']} url={url}")
    return svc["id"]


def main() -> int:
    ses = session()
    state = load_state()
    gen = ensure_generated_secrets()

    pg_id = ensure_postgres(ses, state)
    kv_id = ensure_keyvalue(ses, state)
    ensure_minio(ses, state, gen)

    db_url = get_pg_internal_url(ses, pg_id)
    kv_url = get_kv_internal_url(ses, kv_id)
    env_vars = app_env_vars(gen, db_url, kv_url)

    ensure_repo_service(
        ses,
        state,
        "api_id",
        "playsight-api",
        "web_service",
        "./docker/Dockerfile.api",
        "starter",
        env_vars,
        health_check="/api/v1/health/live",
    )
    ensure_repo_service(
        ses,
        state,
        "worker_id",
        "playsight-worker",
        "background_worker",
        "./docker/Dockerfile.worker",
        "standard",
        env_vars,
    )
    print("provisioning complete")
    print({k: v for k, v in load_state().items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
