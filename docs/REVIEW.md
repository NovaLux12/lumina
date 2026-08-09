# lumina — Critical Review (Round 3 / FINAL RELEASE GATE)

**Reviewer:** independent subagent (round 3, final gate) · **Date:** 2026-08-09
**Gate rule:** operator publishes only at **SCORE >= 90/100**.

## Round history

| Round | Score | Key outcome |
|-------|-------|-------------|
| Round 1 | **73/100** | 3 MAJOR (firehose loop, untested CLI/engine/gallery, vacuous periodicity test) + 2 MINOR + 3 NIT |
| Round 2 | **81/100** | All round-1 items fixed. Left open: incomplete SIGPIPE (exit 120 + trace on `| head`), false-confidence SIGPIPE mock test, banner on piped one-shot, fixed `--still` dimensions, README overclaim |
| **Round 3** | **90/100** | All four round-2 findings verified genuinely fixed & remediated safely. No material defect remains. Passes release gate. |

## Verification performed (actual, not trusted — every command run)

- **SIGPIPE real-world case (finding A):** `bash -o pipefail -c 'python3 -m lumina --effect plasma --still 0.5 2>/tmp/e | head -c 200 >/dev/null; echo rc=$?'` → **rc=141**, stderr **empty** (no `Traceback`, no `BrokenPipeError`). Round-2 behaviour (exit 120 + `Exception ignored while flushing sys.stdout`) is gone. Conventional Unix-tool SIGPIPE death confirmed.
- **Named reproduction test (finding B):** read `tests/test_cli.py::test_pipe_to_closed_reader_is_silent` — it spawns the real CLI via `subprocess.Popen([sys.executable, "-m", "lumina", "--effect", "plasma", "--still", "0.5"])` into an `os.pipe()` whose read end is closed immediately, asserts no `Traceback`/`BrokenPipeError` in stderr and `rc in (0, -13, 141)`. Genuine reproduction, not a stub. Ran 3/3 green in isolation and inside the full suite. Robust: on an un-bootstrapped env it **fails loudly** (rc 1/2 not in the allowed set) rather than false-passing.
- **Banner suppression (finding C):** `python3 -m lumina --effect plasma < /dev/null | head -c 20 | od -c` → begins with `\x1b[38;2;255;122;144m` (truecolor RGB), **no `✨ lumina q to quit` banner**. Piped default one-shot is clean.
- **`--still` terminal awareness (finding D):** piped → deterministic 96×28 defaults (80910-char frame, byte-stable). Via a real PTY sized 60×20 → first-line visual width ~~61~~ **60** (the extra byte was the PTY's `\r` line-end, not an off-by-one bug); explicit `--width`/`--height` still win. Verified with `fcntl`/`TIOCSWINSZ`, not guessed.
- **Ruff:** `ruff check src tests` → **All checks passed!** (`rc 0`, clean).
- **pytest stability:** 3 consecutive full runs → **41 passed** each, no flakes.
- **stdlib-only:** AST walk of all `src/lumina/*.py` → top-level imports are only `shutil, sys, time, os, select, termios, tty, argparse, signal, struct, zlib, math, typing, collections.abc, __future__` (the latter is a pseudo-module). **No third-party imports anywhere.**
- **Entry points:** both `lumina --version` (console script → `lumina 1.0.0`) and `python3 -m lumina` render. `--still`, `--list-effects` (6), `--list-palettes` (6), `--version` all work from outside the repo dir.
- **Render paths:** `--export` writes exactly the requested `fire-ember-NNN.txt` frames; `--png` writes valid PNGs (`file`: 8-bit RGB, correct 192×112 dims for width96/scale2); `--gallery` produces a valid 240×144 PNG tiling all 6 effects. No banner leaks on `--png`/`--export`/`--gallery`.
- **Bounded default one-shot:** `python3 -m lumina --effect plasma < /dev/null` emits exactly **1** RESET-terminated frame and exits (no firehose). Round-1 MAJOR re-confirmed fixed.

## Round-2 findings — final status

### A. Incomplete SIGPIPE (exit 120 + trace on `| head`) — ✅ **Genuinely FIXED**
`cli.main()` now calls `_install_sigpipe_dfl()` (`signal.SIGPIPE = SIG_DFL`) before dispatch, so a closed output pipe kills the process conventionally (rc 141, silent, no shutdown-flush re-raise). A `BrokenPipeError` try/except + fd-1→`/dev/null` redirect remains as the non-POSIX fallback. Verified against the exact round-2 reproduction command. The old failure mode is unreachable.

### B. False-confidence mock SIGPIPE test — ✅ **Genuinely FIXED**
The monkeypatch stub was replaced by a real subprocess closed-pipe reproduction (see above). It exercises the actual defect path, is deterministic (dies by full-buffer + no-reader SIGPIPE), and is stable across repeated runs.

### C. Banner printed off a TTY — ✅ **Genuinely FIXED**
The `✨ lumina … q to quit` line is now inside `if sys.stdout.isatty():`. Piped/non-TTY output (default one-shot and `--still`) begins directly with ANSI RGB, byte-verified.

### D. `--still` ignored terminal size — ✅ **Genuinely FIXED**
`_terminal_dimensions` uses live TTY cols / (`lines − 2`) when stdout is a TTY, deterministic 96×28 defaults when piped, and honours explicit `--width`/`--height`. Verified with a real PTY (60-col terminal → 60-wide still).

## Round-1 re-verification (regression check after the fixes)

- Non-TTY firehose: still bounded (1 frame) ✅
- CLI/engine/gallery tests present and asserting real behaviour ✅
- Real periodicity tests (plasma `T=20π`, fire `T=4π`) — mathematically sound, still green ✅
- `--still` clean redirect (no `2J` / cursor churn / trailing RESET present) ✅
- Gallery curated order, dead `cols` removed, `capture(quiet=True)` returns `frame + RESET` ✅
- PNG writer integrity (sig / IHDR / CRC / zlib round-trip) still green ✅

No regression introduced by the round-3 patch: it touches only `cli.py`, `test_cli.py`, `README.md`, `REVIEW.md`.

## Remaining issues (honest, by severity)

- **MINOR — README test count drift.** README states "40 unit tests" / "# 40 tests" / "The suite (40 tests)" in three spots; the actual suite is **41** (5 ansi + 8 cli + 11 effects + 6 engine + 2 gallery + 7 palettes + 2 pngout). The README *under*-promises (safe direction) but the stated number is factually wrong. One-line fix; not blocking.
- **NIT — SIGPIPE test couples to the installed package.** It launches `python3 -m lumina`, which requires the editable install to be active. Correctly, it fails loudly (not false-passes) in an unbootstrapped env — acceptable, but a `sys.path`/cwd guard or packaging the venv assumption into the test would harden it.
- **NIT — `--still` height heuristic.** Uses `lines − 2` off a TTY even though stills draw no status bar; purely cosmetic, defensible, not a defect.
- **NIT — `--still` unbuffered/no explicit pre-exit flush.** With SIG_DFL the OS handles the closed-pipe case; the code relies on the standard buffering + SIG_DFL interplay (verified correct). No action needed.

No MAJOR or MODERATE issues remain. Every material finding from all three rounds is fixed, verified by execution, and re-tested for stability.

## Scorecard (weighted rubric)

| Dimension (weight) | Score | Justification |
|---|---|---|
| Architecture & design (20) | **18** | Clean module separation (ansi/palettes/effects/engine/pngout/gallery/cli), pure-function effects, curated order + aliases, dead surface removed. |
| Correctness & robustness (20) | **19** | All prior robustness defects fixed and independently verified: conventional SIGPIPE (rc 141, silent), bounded non-TTY, clean redirectable stills, TTY-aware dimensions. Core render, clamping, determinism, PNG writer all correct. No material defect. |
| Test quality & coverage (15) | **14** | 41 real assertions across every layer incl. a genuine subprocess closed-pipe SIGPIPE reproduction and mathematically sound periodicity (20π / 4π). Flag: SIGPIPE test is env-coupled (fail-loud, not false-pass); bounds/gamma still at a few points. |
| Documentation & packaging (15) | **13** | README accurate on commands/behaviour/install (reproduced); pyproject and dependencies solid. Docked for the 40-vs-41 test count drift. |
| CLI ergonomics & UX (15) | **14** | Good flags, aliases, short forms, help, defaults; clean still output, bounded non-TTY one-shot, live terminal-size awareness. Minor cosmetic nits only. |
| Creativity & polish (10) | **8** | Coherent, deterministic, thoughtful palettes, real committed gallery asset; modest scope. Not a toy. |
| Maintainability (5) | **4** | Consistent naming, thorough docstrings, single-responsibility modules, no dead/chaff surface. |
| **Total** | **90** | |

## Bottom line

This is the release gate, and it passes. Across three rounds the suite grew from genuinely broken in places (firehose loop, zero CLI/engine/gallery coverage, vacuous periodicity test, exit-120 SIGPIPE traceback) to a state where **not one material defect survives**, and every fix was verified by executing the exact failing scenario rather than trusted from the commit message. Ruff is clean, all 41 tests are stable across repeated runs, it is stdlib-only, both install entry points and every render path (`--gallery`/`--png`/`--export`/`--still`) work as documented, the README no longer overclaims, and the SIGPIPE behaviour now genuinely matches what the docs say. The only residue is a single off-by-one in README's stated test count plus cosmetic nits — none of which block a 90+ release.

**Verdict: this clears the 90/100 release bar.** Publish.

---
Assertion / provenance: all claims verified by commands run on this reviewer's own account (pty provided fresh subprocesses; counts read from pytest collection, not trusted logs).
