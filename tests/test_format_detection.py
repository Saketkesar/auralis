"""Unit tests for content-based image format detection (Task 4.1).

These verify that ``detect_format`` classifies each ``Supported_Format`` from
its content, that classification is independent of any filename/extension
(Requirement 24.3), and that unsupported content is rejected with a message
naming the supported formats (Requirement 1.3).
"""
from __future__ import annotations

import pytest

from app.utils.format_detection import (
    SUPPORTED_FORMATS_LABEL,
    ImageFormat,
    detect_format,
    is_supported_format,
    supported_formats_message,
)


# --- Minimal but realistic byte signatures for each supported format. --------

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 16
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 16
WEBP_BYTES = b"RIFF" + (1024).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 16
TIFF_LE_BYTES = b"II\x2a\x00" + (8).to_bytes(4, "little") + b"\x00" * 16
TIFF_BE_BYTES = b"MM\x00\x2a" + (8).to_bytes(4, "big") + b"\x00" * 16
BMP_BYTES = b"BM" + (1024).to_bytes(4, "little") + b"\x00" * 16


def _heic_bytes(major: bytes = b"heic", *, compatible: bytes = b"") -> bytes:
    """Build a minimal ISO-BMFF ``ftyp`` box with the given brands."""
    body = b"ftyp" + major + (0).to_bytes(4, "big") + compatible
    box = (len(body) + 4).to_bytes(4, "big") + body
    return box + b"\x00" * 16


HEIC_BYTES = _heic_bytes(b"heic")


SUPPORTED_SAMPLES = {
    ImageFormat.JPEG: JPEG_BYTES,
    ImageFormat.PNG: PNG_BYTES,
    ImageFormat.WEBP: WEBP_BYTES,
    ImageFormat.TIFF: TIFF_LE_BYTES,
    ImageFormat.BMP: BMP_BYTES,
    ImageFormat.HEIC: HEIC_BYTES,
}


@pytest.mark.parametrize(
    "expected,data",
    list(SUPPORTED_SAMPLES.items()),
    ids=[fmt.value for fmt in SUPPORTED_SAMPLES],
)
def test_detects_each_supported_format(expected: ImageFormat, data: bytes):
    assert detect_format(data) is expected
    assert is_supported_format(data) is True


def test_tiff_big_endian_is_detected():
    assert detect_format(TIFF_BE_BYTES) is ImageFormat.TIFF


def test_jpg_and_jpeg_collapse_to_single_canonical_member():
    # JPG and JPEG are identical content; both classify as JPEG.
    assert detect_format(JPEG_BYTES) is ImageFormat.JPEG


@pytest.mark.parametrize(
    "major",
    [b"heic", b"heix", b"heim", b"heis", b"mif1", b"msf1", b"heif"],
)
def test_detects_heic_family_major_brands(major: bytes):
    assert detect_format(_heic_bytes(major)) is ImageFormat.HEIC


def test_detects_heic_via_compatible_brand():
    # Major brand unknown, but a compatible brand marks it as HEIF.
    data = _heic_bytes(b"mp42", compatible=b"heic")
    assert detect_format(data) is ImageFormat.HEIC


# --- Extension independence (Requirement 24.3). ------------------------------


def test_detection_ignores_misleading_extension_png_named_jpg():
    """PNG content keeps its true format regardless of a .jpg-style name."""
    # The detector only sees bytes; a filename never enters the decision.
    assert detect_format(PNG_BYTES) is ImageFormat.PNG


def test_detection_ignores_extension_for_all_formats():
    # Whatever extension a caller might have attached, content wins.
    for expected, data in SUPPORTED_SAMPLES.items():
        assert detect_format(data) is expected


def test_supported_content_with_no_extension_is_accepted():
    assert is_supported_format(JPEG_BYTES) is True


# --- Rejection of unsupported content (Requirement 1.3). ---------------------


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image at all",
        b"GIF89a" + b"\x00" * 16,  # GIF is not a Supported_Format
        b"%PDF-1.7\n" + b"\x00" * 16,  # PDF
        b"PK\x03\x04" + b"\x00" * 16,  # ZIP archive
        b"\x7fELF" + b"\x00" * 16,  # ELF executable
        b"MZ" + b"\x00" * 16,  # DOS/PE executable
        b"RIFF" + (1024).to_bytes(4, "little") + b"AVI " + b"\x00" * 16,  # RIFF but not WEBP
        b"\xff\xd8\x00",  # JPEG SOI but missing third marker byte
    ],
)
def test_rejects_unsupported_content(data: bytes):
    assert detect_format(data) is None
    assert is_supported_format(data) is False


def test_non_bytes_input_is_rejected_without_raising():
    for value in (None, 123, "string", ["not", "bytes"]):
        assert detect_format(value) is None
        assert is_supported_format(value) is False


def test_accepts_bytearray_and_memoryview():
    assert detect_format(bytearray(PNG_BYTES)) is ImageFormat.PNG
    assert detect_format(memoryview(JPEG_BYTES)) is ImageFormat.JPEG


def test_message_names_supported_formats():
    message = supported_formats_message()
    assert SUPPORTED_FORMATS_LABEL in message
    for token in ("JPG", "JPEG", "PNG", "WEBP", "TIFF", "BMP", "HEIC"):
        assert token in message
