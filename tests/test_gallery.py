import struct

from lumina import gallery
from lumina.effects import list_effects


def test_compose_gallery_dims_and_count(tmp_path):
    out = tmp_path / "g.png"
    n = gallery.compose_gallery("nova", str(out), cell_w=10, cell_h=5)
    assert n == len(list_effects())
    data = out.read_bytes()
    w, h, *_ = struct.unpack(">IIBBBBB", data[16:29])
    assert w == 10 * len(list_effects())
    assert h == 5 * 2 * len(list_effects())


def test_compose_gallery_subset_order(tmp_path):
    out = tmp_path / "sub.png"
    n = gallery.compose_gallery("ice", str(out), effect_order=["plasma", "aurora"],
                                cell_w=6, cell_h=3)
    assert n == 2
    data = out.read_bytes()
    w, *_ = struct.unpack(">II", data[16:24])
    assert w == 6 * 2
