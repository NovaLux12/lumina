import math
import struct
import zlib

from lumina import gallery
from lumina.effects import list_effects


def _decode_idat(data: bytes):
    """Return (w, h, decompressed scanline bytes) or raise on corruption."""
    w, h, depth, ctype, *_ = struct.unpack(">IIBBBBB", data[16:29])
    assert depth == 8 and ctype == 2  # 8-bit RGB
    i = 8
    idat = b""
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        tag = data[i + 4:i + 8]
        if tag == b"IDAT":
            idat += data[i + 8:i + 8 + ln]
        i += 12 + ln
    raw = zlib.decompress(idat)
    expected = h * (1 + w * 3)
    assert len(raw) == expected, f"scanline mismatch: {len(raw)} != {expected}"
    return w, h, raw


def test_compose_gallery_output_is_valid_and_sized(tmp_path):
    """Regression: the gallery must produce a PNG whose scanlines match the
    declared dimensions (this previously shipped corrupt output when the grid
    width didn't equal the per-row width)."""
    out = tmp_path / "g.png"
    cols = 2
    n = gallery.compose_gallery("nova", str(out), cell_w=20, cell_h=8, cols=cols)
    assert n == len(list_effects())
    data = out.read_bytes()
    w, h, _ = _decode_idat(data)  # raises if corrupt
    assert w == 20 * cols
    assert h == 8 * 2 * math.ceil(len(list_effects()) / cols)


def test_compose_gallery_subset_order(tmp_path):
    out = tmp_path / "sub.png"
    n = gallery.compose_gallery("ice", str(out), effect_order=["plasma", "aurora"],
                                cell_w=6, cell_h=3, cols=2)
    assert n == 2
    w, h, _ = _decode_idat(out.read_bytes())
    assert w == 6 * 2
    assert h == 3 * 2 * 1  # single row
