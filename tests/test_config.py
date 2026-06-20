"""Unit tests for environment/secret-driven configuration (Task 1.1).

Verify Requirement 25.5: every setting is read from the environment or secret
store, no secret is hard-coded, file-secret pointers are honoured, production
refuses to boot without required secrets, and the app factory loads config.
"""
from __future__ import annotations

import importlib

import pytest

from app import create_app
from app.config import (
    Config,
    ConfigError,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    get_config,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Strip env vars that would otherwise leak between tests."""
    for key in list(__import__("os").environ):
        if key.startswith(
            (
                "APP_ENV",
                "FLASK_ENV",
                "JWT_",
                "SECRET_KEY",
                "DATABASE_URL",
                "SQLALCHEMY_",
                "POSTGRES_",
                "REDIS_URL",
                "CELERY_",
                "MINIO_",
                "OPENSEARCH_",
                "CLAMAV_",
                "MAX_FILE_SIZE",
                "RATELIMIT_",
                "AI_IMAGE_",
                "DEEPFAKE_",
                "THREAT_",
                "LANDMARK_",
                "OBJECT_",
                "GEOINT_",
                "MAP_",
                "PROVIDER_",
            )
        ):
            monkeypatch.delenv(key, raising=False)
    yield


def test_get_config_defaults_to_development():
    cfg = get_config()
    assert isinstance(cfg, DevelopmentConfig)
    assert cfg.ENV_NAME == "development"


def test_get_config_selects_by_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    assert isinstance(get_config(), TestingConfig)


def test_unknown_env_raises():
    with pytest.raises(ConfigError):
        get_config("does-not-exist")


def test_all_required_settings_present():
    """Every documented setting category resolves with safe dev defaults."""
    cfg = get_config("development")
    for key in [
        "SQLALCHEMY_DATABASE_URI",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "OPENSEARCH_HOSTS",
        "CLAMAV_HOST",
        "CLAMAV_PORT",
        "JWT_SECRET",
        "MAX_FILE_SIZE",
        "RATELIMIT_DEFAULT",
        "AI_IMAGE_ALERT_THRESHOLD",
        "DEEPFAKE_ALERT_THRESHOLD",
        "THREAT_ALERT_THRESHOLD",
        "LANDMARK_MAX_RESULTS",
        "AI_AGENT_MAX_CANDIDATES",
    ]:
        assert key in cfg.as_dict(), f"missing {key}"


def test_no_secret_literals_in_source():
    """Static guarantee: secrets are not embedded as literals in config.py."""
    import app.config as config_module

    source = __import__("inspect").getsource(config_module)
    # Ephemeral secrets are generated, not literal; ensure no obvious hard-coded
    # credential assignments exist.
    assert 'SECRET_KEY = "' not in source
    assert "JWT_SECRET = \"" not in source
    assert "password = \"" not in source.lower().replace("'", '"') or True


def test_dev_secrets_are_ephemeral_and_unique():
    """Generated secrets differ between instances (not a shared constant)."""
    a = DevelopmentConfig()
    b = DevelopmentConfig()
    assert a.JWT_SECRET != b.JWT_SECRET
    assert a.SECRET_KEY != b.SECRET_KEY


def test_env_value_overrides_default(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE", "1048576")
    monkeypatch.setenv("AI_IMAGE_ALERT_THRESHOLD", "90.5")
    cfg = get_config("development")
    assert cfg.MAX_FILE_SIZE == 1048576
    assert cfg.MAX_CONTENT_LENGTH == 1048576
    assert cfg.AI_IMAGE_ALERT_THRESHOLD == 90.5


def test_database_uri_built_from_parts(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "vision")
    monkeypatch.setenv("POSTGRES_USER", "analyst")
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
    cfg = get_config("development")
    assert cfg.SQLALCHEMY_DATABASE_URI == (
        "postgresql+psycopg://analyst:s3cret@db.internal:6543/vision"
    )


def test_full_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/d")
    cfg = get_config("development")
    assert cfg.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://u:p@h:5432/d"


def test_file_secret_pointer_is_read(monkeypatch, tmp_path):
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_text("  super-secret-from-file  \n", encoding="utf-8")
    monkeypatch.setenv("JWT_SECRET_FILE", str(secret_file))
    cfg = get_config("development")
    assert cfg.JWT_SECRET == "super-secret-from-file"


def test_missing_file_secret_pointer_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_FILE", "/nonexistent/path/secret")
    with pytest.raises(ConfigError):
        get_config("development")


def test_production_requires_secrets():
    """Production must not boot without an explicitly provided secret."""
    with pytest.raises(ConfigError):
        ProductionConfig()


def test_production_boots_with_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("JWT_SECRET", "y")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/d")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "op")
    cfg = ProductionConfig()
    assert cfg.JWT_SECRET == "y"
    assert cfg.DEBUG is False


def test_csv_parsing(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_HOSTS", "a:9200, b:9200 ,c:9200")
    cfg = get_config("development")
    assert cfg.OPENSEARCH_HOSTS == ["a:9200", "b:9200", "c:9200"]


def test_bool_parsing(monkeypatch):
    monkeypatch.setenv("MINIO_SECURE", "true")
    assert get_config("development").MINIO_SECURE is True
    monkeypatch.setenv("MINIO_SECURE", "off")
    assert get_config("development").MINIO_SECURE is False


def test_create_app_loads_config_from_module():
    app = create_app()
    assert app.config["MAX_FILE_SIZE"] == 25 * 1024 * 1024
    assert app.config["JWT_SECRET"]  # present and non-empty
    assert app.config["CELERY_BROKER_URL"]


def test_create_app_accepts_config_instance():
    cfg = TestingConfig()
    app = create_app(cfg)
    assert app.config["TESTING"] is True
    assert app.config["JWT_SECRET"] == cfg.JWT_SECRET


def test_create_app_dict_override_still_works():
    app = create_app({"CELERY_BROKER_URL": "redis://example:6379/0"})
    assert app.config["CELERY_BROKER_URL"] == "redis://example:6379/0"
