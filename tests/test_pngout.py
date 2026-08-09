import struct
import zlib

from lumina import pngout


def _parse_chunks(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    chunks = []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == (zlib.crc32(tag + body) & 0xFFFFFFFF)
        chunks.append((tag, body))
        pos += 12 + length
    return chunks


def test_write_rgb_png_signature_and_ihdr(tmp_path):
    rows = [[(255, 0, 0), (0, 255, 0)], [(0, 0, 255), (255, 255, 255)]]
    p = tmp_path / "out.png"
    pngout.write_rgb(str(p), 2, 2, rows)
    assert p.exists() and p.stat().st_size > 20
    chunks = _parse_chunks(p.read_bytes())
    tags = [t for t, _ in chunks]
    assert tags == [b"IHDR", b"IDAT", b"IEND"]
    w, h, depth, ctype, *_ = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (w, h, depth, ctype) == (2, 2, 8, 2)


def test_rgba_writes_and_decompresses(tmp_path):
    rows = [[(1, 2, 3, 255), (9, 9, 9, 0)]]
    p = tmp_path / "a.png"
    pngout.write_rgba(str(p), 2, 1, rows)
    chunks = _parse_chunks(p.read_bytes())
    _, _, depth, ctype, *_ = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, ctype) == (8, 6)
    raw = zlib.decompress(chunks[1][1])
    # filter byte + 4 channels * 2 px per row
    assert len(raw) == 1 * (1 + 2 * 4)


def test_write_rgb_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    p = nested / "out.png"
    rows = [[(1, 2, 3), (4, 5, 6)], [(7, 8, 9), (10, 11, 12)]]
    pngout.write_rgb(str(p), 2, 2, rows)
    assert p.exists() and p.stat().st_size > 20
