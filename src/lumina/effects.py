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
    """Radial hyperspace warp: distinct stars streak out from a vanishing
    point at the frame centre, bright near the core and tailing toward the
    rim. Deterministic rays (stable per-star angle), so the field reads as
    coherent warp rather than scatter.
    """
    dx = x - 0.5
    dy = y - 0.5
    r = math.hypot(dx, dy)
    ang = math.atan2(dy, dx)
    n_stars = 34
    best = 0.0
    for i in range(n_stars):
        s1 = _hash01(i, 11)
        s2 = _hash01(i, 23)
        sa = s1 * 2.0 * math.pi          # star's ray angle
        speed = 0.35 + 0.65 * s2          # travel speed
        phase = _frac(t * speed + s1)     # 0 = centre, 1 = rim
        sr = 0.03 + 0.97 * phase          # screen radius of the star
        # angular proximity to this star's ray
        da = abs(ang - sa)
        da = math.pi - abs(da - math.pi)  # wrap to [0, pi]
        # radial proximity
        dr = abs(r - sr)
        w_ang = 0.022                      # thin streak wedge
        w_rad = 0.030 + 0.045 * phase      # streak widens toward rim
        # brightness: bright core that tails along its ray
        streak = math.exp(-(da / w_ang) ** 2) * math.exp(-(dr / w_rad) ** 2)
        # life curve: dim at centre, peak mid-flight, fade at rim
        life = math.sin(phase * math.pi)
        best = max(best, streak * life * life)
    return _clamp01(best * 1.6)


def _plasma(x: float, y: float, t: float) -> float:
    """Dense interference plasma. Several high-frequency sine systems
    (horizontal, vertical, diagonal, radial) sum to fine, flowing bands that
    clearly read as plasma rather than a blur. Integer t-coefficients keep it
    exactly periodic in t (period 2*pi).
    """
    f = 17.0
    h = math.sin(x * f + t * 1.0)
    vb = math.sin(y * f - t * 2.0)
    d1 = math.sin((x + y) * f * 1.15 + t * 3.0)
    d2 = math.sin((x - y) * f * 0.85 - t * 4.0)
    r = math.hypot(x - 0.5, y - 0.5)
    rp = math.sin(r * f * 1.5 - t * 5.0)
    v = (h + vb + d1 + d2 + rp) / 5.0
    v = 0.5 + 0.5 * v
    return _clamp01((v - 0.5) * 1.9 + 0.5)


def _aurora(x: float, y: float, t: float) -> float:
    """Northern-lights ribbons that undulate overhead, with soft falloff
    into a dark sky dotted with faint stars."""
    bands = 4
    best = 0.0
    for i in range(bands):
        speed = 0.7 + 0.3 * i
        base = 0.16 + 0.24 * _frac(_hash01(i, 0) * 9.9 + t * 0.02)
        amp = 0.05 + 0.035 * i
        centre = base + amp * math.sin(x * (2.5 + i) + t * speed)
        falloff = math.exp(-abs(y - centre) * (9.0 - 2.0 * i))  # soakier
        shimmer = 0.8 + 0.2 * math.sin(x * 40.0 + t * 3.0 * (i + 1))
        best = max(best, falloff * shimmer)
    ribbon = _clamp01(best * (1.0 - y * 0.28))
    # faint pinprick stars toward the top of the frame
    sx = int(x * 90.0)
    sy = int(y * 60.0)
    star = 0.0
    if y < 0.35 and _hash01(sx, sy, 7) > 0.97:
        star = 0.5 + 0.5 * math.sin(t * 3.0 + sx)
    return _clamp01(ribbon + 0.35 * star)


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
    """A clear vertical teardrop flame: wide bright base narrowing to a
    rounded glowing tip, with a hot inner core, gentle x-only flicker and
    rising embers. No y-frequency modulation, so it reads as a flame column
    rather than horizontal streaks. Integer t-coefficients keep it exactly
    periodic in t (period 2*pi).
    """
    tip = 0.08
    s = max(0.0, min(1.0, (y - tip) / (1.0 - tip)))  # 0 tip..1 base
    dx = x - 0.5
    half = 0.34 * (s ** 0.75) + 1e-6                  # silhouette half-width
    # Brightness peaks in the lower-middle, dying toward base rim and tip.
    prof = math.sin(s * math.pi) ** 0.8
    # Symmetric flame body with soft edge falloff.
    body = math.exp(-((dx / half) ** 2)) * prof
    # Hot, narrow inner core down the middle.
    inner = math.exp(-((dx / (half * 0.45 + 0.02)) ** 2)) * prof
    # Gentle flicker only along x (keeps vertical structure intact).
    flick = 0.82 + 0.18 * math.sin(x * 9.0 + t * 5.0)
    # Rising embers.
    ember = 0.15 * max(0.0, math.sin(x * 44.0 + t * 9.0 + y * 16.0)) * (1.0 - y)
    return _clamp01((body * 0.75 + inner * 0.6) * flick + ember)


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
