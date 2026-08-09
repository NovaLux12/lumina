# lumina — Critical Review

**Reviewer:** independent subagent (critical pass) · **Date:** 2026-08-09

## Verification performed (actual, not trusted)

- `python3 -m pytest -q` → **27 passed in 0.01s** ✓ (claim holds — real count, pass green)
- `ruff check src tests` → **All checks passed!** ✓
- `python3 -m lumina --list-effects` (6) / `--list-palettes` (6) / `--version` (`lumina 1.0.0`) ✓
- `python3 -m lumina --effect plasma --still 0.5 | head -3` → clean, exit 0, **no BrokenPipeError noise** ✓
- `--gallery` → 240×144 valid PNG (sig + IHDR verified); `docs/gallery.png` present, valid, 240×144 ✓
- `--png` export → valid 288×168 PNG frames using the stdlib writer ✓
- Editable install + `lumina` console script + `python3 -m lumina` all work as documented ✓
- Zero-dependency claim: all imports are stdlib (`argparse, math, os, select, shutil, struct, sys, termios, time, tty, zlib, typing, collections.abc`) ✓

The headline claims are **true**. The material findings below are about depth of testing and robustness, not about the core render pipeline.

---

## Findings (by severity)

### 1. MAJOR — The "temporal periodicity" test is vacuously true (false coverage claim)
`tests/test_effects.py::test_effects_are_temporal_periodic` asserts
`fn(x, y, t) == fn(x, y, t + 0.0)` — identical arguments, so it is **always True** by construction. It duplicates `test_effects_are_deterministic` and yields zero signal about temporal periodicity, yet the README and test count both advertise "periodicity" as a covered property ("27 tests cover … periodicity", docstrings claim effects are "periodic in t").
**Fix:** drop the `+0.0` tautology and test a real property — e.g. starfield/aurora/matrix use `_frac(t*speed)`, so assert `fn(x,y,t) == fn(x,y,t + 1/speed_lcm)` for a hand-picked period, or at minimum rename the test to what it actually checks (`determinism_revisit_same_t`) and stop claiming periodic coverage.

### 2. MAJOR — CLI, engine, and gallery are 100% untested
All 27 tests live in `test_ansi.py`, `test_effects.py`, `test_palettes.py`, `test_pngout.py`. **No test imports `cli.py`, `engine.py`, or `gallery.py` at all** (confirmed by grep). That leaves completely uncovered: the argparse CLI (unknown-effect exit codes, alias resolution on the CLI path, `--version`, exit-code contract), the interactive engine (termios/select, capture prefix/suffix, `export_stills`, `export_png_stills` dimensions, the non-TTY branch, the pause/fps key handling), and gallery composition (which is the flagship single-command portfolio feature with the committed asset).
**Fix:** add `tests/test_cli.py` (capsys + monkeypatched argv: unknown effect → rc 2, `--list-*`, `--still` shape, BrokenPipeError swallowed) and `tests/test_engine.py` (capture contains ANSI, `export_stills`/`export_png_stills` produce exactly `frames` files and correct dims, non-TTY fallback terminates).

### 3. MAJOR — Non-TTY fallback streams frames **forever** (runaway output)
With stdin not a TTY (e.g. `lumina --effect plasma < /dev/null`), `animate_interactive` enters the fallback `while True:` loop and prints unbounded frames at `--fps`. Measured: **~2.2 MB of output in 1 second** with no self-termination. This directly contradicts the code's own "non-TTY fallback must degrade gracefully" comment and means piping `lumina` into a file/pager/CI spawns a firehose only stoppable by SIGPIPE or Ctrl-C.
**Fix:** in the non-TTY branch, when neither stdin nor stdout is a TTY, render a single frame (or a bounded `--frames` count) and exit rather than looping. This is a genuine robustness defect, not cosmetic.

