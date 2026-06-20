"""Shared image-loading helpers built on Pillow / NumPy / OpenCV.

Centralises decoding so engines get a consistent, defensive image handle. All
helpers degrade gracefully (return ``None``) when a library or the image itself
is unusable, so engines never crash the pipeline.
"""
from __future__ import annotations

import io
from typing import Optional

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


def has_pillow() -> bool:
    return Image is not None


def has_cv2() -> bool:
    return cv2 is not None and np is not None


def load_pil(data: bytes):
    """Return a PIL RGB image or ``None``."""
    if Image is None or not data:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None


def load_array(data: bytes):
    """Return an HxWx3 uint8 RGB ndarray or ``None``."""
    img = load_pil(data)
    if img is None or np is None:
        return None
    try:
        return np.asarray(img)
    except Exception:
        return None


def load_gray(data: bytes):
    """Return a grayscale ndarray or ``None``."""
    arr = load_array(data)
    if arr is None or cv2 is None:
        return None
    try:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    except Exception:
        return None


def to_png_bytes(arr) -> Optional[bytes]:
    """Encode an ndarray (RGB or grayscale) to PNG bytes."""
    if Image is None or arr is None:
        return None
    try:
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


__all__ = [
    "np",
    "cv2",
    "Image",
    "has_pillow",
    "has_cv2",
    "load_pil",
    "load_array",
    "load_gray",
    "to_png_bytes",
]
