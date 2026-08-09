"""Generative effects for lumina.

Every effect is a pure function of normalised coordinates and time:

    value(x: float, y: float, t: float) -> float   in [0, 1]

where ``x``, ``y`` are unit-normalised across the canvas and ``t`` is
the animation time in seconds. Being pure and **periodic in t** makes
each effect deterministic and easily unit-tested: the same ``(x, y, t)``
always yields the same brightness. Callers handle palettes and terminal
composition; effects only ever deal with light.
"""

from __future__ import annotations

import math
from typing import Callable

from .ansi import BLOCK_HALF, bg_rgb, fg_rgb
from .palettes import PALETTES

# --------------------------------------------------------------------------- #
# Deterministic helpers
# --------------------------------------------------------------------------- #

def _hash01(x: int, y: int, salt: int = 0) -> float:
    """A cheap, stable [0,1) hash of two integers (for pseudo-random layout)."""
    h = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h * 0.0000004656613) % 1.0


def _frac(v: float) -> float:
    return v - math.floor(v)


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


# --------------------------------------------------------------------------- #
# Effects
# --------------------------------------------------------------------------- #

def _starfield(x: float, y: float, t: float) -> float:
    """Hyperspace warp: stars stream outward from the centre along rays.

    Each ray (angle bucket) hosts a deterministic stack of stars with
    staggered phases and speeds, so the field reads as continuous motion
    rather than a repeating stipple. Brightness peaks mid-flight and
    extinguishes at the rim — the classic fly-toward-the-light look.
    """
    cx, cy = 0.5, 0.5
    dx = x - cx
    dy = y - cy
    r = math.hypot(dx, dy)
    if r < 1e-6:
        return 0.0
    ang = math.atan2(dy, dx)
    # Angle bucket for stable per-ray seeding.
    bucket = int(ang * 16.0)
    layers = 5
    best = 0.0
    for k in range(layers):
        seed = _hash01(bucket, k * 7 + 1)
        speed = 0.08 + 0.45 * _frac(seed * 997.0)
        phase = _frac(t * speed + seed)
        sr = 0.03 + 0.97 * phase  # this star's screen radius
        d = abs(r - sr)
        width = 0.018
        b = max(0.0, 1.0 - d / width)
        if b > 0.0:
            fade = math.sin(phase * math.pi)  # zero at centre and rim
            best = max(best, b * fade * fade)
    return best


def _plasma(x: float, y: float, t: float) -> float:
    """Classic interference plasma: layered drifting sine waves."""
    v = (
        math.sin(x * 5.2 + t * 1.3)
        + math.sin(y * 4.7 + t * 0.9)
        + math.sin((x + y) * 6.1 + t * 1.7)
        + math.sin(math.hypot(x - 0.5, y - 0.5) * 12.0 - t * 2.2)
    ) / 4.0
    return _clamp01(0.5 + 0.5 * v)


def _aurora(x: float, y: float, t: float) -> float:
    """Northern-lights ribbons that undulate and layer overhead."""
    bands = 4
    best = 0.0
    for i in range(bands):
        speed = 0.7 + 0.3 * i
        base = 0.18 + 0.22 * _frac(_hash01(i, 0) * 9.9 + t * 0.02)
        amp = 0.05 + 0.03 * i
        centre = base + amp * math.sin(x * (2.5 + i) + t * speed)
        falloff = math.exp(-abs(y - centre) * (14.0 - 3.0 * i))
        shimmer = 0.85 + 0.15 * math.sin(x * 40.0 + t * 3.0 * (i + 1))
        best = max(best, falloff * shimmer)
    return _clamp01(best * (1.0 - y * 0.35))  # brighter overhead


def _matrix(x: float, y: float, t: float) -> float:
    """Raining glyphs: a bright head per column with a decaying trail."""
    col = int(x / 0.02)  # ~50 columns
    speed = 0.35 + 0.65 * _hash01(col, 1)
    head = _frac(t * speed + _hash01(col, 2))
    offset = head - y  # distance below the head (>0 = trailing)
    trail = 0.16
    if offset < 0.0 or offset > trail:
        return 0.0
    tail = 1.0 - offset / trail
    flicker = _hash01(col, 3) > 0.35
    return _clamp01(tail * tail * (0.9 if flicker else 0.35))


