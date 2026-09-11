"""Application settings (pydantic-settings + YAML layer).

Load order (highest precedence first):

1. Explicit constructor kwargs (tests).
2. Environment variables (prefix ``PLAYSIGHT_``, nested delimiter ``__``).
3. ``.env`` file.
4. YAML config file (path from ``PLAYSIGHT_CONFIG``, default ``configs/default.yaml``).
5. Field defaults defined below.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_DEV_SECRET_KEY = "dev-only-insecure-secret-change-me"

DEFAULT_FEATURES: dict[str, bool] = {
    "video_analytics": True,
    "publishing_youtube": True,
    "competition": False,
    "merchandise": False,
    "playbook": False,
    "training": False,
    "nutrition": False,
    "registration": False,
    "payments": False,
    "commerce": False,
}


class StorageSettings(BaseModel):
    """Object storage configuration (local filesystem or S3/MinIO)."""

    backend: str = "local"  # "local" | "s3"
    local_root: str = "./outputs/storage"
    s3_endpoint: str | None = "http://localhost:9000"
    s3_bucket: str = "playsight"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"


class AuthSettings(BaseModel):
    """JWT auth configuration (HS256)."""

    secret_key: str = _DEV_SECRET_KEY
    access_ttl_minutes: int = 30
    refresh_ttl_days: int = 14
    algorithm: str = "HS256"


class PipelineSettings(BaseModel):
    """Vision pipeline tuning knobs."""

    detection_conf: float = 0.35
    frame_stride: int = 2
    max_frames: int | None = None


class YouTubeSettings(BaseModel):
    """YouTube OAuth2 (installed-app flow) file locations."""

    client_secrets_file: str = "configs/google_client_secret.json"
    token_file: str = "configs/youtube_token.json"


class _YamlConfigSource(PydanticBaseSettingsSource):
    """Settings source reading the YAML layer (``PLAYSIGHT_CONFIG``)."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data = self._load()

    @staticmethod
    def _load() -> dict[str, Any]:
        path = Path(os.environ.get("PLAYSIGHT_CONFIG", "configs/default.yaml"))
        if not path.is_file():
            return {}
        with path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        return loaded if isinstance(loaded, dict) else {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Return (value, key, is_complex) for one field from the YAML layer."""
        value = self._data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return the whole YAML mapping as a settings dict."""
        return dict(self._data)


class Settings(BaseSettings):
    """Top-level application settings (see CONTRACTS.md section 3)."""

    model_config = SettingsConfigDict(
        env_prefix="PLAYSIGHT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "dev"  # dev | test | prod
    database_url: str = "sqlite:///./playsight.db"
    redis_url: str = "redis://localhost:6379/0"

    #: Allowed CORS origins for the API (``PLAYSIGHT_CORS_ORIGINS`` accepts a
    #: comma-separated string or a list; default keeps localhost for dev).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    youtube: YouTubeSettings = Field(default_factory=YouTubeSettings)

    features: dict[str, bool] = Field(default_factory=lambda: dict(DEFAULT_FEATURES))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Accept a comma-separated string (env var) or a list (YAML/kwargs)."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        """Merge feature defaults and refuse insecure prod configuration."""
        merged = dict(DEFAULT_FEATURES)
        merged.update(self.features)
        self.features = merged
        if self.env == "prod" and self.auth.secret_key == _DEV_SECRET_KEY:
            raise ValueError(
                "auth.secret_key is the insecure dev default and env is 'prod'; "
                "set PLAYSIGHT_AUTH__SECRET_KEY to a real secret before starting."
            )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Insert the YAML layer below env/.env but above field defaults."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _YamlConfigSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance.

    Tests can call ``get_settings.cache_clear()`` after mutating the
    environment to force a reload.
    """
    return Settings()
