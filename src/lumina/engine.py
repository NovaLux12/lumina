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


def _terminal_size() -> tuple[int, int]:
    """Best-effort terminal size; falls back to defaults off a TTY."""
    try:
        w, h = shutil.get_terminal_size(fallback=(DEFAULT_WIDTH, DEFAULT_HEIGHT))
    except Exception:  # noqa: BLE001 - size is advisory; never crash on it
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
    """Render a single frame as a full ANSI string.

    With ``quiet=True`` the frame is cleanly redirectable (no screen-clear
    or cursor churn). ``quiet=False`` wraps it in cursor-off/on and a
    clear-screen, which is only appropriate for the live interactive loop.
    """
    frame = render_frame(effect, palette, width, height, t, gamma)
    if quiet:
        return frame + RESET
    return clear_screen() + HIDE_CURSOR + frame + RESET + SHOW_CURSOR


def animate_interactive(
    effect: str = DEFAULT_EFFECT,
    palette: str = DEFAULT_PALETTE,
    fps: float = DEFAULT_FPS,
    gamma: float = 1.0,
    out: str = "",
    frames: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
) -> None:
    """Run the live animation loop, honouring terminal width/height.

    Keys (when *out* is empty): ``1-6`` switch effect, ``n`` next effect,
    ``p`` toggle pause, ``+``/``-`` adjust fps, ``q``/``ESC`` quit.
    When *out* is given, render *frames* stills to files and exit. When
    neither stdin nor stdout is a TTY (piped/CI), render a bounded one-shot
    and exit rather than streaming frames forever.
    """
    names = list_effects()
    palettes = list_palettes()
    eff = fx.resolve(effect) or names[0]
    idx = names.index(eff) if eff in names else 0
    pal = palette if palette in palettes else palettes[0]

    if out:
        export_stills(out, eff, pal, fps=fps, frames=frames, gamma=gamma)
        return

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Piped / non-interactive: bounded one-shot instead of a firehose.
        w, h = _terminal_size()
        n = frames if frames else 1
        for i in range(n):
            sys.stdout.write(
                capture(eff, pal, w, h, i / max(fps, 1.0), gamma, quiet=True) + "\n"
            )
        sys.stdout.flush()
        return

    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:  # noqa: BLE001 - fall back to a bounded one-shot
        w, h = _terminal_size()
        n = frames if frames else 1
        for i in range(n):
            sys.stdout.write(
                capture(eff, pal, w, h, i / max(fps, 1.0), gamma, quiet=True) + "\n"
            )
        sys.stdout.flush()
        return

    paused = False
    start = time.time()
    next_change = (start + interval) if interval > 0 else None
    sys.stdout.write(HIDE_CURSOR)  # hide once at start — never blank the screen
    try:
        while True:
            width, height = _terminal_size()
            # Redraw every cell from the top-left in a single pass. Because we
            # overwrite all cells there's nothing to clear, so no blank flash
            # between frames (this is what made SSH look flickery).
            frame = render_frame(eff, pal, width, height,
                                 time.time() if not paused else 0.0, gamma)
            sys.stdout.write("\x1b[0;0H" + frame + RESET)
            status = (
                f"\x1b[38;2;120;120;255m  [{eff} | {pal} | {fps:.0f}fps"
                + (" | PAUSED" if paused else "")
                + "]  1-6:fx  n:next  p:pause  +/-:fps  q:quit\x1b[0m"
            )
            sys.stdout.write(status)
            sys.stdout.flush()

            keys = _pending_keys(fd)
            if keys:
                for k in keys:
                    if k in ("q", "\x1b"):
                        return
                    elif k == "p":
                        paused = not paused
                    elif k in ("+", "="):
                        fps = min(120.0, fps + 5.0)
                    elif k == "-":
                        fps = max(5.0, fps - 5.0)
                    elif k == "n":
                        idx = (idx + 1) % len(names)
                        eff = names[idx]
                    elif k in "123456":
                        nxt = int(k) - 1
                        if 0 <= nxt < len(names):
                            idx = nxt
                            eff = names[idx]

            now = time.time()
            if duration > 0 and now - start >= duration:
                return
            if next_change is not None and now >= next_change:
                idx = (idx + 1) % len(names)
                eff = names[idx]
                next_change = now + interval
            time.sleep(max(0.0, (1.0 / fps) - (now - start) % (1.0 / fps)))
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
        rows: list[list[tuple[int, int, int]]] = []
        for r in range(img_h):
            row: list[tuple[int, int, int]] = []
            for c in range(img_w):
                x = (c / scale + 0.5) / width
                y = (r / scale + 0.5) / (height * 2)
                row.append(sample_value(palette, EFFECTS[effect](x, y, t), gamma))
            rows.append(row)
        path = os.path.join(out, f"{effect}-{palette}-{i:03d}.png")
        write_rgb(path, img_w, img_h, rows)
    sys.stdout.write(f"[lumina] exported {n} PNG frame(s) ({img_w}x{img_h}) to {out}/\n")


def export_gif(
    out: str,
    effect: str,
    palette: str,
    width: int = 64,
    height: int = 20,
    frames: int = 24,
    fps: float = 12.0,
    gamma: float = 1.0,
    scale: int = 3,
) -> None:
    """Export a short animation loop as an animated GIF (stdlib only).

    Renders *frames* temporally-spaced frames of *effect* and LZW-encodes
    them with a shared gradient palette (sampled from the chosen palette), so
    the GIF stays true to the source colours. Scales by ``scale`` to turn the
    block-art resolution into crisp pixels.
    """
    from .gif import write_animated_gif
    from .palettes import PALETTES, sample

    n = frames if frames else 1
    img_w = width * scale
    img_h = height * 2 * scale
    # Shared palette: the source gradient sampled to 256 steps.
    pal = [sample(PALETTES[palette], v / 255.0) for v in range(256)]
    delays_ms = int(1000.0 / max(fps, 1.0))

    gif_frames = []
    for i in range(n):
        t = i / max(fps, 1.0)
        img = []
        for py in range(img_h):
            row = []
            for px in range(img_w):
                x = (px / scale + 0.5) / width
                y = (py / scale + 0.5) / (height * 2)
                row.append(sample_value(palette, EFFECTS[effect](x, y, t), gamma))
            img.append(row)
        gif_frames.append(img)
    write_animated_gif(out, img_w, img_h, gif_frames, delays_ms=delays_ms, palette=pal)
    sys.stdout.write(
        f"[lumina] exported {n}-frame GIF ({img_w}x{img_h}) to {out}\n"
    )
