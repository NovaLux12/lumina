"""Named colour palettes for lumina effects.

A palette is an ordered list of RGB anchor triples. Rendering samples a
value ``v`` in ``[0, 1]`` and interpolates piecewise-linearly between
anchors, so every palette gives a smooth gradient from the first colour
to the last. Anchors are chosen so the full range reads well on dark
terminals.
"""

from __future__ import annotations

from collections.abc import Sequence

RGB = tuple[int, int, int]
Palette = Sequence[RGB]

PALETTES: dict[str, Palette] = {
    # "Nova" — deep violet-black through magenta to solar gold. The namesake.
    "nova": [
        (4, 2, 14),
        (52, 16, 96),
        (148, 40, 190),
        (255, 108, 148),
        (255, 200, 120),
        (255, 236, 180),
    ],
    # "dusk" — nightfall blues into a hot horizon.
    "dusk": [
        (6, 8, 20),
        (16, 34, 74),
        (46, 76, 148),
        (150, 120, 214),
        (255, 150, 120),
        (255, 210, 150),
    ],
    # "pine" — emerald greens with cool teal shadows (aurora favour).
    "pine": [
        (2, 20, 16),
        (6, 58, 40),
        (24, 110, 76),
        (72, 198, 130),
        (150, 235, 170),
        (210, 255, 210),
    ],
    # "ember" — black through ember orange to near-white core.
    "ember": [
        (12, 6, 4),
        (90, 22, 4),
        (200, 60, 10),
        (255, 130, 40),
        (255, 190, 90),
        (255, 248, 210),
    ],
    # "ice" — arctic cyan and white-blue.
    "ice": [
        (4, 10, 24),
        (10, 40, 70),
        (40, 120, 160),
        (120, 200, 230),
        (200, 240, 250),
        (245, 252, 255),
    ],
    # "retro" — classic CGA-ish bold primaries for the matrix/mandala moods.
    "retro": [
        (0, 0, 0),
        (18, 18, 44),
        (0, 200, 120),
        (255, 212, 90),
        (255, 90, 140),
        (215, 245, 255),
    ],
    # "sunset" — late-summer horizon: plum dusk through coral to warm cream.
    "sunset": [
        (14, 6, 22),
        (80, 22, 52),
        (190, 48, 70),
        (255, 108, 64),
        (255, 176, 110),
        (255, 232, 190),
    ],
}

# Ordered list used for tab-complete / help.
PALETTE_ORDER: list[str] = ["nova", "dusk", "sunset", "pine", "ember", "ice", "retro"]


def list_palettes() -> list[str]:
    """Return palette names in a stable, curated order."""
    return [name for name in PALETTE_ORDER if name in PALETTES]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def sample(palette: Palette, v: float) -> RGB:
    """Map ``v`` in [0,1] onto *palette*, returning an RGB triple.

    A palette with a single anchor returns that anchor for every value.
    Otherwise values are mapped across the anchor list with piecewise
    linear interpolation, and endpoints clamp out-of-range values.
    """
    if not palette:
        return (0, 0, 0)
    if len(palette) == 1:
        return palette[0]
    t = max(0.0, min(1.0, float(v)))
    scaled = t * (len(palette) - 1)
    idx = int(scaled)  # floor
    if idx >= len(palette) - 1:
        return palette[-1]
    frac = scaled - idx
    a = palette[idx]
    b = palette[idx + 1]
    return (
        round(_lerp(a[0], b[0], frac)),
        round(_lerp(a[1], b[1], frac)),
        round(_lerp(a[2], b[2], frac)),
    )