def _fire(x: float, y: float, t: float) -> float:
    """Wall of flame: brightest at the base, turbulent upward."""
    up = 1.0 - y  # 1 at bottom, 0 at top
    turbulence = 0.5 + 0.5 * math.sin(x * 9.0 + t * 4.0 + y * 14.0)
    core = 0.5 + 0.5 * math.sin(x * 4.0 - t * 2.5)
    v = up * (0.35 + 0.65 * turbulence) * (0.7 + 0.3 * core)
    return _clamp01(v * 1.35)


def _mandala(x: float, y: float, t: float) -> float:
    """Rotating radial petals with concentric ripple rings."""
    dx = x - 0.5
    dy = y - 0.5
    r = math.hypot(dx, dy) * 2.2
    ang = math.atan2(dy, dx)
    petals = 9 + int(3 * math.sin(t * 0.4))
    # Guard against zero petal count while it oscillates.
    petals = max(petals, 3)
    spoke = math.sin(petals * (ang + t * 0.9))
    rings = math.sin(r * 16.0 - t * 1.4)
    v = 0.5 + 0.5 * (spoke * 0.6 + rings * 0.4)
    return _clamp01(v * (1.0 - r * 0.12))


# Registry — curated display order doubles as the interactive key map.
_EFFECT_ORDER: list[str] = ["starfield", "plasma", "aurora", "matrix", "fire", "mandala"]

EFFECTS: dict[str, Callable[[float, float, float], float]] = {
    "starfield": _starfield,
    "plasma": _plasma,
    "aurora": _aurora,
    "matrix": _matrix,
    "fire": _fire,
    "mandala": _mandala,
}


def list_effects() -> list[str]:
    """Effect names in curated display order."""
    return [name for name in _EFFECT_ORDER if name in EFFECTS]


ALIASES: dict[str, str] = {
    "sf": "starfield",
    "hyperspace": "starfield",
    "warp": "starfield",
    "pl": "plasma",
    "au": "aurora",
    "northern": "aurora",
    "mat": "matrix",
    "rain": "matrix",
    "fi": "fire",
    "flame": "fire",
    "ma": "mandala",
    "mandelbrot": "mandala",
}


def resolve(name: str) -> str:
    """Resolve an effect name or alias to a canonical registry key."""
    key = name.strip().lower()
    if key in EFFECTS:
        return key
    return ALIASES.get(key, "")


def render_frame(
    effect_name: str,
    palette_name: str,
    width: int,
    height: int,
    t: float,
    gamma: float = 1.0,
) -> str:
    """Compose a single ANSI frame for *effect_name* at time *t*.

    ``width`` and ``height`` are in **character cells**; each cell fakes
    two vertical sub-pixels using the upper-half block, so the rendered
    resolution is ``width`` x ``2*height``.
    """
    effect = EFFECTS.get(resolve(effect_name))
    if effect is None:
        raise ValueError(f"unknown effect: {effect_name!r}")
    palette = PALETTES.get(palette_name)
    if palette is None:
        raise ValueError(f"unknown palette: {palette_name!r}")

    lines: list[str] = []
    for row in range(height):
        buf = []
        for col in range(width):
            x = (col + 0.5) / width
            up = sample_value(palette_name, effect(x, (row * 2 + 0.5) / (height * 2), t), gamma)
            dn = sample_value(palette_name, effect(x, (row * 2 + 1.5) / (height * 2), t), gamma)
            buf.append(fg_rgb(*up) + bg_rgb(*dn) + BLOCK_HALF)
        lines.append("".join(buf))
    return "\n".join(lines)


def sample_value(palette_name: str, v: float, gamma: float = 1.0):
    """Map a brightness value onto *palette_name*, applying gamma clamping."""
    from .palettes import PALETTES, sample

    return sample(PALETTES[palette_name], _clamp01(v) ** gamma)
