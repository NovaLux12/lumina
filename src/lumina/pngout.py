"""Minimal, dependency-free PNG writer.

This exists so lumina can render its own frames to real image files
(still frames for documentation, or frame sequences) using nothing but
the Python standard library. It writes 8-bit RGB(RGBA) PNGs with a
single deflate-compressed IDAT scanline stream — good enough for
screenshots and small graphics without pulling in Pillow.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Sequence

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_rgb(path: str, width: int, height: int, rows: Sequence[Sequence[tuple[int, int, int]]]) -> None:
    """Write *rows* (top-to-bottom, each a sequence of (r,g,b) tuples) to *path*."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colour type 2 (RGB)
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type: None
        for r, g, b in row:
            raw += bytes((r & 0xFF, g & 0xFF, b & 0xFF))
    payload = (
        _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(_PNG_SIG + payload)


def write_rgba(path: str, width: int, height: int, rows: Sequence[Sequence[tuple[int, int, int, int]]]) -> None:
    """Write 8-bit RGBA pixels (a = alpha) to *path*."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # colour type 6 (RGBA)
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r & 0xFF, g & 0xFF, b & 0xFF, a & 0xFF))
    payload = (
        _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(_PNG_SIG + payload)
