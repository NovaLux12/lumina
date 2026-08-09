# lumina — Critical Review

**Reviewer:** independent subagent (round 2 / critical pass) · **Date:** 2026-08-09

## Round history

- **Round 1:** 73/100. Five findings (3 MAJOR, 2 MINOR) plus three NITs. See preamble below for the full list.

## Round 2 — background & verification performed (actual, not trusted)

All commands run in the project venv.

- `python3 -m pytest -q` → **40 passed** (fresh green; count rose 27 → 40) ✓
- `ruff check src tests` → **All checks passed!** ✓
- Zero-dependency: all imports confirmed stdlib (`argparse, math, os, select, shutil, struct, sys, termios, time, tty, zlib, typing, io, collections.abc, __future__`). `grep` over `src/lumina/*.py` returned only `from typing import Callable`. ✓
- Non-TTY bounded run: `python3 -m lumina --effect plasma < /dev/null | wc -c` → **98,619 bytes, exit 0**. Single bounded frame, no MB/s firehose. ✓
- `--still` redirect: piped output begins with truecolor RGB escapes (`38;2;`, `48;2;`, `▀`); **no `\x1b[2J` (erase screen) and no `\x1b[?25l`/`\x1b[?25h` (cursor) bytes**. ✓ Clean and scriptable.
- `--gallery`, `--png`, `--export` all render correct dimensions via the stdlib PNG writer (sig + IHDR verified). ✓

---

## Verification of round-1 findings

1. **MAJOR — Non-TTY fallback streamed forever (~2.2 MB/s).** ✅ **FIXED.** `animate_interactive` now branches on `sys.stdin.isatty() and sys.stdout.isatty()`; piped/CI renders a bounded one-shot — `--frames` (default 1) frames at `i/fps` then exits. Measured 98.6 KB / exit 0. The termios cbreak block is reached only on the TTY path, so the bounded branch touches no terminal state — clean exit.
2. **MAJOR — CLI/engine/gallery had zero tests.** ✅ **FIXED.** `tests/test_cli.py`, `tests/test_engine.py`, `tests/test_gallery.py` exist, run, and genuinely assert the claimed behaviours: unknown-effect/palette → exit `2`, alias resolution (`hyperspace`→starfield renders), `--still` clean-redirect, `capture(quiet=True/False)` churn gating, `export_stills`/`export_png_stills` exact file counts + dims, gallery count/width/height, non-TTY bounded frames (2 frames → 2 `RESET\n`).
3. **MAJOR — periodicity test was vacuous (`t+0.0`).** ✅ **FIXED.** Now asserts real periods with `pytest.approx`:
   - plasma `T=20π`: coeffs 1.3, 0.9, 1.7, 2.2 → `1.3·20π=26π=13·2π`, `0.9·20π=18π=9·2π`, `1.7·20π=34π=17·2π`, `2.2·20π=44π=22·2π` — all full rotations. Genuine common period.
   - fire `T=4π`: coeffs 4.0, 2.5 → `4·4π=16π=8·2π`, `2.5·4π=10π=5·2π`. Genuine.
   Both are mathematically real, non-tautological, and cover 3 + 2 sample points across the domain.
4. **MINOR — `--still` polluted stdout with screen-clear/cursor sequences.** ✅ **FIXED.** `--still` now calls `capture(..., quiet=True)` → `frame + RESET`, no `2J`/cursor bytes. Verified + test-gated.
5. **MINOR — README overclaimed coverage.** ✅ **MOSTLY FIXED.** README now states the honest 40-test count and describes real asserted behaviour. One residual overclaim remains (see finding B below).
6. **NIT — dead `cols` param.** ✅ **FIXED.** `compose_gallery` signature replaced it with `effect_order` and uses curated `list_effects()` order.
7. **NIT — gallery order diverged from curated order.** ✅ **FIXED.** Now `list_effects()`.
8. **NIT — `capture(quiet=True)` omitted trailing RESET.** ✅ **FIXED.** Returns `frame + RESET`.

---

## New findings (round 2)

### MINOR–MODERATE — A. SIGPIPE handling is **incomplete**: piping to a tool that closes early still exits 120 and spews a trace
`cli.main()` wraps `_run` in `try/except BrokenPipeError` and redirects fd 1 to `/dev/null`, documented as "pipes quietly … no noisy BrokenPipeError trace". **Reproducible 3/3**, the real-world `| head` case fails:

```
$ python3 -m lumina --effect plasma --still 0.5 | head -c 200 >/dev/null   # (2>/err captured)
py_exit=120   stderr: "Exception ignored while flushing sys.stdout: BrokenPipeError"
```

