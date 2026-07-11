"""Config layering (yaml + env) and feature flags (CONTRACTS.md sections 3, 10)."""

from __future__ import annotations

import pytest
import yaml
from sqlalchemy.orm import Session

from playsight.config.flags import is_enabled
from playsight.config.settings import DEFAULT_FEATURES, Settings, get_settings
from playsight.db.models import Club, ClubModule
from playsight.jobs.dispatch import eager_jobs_enabled


class TestSettingsLayering:
    def test_defaults_without_yaml(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("PLAYSIGHT_CONFIG", str(tmp_path / "missing.yaml"))
        monkeypatch.delenv("PLAYSIGHT_ENV", raising=False)
        monkeypatch.delenv("PLAYSIGHT_DATABASE_URL", raising=False)
        settings = Settings(_env_file=None)
        assert settings.env == "dev"
        assert settings.database_url == "sqlite:///./playsight.db"
        assert settings.pipeline.detection_conf == 0.35
        assert settings.pipeline.frame_stride == 2
        assert settings.pipeline.max_frames is None
        assert settings.auth.access_ttl_minutes == 30
        assert settings.auth.refresh_ttl_days == 14
        assert settings.storage.backend == "local"

    def test_yaml_layer_overrides_defaults(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "pipeline": {"detection_conf": 0.5, "frame_stride": 5},
                    "features": {"playbook": True},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("PLAYSIGHT_CONFIG", str(config))
        settings = Settings(_env_file=None)
        assert settings.pipeline.detection_conf == 0.5
        assert settings.pipeline.frame_stride == 5

    def test_env_overrides_yaml(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            yaml.safe_dump({"pipeline": {"detection_conf": 0.5, "frame_stride": 5}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("PLAYSIGHT_CONFIG", str(config))
        monkeypatch.setenv("PLAYSIGHT_PIPELINE__FRAME_STRIDE", "7")
        settings = Settings(_env_file=None)
        assert settings.pipeline.frame_stride == 7  # env wins over yaml
        assert settings.pipeline.detection_conf == 0.5  # yaml still visible

    def test_feature_defaults_merged_with_overrides(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(yaml.safe_dump({"features": {"playbook": True}}), encoding="utf-8")
        monkeypatch.setenv("PLAYSIGHT_CONFIG", str(config))
        settings = Settings(_env_file=None)
        assert settings.features["playbook"] is True
        # Unmentioned keys keep their contracted defaults.
        assert settings.features["video_analytics"] is True
        assert settings.features["publishing_youtube"] is True
        assert settings.features["merchandise"] is False
        assert set(DEFAULT_FEATURES).issubset(settings.features)

    def test_session_settings_are_test_env_with_eager_jobs(self) -> None:
        settings = get_settings()
        assert settings.env == "test"
        assert settings.redis_url == ""
        assert settings.storage.backend == "local"
        assert eager_jobs_enabled(settings) is True


class TestFeatureFlags:
    def test_global_defaults(self) -> None:
        assert is_enabled("video_analytics") is True
        assert is_enabled("publishing_youtube") is True
        assert is_enabled("playbook") is False
        assert is_enabled("nutrition") is False

    def test_unknown_key_defaults_to_false(self) -> None:
        assert is_enabled("does_not_exist") is False

    def test_club_override_enables_disabled_module(self, db: Session) -> None:
        club = Club(name="Flag Club", slug="flag-club", settings_json={})
        db.add(club)
        db.flush()
        db.add(ClubModule(club_id=club.id, module_key="playbook", enabled=True))
        db.commit()
        assert is_enabled("playbook") is False  # global default unchanged
        assert is_enabled("playbook", club_id=club.id, db=db) is True

    def test_club_override_disables_enabled_module(self, db: Session) -> None:
        club = Club(name="Flag Club 2", slug="flag-club-2", settings_json={})
        db.add(club)
        db.flush()
        db.add(ClubModule(club_id=club.id, module_key="video_analytics", enabled=False))
        db.commit()
        assert is_enabled("video_analytics", club_id=club.id, db=db) is False

    def test_club_without_override_uses_global(self, db: Session) -> None:
        club = Club(name="Flag Club 3", slug="flag-club-3", settings_json={})
        db.add(club)
        db.commit()
        assert is_enabled("video_analytics", club_id=club.id, db=db) is True
        assert is_enabled("playbook", club_id=club.id, db=db) is False
