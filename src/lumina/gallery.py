"""Compose every effect into a single portfolio image.

Renders each effect at a shared block resolution and tiles the results
into one PNG so a README can show the whole show at a glance. Still pure
stdlib: pixel generation here is exactly the same maths the live render
uses, called at image granularity.
"""

from __future__ import annotations

from collections.abc import Sequence

from .effects import EFFECTS, list_effects, sample_value
from .pngout import write_rgb


def _tile(
    effect: str,
    palette: str,
    cell_w: int = 40,
    cell_h: int = 12,
    t: float = 0.0,
    gamma: float = 1.0,
) -> list[list[tuple[int, int, int]]]:
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
    cell_w: int = 40,
    cell_h: int = 12,
    t: float = 0.0,
    gamma: float = 1.0,
) -> int:
    """Tile all effects (or a chosen order) into *out_path*; returns count.

    Uses the curated ``list_effects()`` order by default; pass *effect_order*
    to reorder or subset (e.g. ``["plasma", "aurora"]``).
    """
    order = list(effect_order) if effect_order else list_effects()
    # Build the big canvas row-by-row at the thumbnail pixel resolution.
    canvas: list[list[tuple[int, int, int]]] = []
    for idx, name in enumerate(order):
        tiles = _tile(name, palette, cell_w, cell_h, t, gamma)
        for r, line in enumerate(tiles):
            canvas_row = idx * cell_h * 2 + r
            while len(canvas) <= canvas_row:
                canvas.append([])
            canvas[canvas_row].extend(line)
    write_rgb(out_path, cell_w * len(order), cell_h * 2 * len(order), canvas)
    return len(order)
