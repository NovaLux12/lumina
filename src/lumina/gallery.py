"""Compose every effect into a single portfolio image.

Renders each effect at a shared block resolution and tiles the results
into one PNG so a README can show the whole show at a glance. Still pure
stdlib: pixel generation here is exactly the same maths the live render
uses, called at image granularity.

The composer lays tiles out on a grid (``cols`` columns) whose dimensions
are derived from the actual tile geometry, so the PNG scanline lengths
always match the declared image size — no malformed output.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .effects import EFFECTS, list_effects, sample_value
from .pngout import write_rgb

# A "good show" moment per effect so no tile looks empty or unreadable:
# matrix needs its heads mid-screen, plasma a busy frame, etc.
GOOD_TS: dict[str, float] = {
    "starfield": 0.35,
    "plasma": 1.25,
    "aurora": 0.50,
    "matrix": 0.45,
    "fire": 0.60,
    "mandala": 1.00,
}


def _tile(
    effect: str,
    palette: str,
    cell_w: int,
    cell_h: int,
    t: float,
    gamma: float,
) -> list[list[tuple[int, int, int]]]:
    """Render one effect as a list of (cell_h*2) rows of cell_w RGB pixels."""
    rows: list[list[tuple[int, int, int]]] = []
    for img_y in range(cell_h * 2):  # 2 sub-pixels per cell row
        row: list[tuple[int, int, int]] = []
        for img_x in range(cell_w):
            x = (img_x + 0.5) / cell_w
            y = (img_y + 0.5) / (cell_h * 2)
            row.append(sample_value(palette, EFFECTS[effect](x, y, t), gamma))
        rows.append(row)
    return rows


def compose_gallery(
    palette: str,
    out_path: str,
    effect_order: Sequence[str] | None = None,
    cell_w: int = 60,
    cell_h: int = 16,
    cols: int = 2,
    gamma: float = 1.0,
    times: Mapping[str, float] | None = None,
) -> int:
    """Tile all effects (or a chosen order) onto a grid into *out_path*.

    Returns the number of effects composed. Image size is derived from the
    actual grid geometry (``cols`` x ``ceil(n/cols)`` tiles), so the PNG
    scanlines always match the declared dimensions. Effect times default to
    ``GOOD_TS`` per effect so the composition reads well.
    """
    order = list(effect_order) if effect_order else list_effects()
    if not order:
        raise ValueError("no effects to compose")
    cols = max(1, int(cols))
    rows_n = math.ceil(len(order) / cols)
    img_w = cols * cell_w
    img_h = rows_n * cell_h * 2

    # Pre-fill the canvas with black, then blit each tile at its grid slot.
    canvas: list[list[tuple[int, int, int]]] = [
        [(0, 0, 0)] * img_w for _ in range(img_h)
    ]
    for idx, name in enumerate(order):
        t = (times.get(name) if times else None) or GOOD_TS.get(name, 0.35)
        tiles = _tile(name, palette, cell_w, cell_h, t, gamma)
        col = idx % cols
        row = idx // cols
        y0 = row * cell_h * 2
        x0 = col * cell_w
        for r, line in enumerate(tiles):
            canvas[y0 + r][x0:x0 + cell_w] = line
    write_rgb(out_path, img_w, img_h, canvas)
    return len(order)
