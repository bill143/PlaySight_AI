"""Application settings loaded from environment variables and config/settings.yaml.

Settings are resolved with the following precedence (highest wins):
1. Environment variables / `.env` file
2. Values in `config/settings.yaml`
3. Field defaults declared below
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_YAML_PATH = BASE_DIR / "config" / "settings.yaml"


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML config file into a flat dict of upper-cased keys.

    Missing files return an empty dict so the app can still boot with
    environment-variable-only configuration (e.g. in containers).
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    flat: dict[str, Any] = {}

    def _flatten(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, val in value.items():
                _flatten(f"{prefix}{key}_" if prefix else f"{key}_", val)
        else:
            flat[prefix.rstrip("_").upper()] = value

    _flatten("", raw)
    return flat


class Settings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    APP_NAME: str = "PlaySight AI"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "insecure-dev-secret-change-me"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://playsight_user@localhost:5432/playsight"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Storage (S3 / MinIO)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "playsight"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # JWT Auth
    JWT_SECRET_KEY: str = "insecure-dev-jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # YouTube integration
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/publish/youtube/callback"

    # Feature flags (Phase 1 core + Phase 2/3 scaffolding)
    ENABLE_YOUTUBE_UPLOAD: bool = True
    ENABLE_COMPETITION_DATA: bool = False
    ENABLE_MERCHANDISE: bool = False
    ENABLE_PLAYBOOK: bool = False
    ENABLE_TRAINING: bool = False
    ENABLE_NUTRITION: bool = False
    ENABLE_REGISTRATION: bool = False

    # ML / Pipeline
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.35
    TRACKER_MAX_AGE: int = 30
    OUTPUT_DIR: str = "data/outputs"

    # CORS
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):  # type: ignore[no-untyped-def]
        """Insert the YAML file as a lower-priority source than env vars."""

        def yaml_settings_source() -> dict[str, Any]:
            return _load_yaml_config(CONFIG_YAML_PATH)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_settings_source,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()

# Allow overriding the environment lookup dir in tests.
if os.environ.get("PLAYSIGHT_TESTING") == "1":
    settings.ENVIRONMENT = "test"
