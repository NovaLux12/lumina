"""Rendering engine: interactive terminal loop plus frame capture/export."""

from __future__ import annotations

import shutil
import sys
import time

from . import effects as fx
from .ansi import HIDE_CURSOR, RESET, SHOW_CURSOR, clear_screen
from .effects import EFFECTS, list_effects, render_frame, sample_value
from .palettes import list_palettes

DEFAULT_EFFECT = "starfield"
DEFAULT_PALETTE = "nova"
DEFAULT_WIDTH = 96
DEFAULT_HEIGHT = 28
DEFAULT_FPS = 30


def _terminal_size() -> tuple:
    try:
        w, h = shutil.get_terminal_size(fallback=(DEFAULT_WIDTH, DEFAULT_HEIGHT))
    except Exception:  # noqa: BLE001 - non-TTY fallback must degrade gracefully
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    # Leave a couple of lines for a status bar when interactive.
    return max(16, w), max(8, h - 2)


def capture(
    effect: str = DEFAULT_EFFECT,
    palette: str = DEFAULT_PALETTE,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    t: float = 0.0,
    gamma: float = 1.0,
    quiet: bool = True,
) -> str:
    """Render a single frame as a full ANSI string (with cursor-off/reset)."""
    frame = render_frame(effect, palette, width, height, t, gamma)
    prefix = "" if quiet else (clear_screen() + HIDE_CURSOR)
    suffix = SHOW_CURSOR if not quiet else ""
    return prefix + frame + RESET + suffix


def animate_interactive(
    effect: str,
    palette: str,
    fps: float,
    gamma: float,
    out: str = "",
    frames: int | None = None,
) -> None:
    """Run the live animation loop, honouring terminal width/height.

    Keys (when *out* is empty): ``1-6`` switch effect, ``n`` next effect,
    ``p`` toggle pause, ``+``/``-`` adjust fps, ``q``/``ESC`` quit.
    When *out* is given instead, render *frames* stills to files and exit.
    """
    names = list_effects()
    palettes = list_palettes()
    idx = names.index(fx.resolve(effect)) if fx.resolve(effect) in names else 0
    pid = palettes.index(palette) if palette in palettes else 0
    eff = names[idx]
    pal = palettes[pid]

    if out:
        export_stills(out, eff, pal, fps=fps, frames=frames, gamma=gamma)
        return

    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:  # noqa: BLE001 - non-TTY fallback must degrade gracefully
        # Non-TTY fallback: no key handling, just stream frames.
        try:
            while True:
                _width, _height = _terminal_size()
                sys.stdout.write("\r" + capture(eff, pal, _width, _height, time.time(), gamma))
                sys.stdout.flush()
                time.sleep(1.0 / fps)
        except KeyboardInterrupt:
            return

    paused = False
    start = time.time()
    try:
        while True:
            width, height = _terminal_size()
            # Reset cursor each frame so output doesn't scroll.
            sys.stdout.write("\x1b[0;0H")
            sys.stdout.write(capture(eff, pal, width, height, time.time() if not paused else 0, gamma))
            status = (
                f"\x1b[38;2;120;120;255m  [{eff} | {pal} | {fps:.0f}fps"
                + (" | PAUSED" if paused else "")
                + "]  1-6:fx  n:next  p:pause  +/-:fps  q:quit\x1b[0m"
            )
            sys.stdout.write(status)
            sys.stdout.flush()

            # Drain any pending keypresses without blocking the render loop.
            keys = _pending_keys(fd)
            if keys:
                for k in keys:
                    if k == "q" or k == "\x1b":
                        return
                    elif k == "p":
                        paused = not paused
                    elif k == "+" or k == "=":
                        fps = min(120.0, fps + 5.0)
                    elif k == "-":
                        fps = max(5.0, fps - 5.0)
                    elif k == "n":
                        idx = (idx + 1) % len(names)
                        eff = names[idx]
                    elif k in "123456":
                        idx = int(k) - 1
                        if 0 <= idx < len(names):
                            eff = names[idx]

            elapsed = time.time() - start
            if fps > 0:
                time.sleep(max(0.0, (1.0 / fps) - (time.time() - start - elapsed)))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:  # noqa: BLE001,S110 - best-effort terminal restore
            pass
        sys.stdout.write(SHOW_CURSOR + "\n")


def _pending_keys(fd: int) -> list[str]:
    """Non-blocking read of any queued key bytes (fd in cbreak mode)."""
    import os
    import select

    keys: list[str] = []
    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0.0)
            if not ready:
                break
            ch = os.read(fd, 1)
            if not ch:
                break
            keys.append(ch.decode("utf-8", "replace"))
    except (OSError, ValueError):
        return keys


def export_stills(
    out: str,
    effect: str,
    palette: str,
    fps: float = 8.0,
    frames: int | None = 12,
    gamma: float = 1.0,
) -> None:
    """Export *frames* temporally-spaced ANSI stills as text files.

    Writes ``<out>/<effect>-<palette>-NNN.txt``. Solid proof-of-render
    for CI or documentation without a live terminal.
    """
    import os

    os.makedirs(out, exist_ok=True)
    n = frames if frames else 1
    for i in range(n):
        t = i / max(fps, 1.0)
        path = os.path.join(out, f"{effect}-{palette}-{i:03d}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_frame(effect, palette, 96, 28, t, gamma) + "\n")
    sys.stdout.write(f"[lumina] exported {n} frame(s) to {out}/\n")


def export_png_stills(
    out: str,
    effect: str,
    palette: str,
    width: int = 96,
    height: int = 28,
    frames: int | None = 6,
    fps: float = 8.0,
    gamma: float = 1.0,
    scale: int = 2,
) -> None:
    """Export frames as real PNG images (stdlib only).

    Each character cell becomes ``scale`` image columns and ``2*scale``
    rows, surfacing the full fake-sub-pixel resolution. Solid, dependency-
    free proof-of-render for documentation and README previews.
    """
    import os

    from .pngout import write_rgb

    os.makedirs(out, exist_ok=True)
    n = frames if frames else 1
    img_w = width * scale
    img_h = height * 2 * scale
    for i in range(n):
        t = i / max(fps, 1.0)
        rows: list[list[tuple]] = []
        for r in range(img_h):
            row: list[tuple] = []
            for c in range(img_w):
                x = (c / scale + 0.5) / width
                y = (r / scale + 0.5) / (height * 2)
                row.append(sample_value(palette, EFFECTS[effect](x, y, t), gamma))
            rows.append(row)
        path = os.path.join(out, f"{effect}-{palette}-{i:03d}.png")
        write_rgb(path, img_w, img_h, rows)
    sys.stdout.write(f"[lumina] exported {n} PNG frame(s) ({img_w}x{img_h}) to {out}/\n")
