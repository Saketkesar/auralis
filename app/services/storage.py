"""Object storage abstraction (MinIO/S3 with a local-filesystem fallback).

Stores original image bytes byte-for-byte in a namespace isolated from the
application execution path (Requirements 1.5, 24.4). When the ``minio`` client
and a reachable server are available it uses MinIO; otherwise it transparently
falls back to a local content store so ingestion works in development and tests
without external services.
"""
from __future__ import annotations

import io
import os
import threading
from pathlib import Path
from typing import Optional

try:  # optional dependency
    from minio import Minio  # type: ignore

    _HAS_MINIO = True
except Exception:  # pragma: no cover - minio not installed
    Minio = None  # type: ignore
    _HAS_MINIO = False


class ObjectStorage:
    """Stores and retrieves immutable objects by key."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self._config = config or {}
        self._lock = threading.Lock()
        self._client = None
        self._local_root = Path(
            self._config.get("LOCAL_STORAGE_ROOT", os.environ.get("LOCAL_STORAGE_ROOT", "/tmp/auralis-storage"))
        )
        self._bucket = self._config.get("MINIO_BUCKET", "auralis-originals")
        self._artifact_bucket = self._config.get(
            "MINIO_ARTIFACT_BUCKET", "auralis-artifacts"
        )
        if _HAS_MINIO and self._config.get("MINIO_ENDPOINT"):
            try:
                self._client = Minio(
                    self._config["MINIO_ENDPOINT"],
                    access_key=self._config.get("MINIO_ACCESS_KEY"),
                    secret_key=self._config.get("MINIO_SECRET_KEY"),
                    secure=bool(self._config.get("MINIO_SECURE", False)),
                )
            except Exception:  # pragma: no cover - degrade to local
                self._client = None

    # -- public API --------------------------------------------------------- #
    def put(self, key: str, data: bytes, *, bucket: Optional[str] = None) -> str:
        bucket = bucket or self._bucket
        if self._client is not None:
            try:
                self._ensure_bucket(bucket)
                self._client.put_object(
                    bucket, key, io.BytesIO(data), length=len(data)
                )
                return f"{bucket}/{key}"
            except Exception:
                # MinIO unreachable: fall back to local disk for this process.
                self._client = None
        # local fallback
        path = self._local_path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{bucket}/{key}"

    def put_artifact(self, key: str, data: bytes) -> str:
        return self.put(key, data, bucket=self._artifact_bucket)

    def get(self, key: str, *, bucket: Optional[str] = None) -> bytes:
        bucket = bucket or self._bucket
        if self._client is not None:
            try:
                response = self._client.get_object(bucket, key)
                try:
                    return response.read()
                finally:
                    response.close()
                    response.release_conn()
            except Exception:
                self._client = None
        return self._local_path(bucket, key).read_bytes()

    # -- helpers ------------------------------------------------------------ #
    def _ensure_bucket(self, bucket: str) -> None:
        with self._lock:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)

    def _local_path(self, bucket: str, key: str) -> Path:
        return self._local_root / bucket / key


_default_storage: Optional[ObjectStorage] = None


def get_storage(config: Optional[dict] = None) -> ObjectStorage:
    """Return a process-wide ObjectStorage, building it on first use."""
    global _default_storage
    if _default_storage is None or config is not None:
        try:
            from flask import current_app, has_app_context

            if config is None and has_app_context():
                config = dict(current_app.config)
        except Exception:
            pass
        _default_storage = ObjectStorage(config)
    return _default_storage


__all__ = ["ObjectStorage", "get_storage"]