Root cause: `_run` writes the ~98 KB still into a **buffered** stdout. When the consumer closes the pipe (e.g. `head -c 200`), the `BrokenPipeError` surfaces during the **interpreter-shutdown flush of the TextIOWrapper** — *after* `main()` has returned — so the `try/except` and the fd-1 redirect never see it. Result: non-zero exit **120** (breaks `set -o pipefail` CI) and a noisy stderr line. This contradicts both the CLI docstring and the README's "SIGPIPE is swallowed" claim. The fix only covers the caught mid-write path. (Robust remedy: from the handler, also `sys.stdout = None`/close the wrapper, or set the handler to flush/abandon the stream so shutdown doesn't re-raise.)

### MINOR — B. The SIGPIPE test only covers the caught path, so it gives **false confidence**
`test_cli.py::test_broken_pipe_is_swallowed` monkeypatches `sys.stdout` with a stub whose `write()` raises `BrokenPipeError` — this exercises exactly the path `main()`'s `try/except` *does* handle, and asserts `== 0`. It does **not** reproduce the real shutdown-flush failure above, so the suite is green while the actual pipe-to-`head` scenario fails. The test should pipe a real frame through a real closed pipe (subprocess) or flush-after-close to cover the defect. Also the README's "SIGPIPE is swallowed" bullet should be toned down until it is.

### NIT — C. Non-TTY default mode prints the interactive banner before the bounded frame
Running `lumina --effect plasma < /dev/null | …` emits the `✨ lumina [plasma|nova] q to quit` banner line ahead of the single frame — a "q to quit" hint that is meaningless off a TTY and pollutes an otherwise clean redirected single frame. Bounded and harmless, but arguably the banner should be suppressed on the non-TTY one-shot path (users wanting pure output use `--still`, which is already clean).

### NIT — D. `--still` frames are fixed at 96×28 regardless of a small terminal
`_run`'s still branch hardcodes `DEFAULT_WIDTH/HEIGHT`; a terminal narrower than 96 cols (or `COLUMNS`) still gets a 96-wide frame. Defensible for reproducible scripting output, but worth a note that stills don't respect terminal size the way the live mode does.

### Round-1 praised items still hold
- Ruff clean ✓ · pytest green at **40** ✓ · stdlib-only ✓ · live `--gallery`/`--png`/`--export` verified ✓.

---

## Scores

| Dimension (weight) | Score | Justification |
|---|---|---|
| Architecture & design (20) | **18** | Pure-function effects, clean module split, curated order + aliases; dead `cols` removed, gallery now uses curated order. Minor: banner-before-frame on the non-TTY one-shot. |
| Correctness & robustness (20) | **15** | Core render, clamping, determinism, PNG writer all correct; the big non-TTY firehose and `--still` churn are fixed. Docked for the residual incomplete-SIGPIPE defect (exit 120 + stderr noise on `\| head`). |
| Test quality & coverage (15) | **12** | 40 tests now genuinely cover CLI/engine/gallery (round-1 gap closed) and periodicity is real (T=20π / 4π verified). Docked: SIGPIPE test covers only the caught path, missing the shutdown-flush failure; bounds/gamma still at few sample points. |
| Documentation & packaging (15) | **12** | README honest on count/behaviour now; install and pyproject solid. Docked: residual "SIGPIPE is swallowed" overclaim, which finding A disproves. |
| CLI ergonomics & UX (15) | **12** | Good flags, aliases, short forms, defaults; `--still` now clean and scriptable; non-TTY bounded. Docked: exit 120 + noise when piped to `head`, and the stray banner on the piped one-shot. |
| Creativity & polish (10) | **8** | Coherent, well-crafted, deterministic; real committed gallery asset, thoughtful palettes. Not a toy. |
| Maintainability (5) | **4** | Consistent naming, thorough docstrings, dead surface removed, single-responsibility modules. |
| **Total** | **81** | |

---

## Bottom line
Every one of round-1's material findings (the firehose, the missing CLI/engine/gallery tests, the vacuous periodicity test, the `--still` control churn, the README overclaim, the dead `cols`/order nits, the missing RESET) is genuinely fixed, verified, not just claimed. The suite grew 27 → 40 real assertions across every layer and the periodicity tests are mathematically sound. What keeps it from the high 80s is one honest residual defect: the SIGPIPE handling is incomplete end-to-end — pipeline the still to `head`/a pager and you still get exit 120 plus a `BrokenPipeError` trace, and the test that claims this is covered only exercises the path that already worked. Fix that one path (and re-tone the README bullet) and this is an 85+ project. As it stands it is a genuinely good, well-tested, dependency-free art tool.

SCORE: 81/100
