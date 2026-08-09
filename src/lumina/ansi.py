"""ANSI escape-sequence building.

Kept deliberately tiny and dependency-free. Everything here produces
escape sequences as plain strings so callers can compose renders
without caring about the terminal under the hood.
"""

from __future__ import annotations

__all__ = [
    "BLOCK_FULL",
    "BLOCK_HALF",
    "BLOCK_QUARTER",
    "HIDE_CURSOR",
    "RESET",
    "SHOW_CURSOR",
    "bg_rgb",
    "clear_screen",
    "fg_rgb",
    "move_to",
]

RESET = "\x1b[0m"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
# Block characters used to fake sub-character vertical resolution.
BLOCK_FULL = "\u2588"  # █
BLOCK_HALF = "\u2580"  # ▀ (upper half)
BLOCK_QUARTER = "\u2591"  # ░


def _clamp(v: int) -> int:
    return max(0, min(255, int(v)))


def fg_rgb(r: float, g: float, b: float) -> str:
    """24-bit truecolor foreground escape for the given RGB triple."""
    return f"\x1b[38;2;{_clamp(r)};{_clamp(g)};{_clamp(b)}m"


def bg_rgb(r: float, g: float, b: float) -> str:
    """24-bit truecolor background escape for the given RGB triple."""
    return f"\x1b[48;2;{_clamp(r)};{_clamp(g)};{_clamp(b)}m"


def move_to(row: int, col: int) -> str:
    """1-indexed cursor move (row;col)."""
    return f"\x1b[{row:d};{col:d}H"


def clear_screen() -> str:
    return CLEAR_SCREEN
