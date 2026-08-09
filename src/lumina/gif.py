"""Minimal, dependency-free animated GIF (GIF89a) writer.

Lets lumina export its light shows as real animated GIFs using only the
Python standard library - no Pillow, no imageio. Two pieces do the work:

* LZW compression (the GIF image-data format, 3-12 bit codes).
* A small container writer: header, logical screen + global colour table,
  one graphic-control block + image descriptor per frame, then the trailer.

Frames are full-screen overwrites (no transparency), so the encoder stays
simple and robust: quantise each frame to a shared palette, LZW each index
grid, and interleave a per-frame delay.
"""

from __future__ import annotations

import math
import os
import struct


def _lzw(indices, min_code_size: int) -> bytes:
    """LZW-compress a stream of palette indices (GIF LZW variant).

    Emits a clear code, grows the code width one bit **before** registering
    the entry whose value reaches ``1 << code_size`` (the classic GIF LZW
    subtlety), and enforces the 12-bit ceiling with a table reset when it
    would overflow. Output is bit-packed LSB-first.
    """
    clear = 1 << min_code_size
    end = clear + 1
    code_size = min_code_size + 1
    table = {}
    next_code = end + 1
    out = bytearray()
    bitbuf = 0
    bitcnt = 0

    def emit(code: int) -> None:
        nonlocal bitbuf, bitcnt
        bitbuf |= code << bitcnt
        bitcnt += code_size
        while bitcnt >= 8:
            out.append(bitbuf & 0xFF)
            bitbuf >>= 8
            bitcnt -= 8

    emit(clear)
    prefix = None
    for k in indices:
        if prefix is None:
            prefix = k
            continue
        key = (prefix, k)
        if key in table:
            prefix = table[key]
        else:
            emit(prefix)
            if next_code > 4095:
                # 12-bit table full: clear and rebuild from scratch.
                emit(clear)
                table = {}
                code_size = min_code_size + 1
                next_code = end + 1
            else:
                if next_code == (1 << code_size) and code_size < 12:
                    code_size += 1
                table[key] = next_code
                next_code += 1
            prefix = k
    if prefix is not None:
        emit(prefix)
    emit(end)
    if bitcnt > 0:
        out.append(bitbuf & 0xFF)
    return bytes(out)


def write_animated_gif(
    path: str,
    width: int,
    height: int,
    frames,
    delays_ms: int = 100,
    palette=None,
) -> None:
    """Write an animated GIF from *frames* (list of row-major RGB images).

    *palette* is an optional fixed colour table (2..256 RGB entries). When
    omitted one is derived from the frames so the global table stays small
    and deterministic.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = len(frames)
    if n == 0:
        raise ValueError("no frames to encode")
    if palette is None:
        palette = _auto_palette(frames, 256)
    if len(palette) == 1:
        palette = list(palette) + [(0, 0, 0)]  # uniform frame still needs >=2
    if not 2 <= len(palette) <= 256:
        raise ValueError("palette must have 2..256 entries")

    min_code_size = max(2, math.ceil(math.log2(len(palette))))
    gct_size = 1 << min_code_size

    out = bytearray()
    out += b"GIF89a"
    out += struct.pack("<HHBBB", width, height, 0xF0 | (min_code_size - 1), 0, 0)
    table = list(palette) + [(0, 0, 0)] * (gct_size - len(palette))
    for r, g, b in table:
        out += bytes((r, g, b))

    for frame in frames:
        out += b"\x21\xf9\x04\x00" + struct.pack("<HB", max(1, delays_ms // 10), 0) + b"\x00"
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00"
        indices = []
        for row in frame:
            indices.extend(_quantise(row, palette))
        compressed = _lzw(indices, min_code_size)
        out.append(min_code_size)
        for i in range(0, len(compressed), 255):
            chunk = compressed[i:i + 255]
            out.append(len(chunk))
            out += chunk
        out.append(0x00)
    out += b"\x3b"

    with open(path, "wb") as fh:
        fh.write(bytes(out))


def _quantise(row, palette) -> list[int]:
    """Map an RGB row to palette indices by nearest RGB distance."""
    idx = []
    for r, g, b in row:
        best = 0
        best_d = 1 << 30
        for i, (pr, pg, pb) in enumerate(palette):
            d = (pr - r) * (pr - r) + (pg - g) * (pg - g) + (pb - b) * (pb - b)
            if d < best_d:
                best_d = d
                best = i
        idx.append(best)
    return idx


def _auto_palette(frames, max_colors: int) -> list[tuple[int, int, int]]:
    """Deterministic palette from the most frequent (coarsely bucketed) colours."""
    counts = {}
    for frame in frames:
        seen = set()
        for row in frame:
            for px in row:
                key = (px[0] & 0xF8, px[1] & 0xFC, px[2] & 0xF8)
                h = key[0] << 16 | key[1] << 8 | key[2]
                if h not in seen:
                    seen.add(h)
                    counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return [c for c, _ in ordered[:max_colors]] or [(0, 0, 0)]
