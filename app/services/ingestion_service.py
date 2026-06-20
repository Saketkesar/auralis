"""Image ingestion engine (Task 4.3 + 4.7).

Accepts images from any input method (file upload, drag-and-drop, pasted URL,
screenshot, camera capture), validates format by content, enforces the maximum
file size, scans for malware, stores the original bytes unmodified, and creates
one Case per image.

Requirements: 1.1-1.8, 24.1-24.4.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from app.services import malware_scan
from app.services.storage import get_storage
from app.utils.format_detection import detect_format, supported_formats_message


@dataclass(frozen=True)
class IngestionResult:
    accepted: bool
    case_id: Optional[uuid.UUID] = None
    object_key: Optional[str] = None
    content_format: Optional[str] = None
    status_code: int = 202
    message: Optional[str] = None


class IngestionService:
    """Validates, scans, stores, and registers ingested images."""

    def __init__(self, session=None, config: Optional[dict] = None, audit=None) -> None:
        self._session = session
        self._config = config or {}
        self._audit = audit
        self._max_size = int(self._config.get("MAX_FILE_SIZE", 25 * 1024 * 1024))

    def ingest_bytes(
        self,
        data: bytes,
        *,
        filename: Optional[str] = None,
        owner_id: Optional[uuid.UUID] = None,
    ) -> IngestionResult:
        # 1) size (1.7)
        if len(data) > self._max_size:
            return IngestionResult(
                accepted=False,
                status_code=413,
                message=f"File exceeds the maximum allowed size of {self._max_size} bytes.",
            )

        # 2) malware scan BEFORE processing (24.1, 24.2)
        scan = malware_scan.scan_bytes(data, self._config)
        if not scan.clean:
            self._record_audit(
                "ingest.rejected_malware",
                owner_id,
                detail={"filename": filename, "signature": scan.signature},
            )
            return IngestionResult(
                accepted=False,
                status_code=400,
                message="File rejected: malware detected.",
            )

        # 3) content-based format validation, extension-independent (1.2, 1.3, 24.3)
        fmt = detect_format(data)
        if fmt is None:
            return IngestionResult(
                accepted=False,
                status_code=415,
                message=supported_formats_message(),
            )

        # 4) create Case + store original bytes unmodified (1.4, 1.5, 24.4)
        case_id = uuid.uuid4()
        key = f"{case_id}/original"
        object_key = get_storage(self._config or None).put(key, data)

        if self._session is not None:
            from app.models.case import Case
            from app.models.enums import CaseStatus

            case = Case(
                id=case_id,
                owner_id=owner_id,
                status=CaseStatus.QUEUED,
                original_object_key=object_key,
                original_filename=filename,
                content_format=fmt.value,
            )
            self._session.add(case)
            self._session.commit()

        self._record_audit("ingest.accepted", owner_id, detail={"case_id": str(case_id)})
        return IngestionResult(
            accepted=True,
            case_id=case_id,
            object_key=object_key,
            content_format=fmt.value,
            status_code=202,
        )

    def ingest_url(self, url: str, *, owner_id: Optional[uuid.UUID] = None) -> IngestionResult:
        """Fetch a URL server-side and validate before creating a Case (1.8)."""
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
                data = resp.read(self._max_size + 1)
        except Exception as exc:  # noqa: BLE001
            return IngestionResult(
                accepted=False, status_code=400, message=f"Could not retrieve URL: {exc}"
            )
        return self.ingest_bytes(data, filename=url.rsplit("/", 1)[-1], owner_id=owner_id)

    def ingest_batch(self, items, *, owner_id: Optional[uuid.UUID] = None):
        """Create one Case per image in a batch (1.6)."""
        return [self.ingest_bytes(b, filename=n, owner_id=owner_id) for (b, n) in items]

    def _record_audit(self, action, owner_id, *, detail=None):
        if self._audit is not None:
            try:
                self._audit.record(action, actor_id=owner_id, detail=detail)
            except Exception:  # noqa: BLE001 - auditing must not block ingestion
                pass


__all__ = ["IngestionService", "IngestionResult"]
