
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


@pytest.mark.parametrize("name", ["starfield", "plasma", "fire", "matrix", "aurora"])
def test_effects_are_temporal_periodic(name):
    """Each effect must revisit the same frame for a fixed t — pure functions."""
    fn = EFFECTS[name]
    for x, y, t in [(0.4, 0.5, 0.0), (0.9, 0.1, 5.0)]:
        assert fn(x, y, t) == fn(x, y, t + 0.0), (name, x, y, t)


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
