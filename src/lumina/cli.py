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
    export_png_stills,
)
from .palettes import PALETTES, list_palettes


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lumina",
        description="Zero-dependency terminal generative art. Animated ANSI light shows.",
        epilog=(
            "effects: " + ", ".join(list_effects())
            + "  |  palettes: " + ", ".join(list_palettes())
        ),
    )
    p.add_argument("-e", "--effect", default=DEFAULT_EFFECT,
                   help=f"effect to render (default: {DEFAULT_EFFECT}); supports aliases like 'hyperspace'")
    p.add_argument("-c", "--palette", default=DEFAULT_PALETTE,
                   help=f"colour palette (default: {DEFAULT_PALETTE})")
    p.add_argument("--width", type=int, default=0, help="character-column width (0 = auto/terminal)")
    p.add_argument("--height", type=int, default=0, help="character-row height (0 = auto/terminal)")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS, help="frames per second (default: %(default)s)")
    p.add_argument("--gamma", type=float, default=1.0, help="brightness gamma curve")
    p.add_argument("--still", type=float, metavar="T", default=None,
                   help="render a single frame at time T and print it, then exit")
    p.add_argument("--export", metavar="DIR", default="",
                   help="export temporally-spaced ANSI frames to DIR and exit")
    p.add_argument("--png", metavar="DIR", default="",
                   help="render real PNG frames (stdlib-only encoder) to DIR and exit")
    p.add_argument("--scale", type=int, default=2, help="PNG upscale factor per cell (default: 2)")
    p.add_argument("--gallery", metavar="PNG", default="",
                   help="tile all effects into one portfolio PNG and exit")
    p.add_argument("--cell-w", type=int, default=40, help="gallery cell width (default: 40)")
    p.add_argument("--cell-h", type=int, default=12, help="gallery cell height (default: 12)")
    p.add_argument("--frames", type=int, default=None, help="number of frames to export")
    p.add_argument("--list-effects", action="store_true", help="print effect names")
    p.add_argument("--list-palettes", action="store_true", help="print palette names")
    p.add_argument("--version", action="version", version=f"lumina {__version__}")
    return p


def _run(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list_effects:
        print("\n".join(list_effects()))
        return 0
    if args.list_palettes:
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
        w = args.width or DEFAULT_WIDTH
        h = args.height or DEFAULT_HEIGHT
        sys.stdout.write(capture(eff, args.palette, w, h, args.still, args.gamma, quiet=False))
        sys.stdout.write("\n")
        return 0

    w = args.width or 0
    h = args.height or 0
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

    sys.stdout.write(f"\n\x1b[38;2;120;200;255m✨ lumina\x1b[0m "
                     f"[{eff} | {args.palette}]  q to quit\n")
    animate_interactive(eff, args.palette, args.fps, args.gamma)
    return 0


def main(argv=None) -> int:
    """Entry point: runs _run, swallowing SIGPIPE so piping to tools like
    ``head`` doesn't dump a noisy BrokenPipeError trace."""
    try:
        return _run(argv)
    except BrokenPipeError:
        # Downstream closed the pipe; exit quietly with success.
        import os
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
