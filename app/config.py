"""Application configuration loaded from the environment and secret store.

Implements Requirement 25.5: the Platform retrieves secrets from a secrets
management mechanism rather than from source code. No secret value is ever
hard-coded as a literal in this module. Every setting (database URL, Redis,
MinIO, OpenSearch, ClamAV, JWT secret, max file size, rate limits, detection
thresholds, and result caps) is read from environment variables, with support
for the Docker/Vault file-secret convention (``<VAR>_FILE`` pointing at a file
whose contents hold the value).

Configuration is exposed as classes (``Config`` and environment-specific
subclasses). ``get_config`` selects the active class from ``APP_ENV`` and
returns a configured instance whose uppercase attributes are consumed by the
Flask application factory via ``Config.as_dict``.

Design intent:
- Development and Testing environments may synthesise ephemeral secrets at
  runtime (randomly generated, never literals) so the app boots locally and in
  CI without provisioning a secret store.
- Production refuses to start when a required secret is absent, guaranteeing no
  silent fallback to an insecure default.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Callable


class ConfigError(RuntimeError):
    """Raised when a required configuration value or secret is missing."""


# ---------------------------------------------------------------------------
# Environment / secret readers
# ---------------------------------------------------------------------------
# A sentinel distinguishing "no default supplied" from an explicit ``None``
# default, so callers can mark a value as strictly required.
_REQUIRED = object()


def _read_raw(name: str) -> str | None:
    """Return a raw setting from the environment or its file-secret pointer.

    Supports the Docker secrets / Vault convention: when ``<name>_FILE`` is set
    it points at a file (e.g. ``/run/secrets/jwt_secret``) whose trimmed
    contents are the value. The file pointer takes precedence over an inline
    environment variable so mounted secrets win over shell exports.
    """
    file_pointer = os.environ.get(f"{name}_FILE")
    if file_pointer:
        path = Path(file_pointer)
        if not path.is_file():
            raise ConfigError(
                f"{name}_FILE points to '{file_pointer}' which does not exist"
            )
        return path.read_text(encoding="utf-8").strip()
    return os.environ.get(name)


def _get(
    name: str,
    default: Any = _REQUIRED,
    *,
    cast: Callable[[str], Any] | None = None,
) -> Any:
    """Fetch a setting, optionally casting it, enforcing required values."""
    raw = _read_raw(name)
    if raw is None or raw == "":
        if default is _REQUIRED:
            raise ConfigError(
                f"Required configuration '{name}' is not set in the environment "
                f"or secret store"
            )
        return default
    if cast is None:
        return raw
    try:
        return cast(raw)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Configuration '{name}' is invalid: {exc}") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = _read_raw(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int | object = _REQUIRED) -> int:
    return _get(name, default, cast=int)


def _get_float(name: str, default: float | object = _REQUIRED) -> float:
    return _get(name, default, cast=float)


def _required_secret(name: str) -> str:
    """Read a secret that must be provided by the environment/secret store."""
    return _get(name)


def _optional_secret(name: str, *, generate: bool) -> str:
    """Read a secret, synthesising an ephemeral one when permitted.

    ``generate=True`` (development/testing) produces a cryptographically random
    value at runtime rather than embedding a literal in source. ``generate=False``
    (production) makes the secret strictly required.
    """
    raw = _read_raw(name)
    if raw:
        return raw
    if generate:
        return secrets.token_urlsafe(32)
    return _required_secret(name)


# ---------------------------------------------------------------------------
# Base configuration
# ---------------------------------------------------------------------------
class Config:
    """Base configuration read entirely from the environment / secret store.

    Subclasses set :attr:`ENV_NAME`, :attr:`DEBUG`, :attr:`TESTING`, and
    :attr:`_GENERATE_EPHEMERAL_SECRETS` to control whether missing secrets are
    fatal (production) or synthesised at runtime (development/testing).
    """

    ENV_NAME: str = "base"
    DEBUG: bool = False
    TESTING: bool = False
    # Whether secrets may be randomly generated at runtime when not supplied.
    _GENERATE_EPHEMERAL_SECRETS: bool = False

    def __init__(self) -> None:
        gen = self._GENERATE_EPHEMERAL_SECRETS

        # --- Core Flask / session ------------------------------------------
        self.SECRET_KEY: str = _optional_secret("SECRET_KEY", generate=gen)

        # --- Authentication (JWT) ------------------------------------------
        self.JWT_SECRET: str = _optional_secret("JWT_SECRET", generate=gen)
        self.JWT_ALGORITHM: str = _get("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRES_SECONDS: int = _get_int(
            "JWT_ACCESS_TOKEN_EXPIRES_SECONDS", 3600
        )

        # --- Relational store (PostgreSQL) ---------------------------------
        # Accept a full DSN or compose one from parts; the password is treated
        # as a secret (supports the ``*_FILE`` pointer convention).
        self.SQLALCHEMY_DATABASE_URI: str = self._database_uri(gen)
        self.SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

        # --- Redis / Celery ------------------------------------------------
        redis_url = _get("REDIS_URL", "redis://localhost:6379/0")
        self.REDIS_URL: str = redis_url
        self.CELERY_BROKER_URL: str = _get("CELERY_BROKER_URL", redis_url)
        self.CELERY_RESULT_BACKEND: str = _get(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
        )
        self.CELERY_TASK_DEFAULT_QUEUE: str = _get("CELERY_TASK_DEFAULT_QUEUE", "cpu")

        # --- Object storage (MinIO / S3-compatible) ------------------------
        self.MINIO_ENDPOINT: str = _get("MINIO_ENDPOINT", "localhost:9000")
        self.MINIO_ACCESS_KEY: str = _optional_secret("MINIO_ACCESS_KEY", generate=gen)
        self.MINIO_SECRET_KEY: str = _optional_secret("MINIO_SECRET_KEY", generate=gen)
        self.MINIO_SECURE: bool = _get_bool("MINIO_SECURE", False)
        self.MINIO_BUCKET: str = _get("MINIO_BUCKET", "auralis-originals")
        self.MINIO_ARTIFACT_BUCKET: str = _get(
            "MINIO_ARTIFACT_BUCKET", "auralis-artifacts"
        )

        # --- Search index (OpenSearch) -------------------------------------
        self.OPENSEARCH_HOSTS: list[str] = self._csv("OPENSEARCH_HOSTS", "localhost:9200")
        self.OPENSEARCH_USER: str = _get("OPENSEARCH_USER", "admin")
        self.OPENSEARCH_PASSWORD: str = _optional_secret(
            "OPENSEARCH_PASSWORD", generate=gen
        )
        self.OPENSEARCH_USE_SSL: bool = _get_bool("OPENSEARCH_USE_SSL", False)
        self.OPENSEARCH_INDEX: str = _get("OPENSEARCH_INDEX", "cases")

        # --- Malware scanning (ClamAV sidecar) -----------------------------
        self.CLAMAV_HOST: str = _get("CLAMAV_HOST", "localhost")
        self.CLAMAV_PORT: int = _get_int("CLAMAV_PORT", 3310)
        self.CLAMAV_TIMEOUT_SECONDS: float = _get_float("CLAMAV_TIMEOUT_SECONDS", 30.0)

        # --- Ingestion limits ----------------------------------------------
        # Maximum accepted upload size in bytes (default 25 MiB). Also wired to
        # Flask's MAX_CONTENT_LENGTH so oversize bodies are rejected at the edge.
        self.MAX_FILE_SIZE: int = _get_int("MAX_FILE_SIZE", 25 * 1024 * 1024)
        self.MAX_CONTENT_LENGTH: int = self.MAX_FILE_SIZE

        # --- Rate limiting --------------------------------------------------
        # A configured limit of zero rejects all rate-limited requests (25.4).
        self.RATELIMIT_DEFAULT: str = _get("RATELIMIT_DEFAULT", "100/minute")
        self.RATELIMIT_STORAGE_URI: str = _get("RATELIMIT_STORAGE_URI", redis_url)
        self.RATELIMIT_ENABLED: bool = _get_bool("RATELIMIT_ENABLED", True)

        # --- Detection / scoring thresholds (Confidence_Score in [0, 100]) -
        self.AI_IMAGE_ALERT_THRESHOLD: float = _get_float(
            "AI_IMAGE_ALERT_THRESHOLD", 70.0
        )
        self.DEEPFAKE_ALERT_THRESHOLD: float = _get_float(
            "DEEPFAKE_ALERT_THRESHOLD", 50.0
        )
        self.THREAT_ALERT_THRESHOLD: float = _get_float("THREAT_ALERT_THRESHOLD", 70.0)
        self.LANDMARK_MIN_CONFIDENCE: float = _get_float(
            "LANDMARK_MIN_CONFIDENCE", 40.0
        )
        self.OBJECT_MIN_CONFIDENCE: float = _get_float("OBJECT_MIN_CONFIDENCE", 40.0)

        # --- Result caps ----------------------------------------------------
        self.LANDMARK_MAX_RESULTS: int = _get_int("LANDMARK_MAX_RESULTS", 20)
        self.AI_AGENT_MAX_CANDIDATES: int = _get_int("AI_AGENT_MAX_CANDIDATES", 20)
        self.GEOINT_MAX_CANDIDATES: int = _get_int("GEOINT_MAX_CANDIDATES", 20)
        self.MAP_MAX_CANDIDATES: int = _get_int("MAP_MAX_CANDIDATES", 20)

        # --- Provider dispatch ---------------------------------------------
        self.PROVIDER_DEFAULT_TIMEOUT_SECONDS: float = _get_float(
            "PROVIDER_DEFAULT_TIMEOUT_SECONDS", 10.0
        )

    # -- helpers -------------------------------------------------------------
    def _database_uri(self, gen: bool) -> str:
        """Build the SQLAlchemy DSN from a full URL or discrete parts."""
        full = _read_raw("DATABASE_URL") or _read_raw("SQLALCHEMY_DATABASE_URI")
        if full:
            return full
        host = _get("POSTGRES_HOST", "localhost")
        port = _get_int("POSTGRES_PORT", 5432)
        db = _get("POSTGRES_DB", "auralis")
        user = _get("POSTGRES_USER", "auralis")
        password = _optional_secret("POSTGRES_PASSWORD", generate=gen)
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    @staticmethod
    def _csv(name: str, default: str) -> list[str]:
        raw = _get(name, default)
        return [item.strip() for item in raw.split(",") if item.strip()]

    def as_dict(self) -> dict[str, Any]:
        """Return uppercase configuration keys for ``Flask.config.update``."""
        return {
            key: value
            for key, value in vars(self).items()
            if key.isupper()
        }


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    _GENERATE_EPHEMERAL_SECRETS = True


class TestingConfig(Config):
    # Prevent pytest from collecting this configuration class as a test case.
    __test__ = False

    ENV_NAME = "testing"
    TESTING = True
    _GENERATE_EPHEMERAL_SECRETS = True


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    TESTING = False
    # Secrets MUST be provided by the secret store; never synthesised.
    _GENERATE_EPHEMERAL_SECRETS = False


_CONFIG_BY_NAME: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env: str | None = None) -> Config:
    """Return a configured ``Config`` instance for the active environment.

    The environment is selected from the ``env`` argument, then ``APP_ENV``,
    then ``FLASK_ENV``, defaulting to ``development``. An unknown name is a hard
    error so misconfiguration fails loudly rather than silently degrading.
    """
    name = (
        env
        or os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or "development"
    ).strip().lower()
    try:
        config_cls = _CONFIG_BY_NAME[name]
    except KeyError:
        raise ConfigError(
            f"Unknown APP_ENV '{name}'. Expected one of: "
            f"{', '.join(sorted(_CONFIG_BY_NAME))}"
        )
    return config_cls()
