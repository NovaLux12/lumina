import struct

import pytest

from lumina.gif import _auto_palette, write_animated_gif

BLACK = (0, 0, 0)
RED = (250, 0, 0)
GREEN = (0, 250, 0)


def _make_frame(appear_xy):
    return [[RED if (r, c) in appear_xy else GREEN for c in range(8)] for r in range(6)]


def _parse(data: bytes):
    """Parse a GIF into (w, h, gct_size, n_frames, delays, lzw_subblock_sizes)."""
    assert data[:6] == b"GIF89a"
    w, h, packed, _, _ = struct.unpack("<HHBBB", data[6:13])
    assert packed & 0x80  # global colour table present
    gct_size = 3 * (1 << ((packed & 0x07) + 1))
    pos = 13 + gct_size
    n_frames = 0
    delays = []
    max_sub = 0
    while pos < len(data):
        if data[pos] == 0x3B:  # trailer
            break
        if data[pos] == 0x21 and data[pos + 1] == 0xF9:  # GCE
            delays.append(struct.unpack("<H", data[pos + 4:pos + 6])[0])
            pos += 8
            n_frames += 1  # one GCE per frame (we always emit one)
        elif data[pos] == 0x2C:  # image descriptor
            pos += 10
            pos += 1  # skip LZW min code size
            while True:
                sub = data[pos]
                if sub == 0:
                    pos += 1
                    break
                max_sub = max(max_sub, sub)
                pos += 1 + sub
        else:
            pos += 1
    return w, h, gct_size, n_frames, delays, max_sub


def test_gif_header_lsd_and_trailer(tmp_path):
    f = [[BLACK for _ in range(4)] for _ in range(4)]
    out = tmp_path / "t.gif"
    write_animated_gif(str(out), 4, 4, [f], delays_ms=100)
    data = out.read_bytes()
    assert data[:6] == b"GIF89a"
    assert data[-1] == 0x3B
    w, h, *_ = struct.unpack("<HHBBB", data[6:13])
    assert (w, h) == (4, 4)


def test_frame_count_and_delay(tmp_path):
    frames = [_make_frame({(0, 0)}), _make_frame({(2, 3)}), _make_frame(set())]
    out = tmp_path / "t.gif"
    write_animated_gif(str(out), 8, 6, frames, delays_ms=100)
    w, h, _, n, delays, max_sub = _parse(out.read_bytes())
    assert n == 3
    assert (w, h) == (8, 6)
    assert delays == [10, 10, 10]  # 100 ms == 10 centiseconds
    assert max_sub <= 255  # LZW sub-blocks never exceed the spec limit


def test_palette_size_constraints(tmp_path):
    auto = _auto_palette([_make_frame({(0, 0)})], 256)
    assert 2 <= len(auto) <= 256
    two = [(10, 10, 10), (200, 0, 0)]
    f = [[two[0] for _ in range(3)] for _ in range(3)]
    out = tmp_path / "t.gif"
    write_animated_gif(str(out), 3, 3, [f], delays_ms=50, palette=two)
    _, _, gct, _, _, _ = _parse(out.read_bytes())
    assert gct >= 6  # at least 2 entries x 3 bytes


def test_empty_frames_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_animated_gif(str(tmp_path / "x.gif"), 4, 4, [], delays_ms=100)
