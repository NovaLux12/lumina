import io
import struct

from lumina import engine


def test_capture_quiet_is_clean_redirect():
    out = engine.capture("plasma", "nova", 8, 4, t=0.0, quiet=True)
    assert "\u2580" in out
    assert "\x1b[2J" not in out
    assert "\x1b[?25l" not in out
    assert "\x1b[0m" in out  # RESET present


def test_capture_nonquiet_has_terminal_churn():
    out = engine.capture("plasma", "nova", 8, 4, t=0.0, quiet=False)
    assert "\x1b[2J" in out          # clear screen
    assert "\x1b[?25l" in out        # hide cursor
    assert "\x1b[?25h" in out        # show cursor
    assert "\x1b[0m" in out          # RESET


def test_capture_dimensions_match():
    out = engine.capture("aurora", "pine", 20, 6, t=1.0)
    assert len(out.split("\n")) == 6


def test_export_stills_bounded(tmp_path):
    engine.export_stills(str(tmp_path), "fire", "ember", fps=4.0, frames=3)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["fire-ember-000.txt", "fire-ember-001.txt", "fire-ember-002.txt"]
    for p in tmp_path.iterdir():
        assert "\u2580" in p.read_text(encoding="utf-8")


def test_export_png_stills_dims(tmp_path):
    engine.export_png_stills(str(tmp_path), "mandala", "retro", width=10, height=5,
                             frames=2, fps=4.0, scale=2)
    pngs = sorted(p for p in tmp_path.iterdir() if p.suffix == ".png")
    assert len(pngs) == 2
    for p in pngs:
        data = p.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h, depth, ctype, *_ = struct.unpack(">IIBBBBB", data[16:29])
        assert (w, h, depth, ctype) == (20, 20, 8, 2)


def test_non_tty_iterator_is_bounded(monkeypatch):
    """A single non-TTY run must exit after a handful of frames (finding #1)."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    sink = io.StringIO()
    monkeypatch.setattr("sys.stdout", sink)
    engine.animate_interactive("plasma", "nova", fps=5.0, frames=2)
    text = sink.getvalue()
    assert text.count("\x1b[0m\n") == 2  # each frame = <escape>RESET newline
    assert "\u2580" in text
