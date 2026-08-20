"""Command-line interface for lumina."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .effects import EFFECTS, list_effects, resolve
from .engine import (
    DEFAULT_EFFECT,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_PALETTE,
    DEFAULT_WIDTH,
    animate_interactive,
    capture,
    export_gif,
    export_png_stills,
)
from .palettes import PALETTES, list_palettes


def _install_sigpipe_dfl() -> None:
    """Die silently (conventionally) if the output pipe closes.

    With SIGPIPE back at its default disposition, a tool that closes our
    output early (``lumina --still 0.5 | head -c 200``) just terminates the
    process via SIGPIPE instead of surfacing a Python BrokenPipeError
    traceback at interpreter shutdown. This is the standard Unix-tool
    behaviour. No-op where SIGPIPE isn't defined (e.g. Windows), where the
    BrokenPipeError fallback in :func:`main` still applies.
    """
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError, OSError):
        pass


def _terminal_dimensions(args) -> tuple:
    """Return (width, height) for a still, honouring a live TTY.

    Explicit ``--width``/``--height`` win; otherwise a real terminal's size
    is used when stdout is a TTY. When output is piped (scripting), fall
    back to the deterministic defaults so ``--still`` output stays stable.
    """
    import shutil

    interactive = sys.stdout.isatty()
    cols = shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT)).columns
    lines = shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT)).lines
    width = args.width if args.width else (cols if interactive else DEFAULT_WIDTH)
    height = args.height if args.height else (lines - 2 if interactive else DEFAULT_HEIGHT)
    return max(1, width), max(1, height)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lumina",
        description="Zero-dependency terminal generative art. Animated ANSI light shows.",
        epilog=(
            "effects: " + ", ".join(list_effects())
            + "  |  palettes: " + ", ".join(list_palettes())
            + "\n"
            "keys (interactive): 1-6 switch effect · n next · p pause · +/- fps · q/ESC quit"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g_render = p.add_argument_group("rendering")
    g_render.add_argument("-e", "--effect", default=DEFAULT_EFFECT,
                   help=f"effect to render (default: {DEFAULT_EFFECT}); supports aliases like 'hyperspace'")
    g_render.add_argument("-c", "--palette", default=DEFAULT_PALETTE,
                   help=f"colour palette (default: {DEFAULT_PALETTE})")
    g_render.add_argument("--width", type=int, default=0, help="character-column width (0 = auto/terminal)")
    g_render.add_argument("--height", type=int, default=0, help="character-row height (0 = auto/terminal)")
    g_render.add_argument("--fps", type=float, default=DEFAULT_FPS, help="frames per second (default: %(default)s)")
    g_render.add_argument("--gamma", type=float, default=1.0, help="brightness gamma curve")
    g_render.add_argument("--duration", type=float, default=0.0, metavar="SECS",
                   help="auto-exit after SECS seconds in interactive/show mode (0 = run until q)")

    g_still = p.add_argument_group("still / export")
    g_still.add_argument("--still", type=float, metavar="T", default=None,
                   help="render a single frame at time T and print it, then exit")
    g_still.add_argument("--export", metavar="DIR", default="",
                   help="export temporally-spaced ANSI frames to DIR and exit")
    g_still.add_argument("--png", metavar="DIR", default="",
                   help="render real PNG frames (stdlib-only encoder) to DIR and exit")
    g_still.add_argument("--gif", metavar="OUT.GIF", default="",
                   help="export an animated GIF (stdlib-only encoder) to OUT.GIF and exit")
    g_still.add_argument("--gallery", metavar="PNG", default="",
                   help="tile all effects into one portfolio PNG and exit")
    g_still.add_argument("--cell-w", type=int, default=40, help="gallery cell width (default: 40)")
    g_still.add_argument("--cell-h", type=int, default=12, help="gallery cell height (default: 12)")
    g_still.add_argument("--frames", type=int, default=None, help="number of frames to export")
    g_still.add_argument("--scale", type=int, default=3, help="PNG/GIF upscale factor per cell (default: 3)")

    g_show = p.add_argument_group("show")
    g_show.add_argument("--show", action="store_true",
                   help="autoplay: cycle through all effects automatically (setlist mode)")
    g_show.add_argument("--interval", type=float, default=5.0,
                   help="seconds between auto-cycling effects in --show mode (default: 5)")

    g_info = p.add_argument_group("info")
    g_info.add_argument("--list-effects", action="store_true", help="list available effects")
    g_info.add_argument("--list-palettes", action="store_true", help="list available palettes")
    g_info.add_argument("--version", action="version", version=f"lumina {__version__}")
    return p


def _run(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list_effects:
        if sys.stdout.isatty():
            # Delightful TTY table; piped output stays plain for scripting/tests.
            descs = {
                "starfield": "hyperspace warp — stars streak from centre",
                "plasma": "interference plasma — rippling colour fields",
                "aurora": "northern lights — undulating ribbons",
                "matrix": "raining glyphs — bright head + trail",
                "fire": "turbulent flame — brightest at the base",
                "mandala": "rotating petals + ripple rings",
            }
            for name in list_effects():
                print(f"  {name:<12} {descs.get(name, '')}")
        else:
            print("\n".join(list_effects()))
        return 0
    if args.list_palettes:
        if sys.stdout.isatty():
            descs = {
                "nova": "violet-black → magenta → solar gold",
                "dusk": "nightfall blues → hot horizon",
                "sunset": "plum dusk → coral → warm cream",
                "pine": "emerald greens, teal shadows",
                "ember": "black → ember orange → near-white",
                "ice": "arctic cyan → white-blue",
                "retro": "bold CGA-ish primaries",
            }
            for name in list_palettes():
                print(f"  {name:<10} {descs.get(name, '')}")
        else:
            print("\n".join(list_palettes()))
        return 0

    eff = resolve(args.effect)
    if eff not in EFFECTS:
        sys.stderr.write(f"lumina: unknown effect {args.effect!r}\n")
        return 2
    if args.palette not in PALETTES:
        sys.stderr.write(f"lumina: unknown palette {args.palette!r}\n")
        return 2

    # Single still frame requested (good for scripting / CI proof).
    if args.still is not None:
        w, h = _terminal_dimensions(args)
        sys.stdout.write(capture(eff, args.palette, w, h, args.still, args.gamma, quiet=True))
        sys.stdout.write("\n")
        return 0

    w = args.width or 0
    h = args.height or 0
    if args.gif:
        export_gif(
            args.gif, eff, args.palette,
            width=args.width or 64, height=args.height or 20,
            frames=args.frames or 24, fps=args.fps, gamma=args.gamma,
            scale=args.scale,
        )
        return 0
    if args.gallery:
        return _gallery_main(args)
    if args.png:
        export_png_stills(args.png, eff, args.palette,
                          width=args.width or DEFAULT_WIDTH,
                          height=args.height or DEFAULT_HEIGHT,
                          frames=args.frames, fps=args.fps, gamma=args.gamma,
                          scale=args.scale)
        return 0
    if args.export:
        animate_interactive(eff, args.palette, args.fps, args.gamma,
                            out=args.export, frames=args.frames)
        return 0

    if sys.stdout.isatty():
        sys.stdout.write(f"\n\x1b[38;2;120;200;255m✨ lumina\x1b[0m "
                         f"[{eff} | {args.palette}]  q to quit\n")
    animate_interactive(
        eff, args.palette, args.fps, args.gamma,
        interval=args.interval if args.show else 0.0,
        duration=args.duration,
    )
    return 0


def main(argv=None) -> int:
    """Entry point.

    On POSIX, a closed output pipe terminates the process conventionally via
    SIGPIPE (silent, no traceback, exit 141) so ``lumina ... | head`` behaves
    like any other Unix tool. On platforms without SIGPIPE, a BrokenPipeError
    is swallowed and the stream abandoned so shutdown produces no noise.
    """
    _install_sigpipe_dfl()
    try:
        return _run(argv)
    except BrokenPipeError:
        # Fallback (e.g. Windows): abandon the broken stream quietly.
        import os
        try:
            sys.stdout.close()
        except Exception:  # noqa: BLE001,S110 - best-effort abandon
            pass
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        return 0


def _gallery_main(args) -> int:
    from .gallery import compose_gallery

    count = compose_gallery(args.palette, args.gallery,
                            cell_w=args.cell_w, cell_h=args.cell_h,
                            gamma=args.gamma)
    sys.stdout.write(f"[lumina] gallery: {count} effects -> {args.gallery}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