### 4. MINOR — `--still` pollutes the piped output with terminal-control sequences
`--still` calls `capture(..., quiet=False)`, which prepends `\x1b[2J` (full clear screen) and `\x1b[?25l`/`\x1b[?25h` (hide/show cursor) to the frame. The README markets `--still` as "great for scripting / docs", but redirecting it produces a screen-clear and cursor churn in the file/stream. Verified raw bytes begin `^[[2J^[[?25l…`.
**Fix:** use `quiet=True` for `--still` (reserve `quiet=False` for the live loop), or add a `--no-clear` escape hatch so stills are cleanly redirectable.

### 5. MINOR — README overstates the test contract
The README claims 27 tests cover "empty/single-anchor" palettes, "every effect's output bounds and determinism", "periodicity", and PNG "integrity". Reality: palette edge cases only exercise the `sample()` function with synthetic `[]`/single lists (the shipped registries are all ≥2 anchors, so nothing about the real library state is tested); every effect's bounds are checked at just **4 fixed (x,y,t) points**, not the domain; the "periodicity" claim is the vacuous test of finding #1. Balanced against this: PNG integrity IS genuinely tested (signature, IHDR fields, CRC, zlib decompress round-trip) — nice. Install instructions are accurate and reproduce exactly.
**Fix:** either add real tests matching the prose, or soften the README claims to what is actually covered.

### 6. NIT — `compose_gallery` accepts a `cols` parameter that is never used
`cols: int = 3` is declared and documented, but the gallery is always built as a single horizontally-tiled strip (6 effects → 240×144). The parameter is dead API surface and silently misleading. If kept, implement multi-row wrapping; otherwise remove it.

### 7. NIT — `compose_gallery` default order diverges from the curated order
The gallery fallback uses `EFFECTS.keys()` (dict insertion order) instead of `list_effects()` / `_EFFECT_ORDER`. They coincide today, but the code already defines curated ordering elsewhere and the gallery quietly bypasses it — a latent inconsistency if the registry is ever reordered.

### 8. NIT — `capture(quiet=True)` omits a trailing `RESET`
The default live-loop/non-TTY path leaves the terminal in the last rendered fg/bg colour when streaming stops mid-frame. Cosmetic only, but easy to fix by always appending `RESET` unless quiet-rendering is explicitly intended.

---

## Scores

| Dimension (weight) | Score | Justification |
|---|---|---|
| Architecture & design (20) | **17** | Pure-function effects, clean registry, clean ansi/palettes/effects/engine/pngout/gallery separation, curated order + aliases. Docked: dead `cols` param, gallery order bypasses curation. |
| Correctness & robustness (20) | **14** | Strong core: clamping, empty/single anchors, PNG integrity, zero-dep holds, SIGPIPE handled in `main`. Docked heavily for the unlimited non-TTY output loop and the `--still` control-churn. |
| Test quality & coverage (15) | **8** | 27 real assertions for ansi/palettes/pngout/effects; PNG tests are genuinely good. But the periodicity test is a tautology, and CLI/engine/gallery are entirely untested; bounds only at 4 points, gamma untested. |
| Documentation & packaging (15) | **11** | Features, commands and gallery asset verified accurate; install reproduces exactly; pyproject fields are solid. Docked for overclaiming test coverage and "great for scripting" contradicting `--still` noise. |
| CLI ergonomics & UX (15) | **11** | Good flags, aliases, short forms, defaults, help. Docked: `--still` output not cleanly redirectable, non-TTY never bounds itself. |
| Creativity & polish (10) | **8** | Coherent, well-crafted thing — deterministic art, thoughtful palettes, polished docs, real committed gallery asset. Not a toy. |
| Maintainability (5) | **4** | Consistent naming and thorough docstrings throughout; only minor dead/chaff surface (`cols`, gallery order). |
| **Total** | **73** | |

---

## Bottom line
lumina is a genuinely well-built zero-dependency art engine: the render pipeline, palette sampler, stdlib PNG writer and packaging are all correct and the 27 tests that exist are real. The honest weaknesses are **(a)** a falsely-labelled periodicity test, **(b)** zero tests for the CLI/engine/gallery — the very features that make it a "product" rather than a library — and **(c)** an unbounded non-TTY streaming loop. These are all fixable without touching the render core, which is the strongest part of the project.

SCORE: 73/100
