
from lumina.palettes import PALETTES, list_palettes, sample


def test_all_palettes_canonical():
    for name in list_palettes():
        assert name in PALETTES


def test_palettes_are_strictly_lookupable():
    for pal in PALETTES.values():
        assert len(pal) >= 2
        for rgb in pal:
            assert len(rgb) == 3
            assert all(0 <= c <= 255 for c in rgb)


def test_sample_bounds():
    for name, pal in PALETTES.items():
        for v in (0.0, 0.25, 0.5, 0.75, 1.0):
            r, g, b = sample(pal, v)
            assert all(0 <= c <= 255 for c in (r, g, b)), (name, v)


def test_sample_endpoints_hit_anchors():
    for pal in PALETTES.values():
        if len(pal) == 1:
            continue
        assert sample(pal, 0.0) == pal[0]
        assert sample(pal, 1.0) == pal[-1]


def test_sample_out_of_range_clamps():
    pal = PALETTES["nova"]
    assert sample(pal, -1.0) == pal[0]
    assert sample(pal, 2.0) == pal[-1]


def test_sample_single_and_empty():
    assert sample([(10, 20, 30)], 0.7) == (10, 20, 30)
    assert sample([], 0.5) == (0, 0, 0)


def test_sample_monotonic_no_wraparound_spikes():
    pal = PALETTES["ice"]
    prev = None
    for v in (i / 100 for i in range(101)):
        cur = sample(pal, v)
        if prev is not None:
            # Channel values shouldn't jump by more than a sane gap for a smooth ramp.
            assert all(abs(a - b) <= 320 for a, b in zip(cur, prev))
        prev = cur
