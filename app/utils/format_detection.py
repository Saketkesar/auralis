"""Content-based image format detection.

The Ingestion_Engine must decide whether a submission is a ``Supported_Format``
(JPG/JPEG, PNG, WEBP, TIFF, BMP, HEIC) by inspecting the *content* of the bytes
— never the file extension or a client-supplied MIME type (Requirements 1.2,
1.3, and the security control 24.3). A ``.png`` extension on a renamed
executable, or a ``.jpg`` extension on a real HEIC, must both be classified by
what the bytes actually are.

This module is the single implementation behind that control. It identifies the
format from each format's well-known file signature ("magic bytes"):

============  ==========================================================
Format        Signature
============  ==========================================================
JPEG          starts with ``FF D8 FF``
PNG           ``89 50 4E 47 0D 0A 1A 0A``
WEBP          ``RIFF`` .... ``WEBP`` (RIFF container with a WEBP form type)
TIFF          ``II 2A 00`` (little-endian) or ``MM 00 2A`` (big-endian)
BMP           ``42 4D`` (``BM``)
HEIC          ISO-BMFF ``ftyp`` box whose brand is in the HEIC/HEIF family
============  ==========================================================

The functions are pure and take ``bytes``/``bytes``-like input, so they are
independent of how the bytes arrived (upload, drag-and-drop, pasted URL fetch,
screenshot, or camera capture) and of any filename. Detection never raises on
malformed input; unrecognized content simply yields ``None`` so the caller can
reject it (Requirement 1.3).
"""
from __future__ import annotations

from enum import Enum

__all__ = [
    "ImageFormat",
    "SUPPORTED_FORMATS_LABEL",
    "detect_format",
    "is_supported_format",
    "supported_formats_message",
]


class ImageFormat(str, Enum):
    """A detected ``Supported_Format``.

    JPG and JPEG are the same byte content, so both collapse to the single
    canonical member :attr:`JPEG`. The remaining members map one-to-one to the
    formats named in the requirements glossary.
    """

    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"
    TIFF = "TIFF"
    BMP = "BMP"
    HEIC = "HEIC"


# Human-readable list of accepted formats, surfaced in the rejection message a
# caller returns when content is not a Supported_Format (Requirement 1.3).
SUPPORTED_FORMATS_LABEL: str = "JPG/JPEG, PNG, WEBP, TIFF, BMP, HEIC"

# ISO-BMFF (the HEIC/HEIF container) ``ftyp`` brands that identify a still image
# we accept as HEIC. iOS cameras commonly emit ``heic``/``heix`` major brands
# and the generic ``mif1``/``msf1`` HEIF brands.
_HEIF_BRANDS: frozenset[bytes] = frozenset(
    {
        b"heic",
        b"heix",
        b"heim",
        b"heis",
        b"hevc",
        b"hevx",
        b"heif",
        b"mif1",
        b"msf1",
    }
)


def detect_format(data: object) -> ImageFormat | None:
    """Identify the image format of ``data`` from its content.

    Args:
        data: The raw image bytes. ``bytes``, ``bytearray``, or ``memoryview``
            are accepted; any other type yields ``None`` rather than raising so
            callers can treat "unrecognized" and "wrong type" uniformly.

    Returns:
        The matching :class:`ImageFormat`, or ``None`` when the content does not
        match any ``Supported_Format``. The result depends only on the bytes,
        never on a filename or extension.
    """
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes):
        return None

    # Order is chosen so that container formats (WEBP within RIFF) are checked
    # before their generic prefixes could be mistaken for something else.
    if _is_jpeg(data):
        return ImageFormat.JPEG
    if _is_png(data):
        return ImageFormat.PNG
    if _is_webp(data):
        return ImageFormat.WEBP
    if _is_tiff(data):
        return ImageFormat.TIFF
    if _is_bmp(data):
        return ImageFormat.BMP
    if _is_heif(data):
        return ImageFormat.HEIC
    return None


def is_supported_format(data: object) -> bool:
    """Return ``True`` when ``data`` is a ``Supported_Format`` by content."""
    return detect_format(data) is not None


def supported_formats_message() -> str:
    """Return the rejection message naming the supported formats (1.3)."""
    return f"Unsupported image format. Supported formats are: {SUPPORTED_FORMATS_LABEL}."


def _is_jpeg(data: bytes) -> bool:
    # Every JPEG starts with the SOI marker FF D8 followed by another FF marker.
    return data[:3] == b"\xff\xd8\xff"


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_webp(data: bytes) -> bool:
    # RIFF container whose form type is WEBP: "RIFF" <4-byte size> "WEBP".
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _is_tiff(data: bytes) -> bool:
    # Little-endian (Intel) or big-endian (Motorola) TIFF header.
    return data[:4] in (b"II\x2a\x00", b"MM\x00\x2a")


def _is_bmp(data: bytes) -> bool:
    return data[:2] == b"BM"


def _is_heif(data: bytes) -> bool:
    """Detect a HEIC/HEIF still image by parsing the leading ``ftyp`` box.

    An ISO-BMFF file begins with a box: a 4-byte big-endian size, a 4-byte type
    (``ftyp`` for the file-type box), a 4-byte major brand, a 4-byte minor
    version, then zero or more 4-byte compatible brands. We accept the file when
    the major brand or any compatible brand is in the HEIC/HEIF family.
    """
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False

    box_size = int.from_bytes(data[0:4], "big")
    # A zero/oversized box size means "to end of file"; clamp to what we have so
    # we still scan the brands that are present.
    if box_size <= 0 or box_size > len(data):
        box_size = len(data)

    major_brand = data[8:12]
    if major_brand in _HEIF_BRANDS:
        return True

    # Compatible brands begin after the major brand (8) and minor version (4).
    for offset in range(16, box_size - 3, 4):
        if data[offset : offset + 4] in _HEIF_BRANDS:
            return True
    return False
