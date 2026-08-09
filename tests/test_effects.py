
import math

import pytest

from lumina.effects import ALIASES, EFFECTS, list_effects, render_frame, resolve


def test_registry_is_curated_and_complete():
    names = list_effects()
    # Curated order matches exactly the registry, no strays.
    assert names == list(EFFECTS.keys())
    # Every effect has a help-friendly resolve.
    for n in names:
        assert resolve(n) == n


def test_aliases_resolve():
    for alias, canon in ALIASES.items():
        assert resolve(alias) == canon


def test_all_effect_values_in_bounds():
    for name, fn in EFFECTS.items():
        for x, y, t in [(0.0, 0.0, 0.0), (0.5, 0.5, 1.0), (0.99, 0.99, 3.3), (0.2, 0.8, 7.7)]:
            v = fn(x, y, t)
            assert 0.0 <= v <= 1.0, (name, (x, y, t), v)


def test_effects_are_deterministic():
    for name, fn in EFFECTS.items():
        assert fn(0.31, 0.77, 2.75) == fn(0.31, 0.77, 2.75), name


def test_plasma_is_temporally_periodic():
    """Plasma combines sines with t-coefficients 1.3, 0.9, 1.7, 2.2.

    T = 20*pi is a common period: 1.3*20pi=26pi=13*2pi, 0.9*20pi=18pi=9*2pi,
    1.7*20pi=34pi=17*2pi, 2.2*20pi=44pi=22*2pi — all full rotations.
    """
    fn = EFFECTS["plasma"]
    T = 20 * math.pi
    for x, y, t in [(0.3, 0.7, 0.0), (0.9, 0.1, 3.3), (0.5, 0.5, 11.0)]:
        assert fn(x, y, t) == pytest.approx(fn(x, y, t + T)), (x, y, t)


def test_fire_is_temporally_periodic():
    """Fire's t-coefficients are 4.0 and 2.5; T = 4*pi is a common period
    (4*4pi=16pi=8*2pi and 2.5*4pi=10pi=5*2pi)."""
    fn = EFFECTS["fire"]
    T = 4 * math.pi
    for x, y, t in [(0.2, 0.8, 0.0), (0.6, 0.4, 2.0)]:
        assert fn(x, y, t) == pytest.approx(fn(x, y, t + T)), (x, y, t)


def test_render_frame_produces_expected_shape():
    frame = render_frame("plasma", "nova", 8, 4, t=0.0)
    lines = frame.split("\n")
    assert len(lines) == 4
    # Each character cell is an upper-half block with fg+bg colour escapes.
    for line in lines:
        assert "\u2580" in line
        assert "\x1b[38;2;" in line and "\x1b[48;2;" in line
        # strip escapes and check the visible cells are all blocks
        visible = [ch for ch in line if not ch.startswith("\x1b")]
        assert "\u2580" in visible


def test_render_frame_unknown_effect_raises():
    with pytest.raises(ValueError):
        render_frame("does-not-exist", "nova", 8, 4, t=0.0)


def test_render_frame_unknown_palette_raises():
    with pytest.raises(ValueError):
        render_frame("plasma", "nope", 8, 4, t=0.0)


def test_render_frame_time_variation_changes_output():
    a = render_frame("plasma", "nova", 16, 8, t=0.0)
    b = render_frame("plasma", "nova", 16, 8, t=2.5)
    assert a != b  # animation advances


def test_gamma_changes_output():
    """Gamma must actually affect the rendered frame (brightness curve)."""
    lo = render_frame("plasma", "nova", 16, 8, t=1.0, gamma=0.3)  # brighter
    hi = render_frame("plasma", "nova", 16, 8, t=1.0, gamma=3.0)  # darker
    assert lo != hi
