import pytest

from lumina import cli
from lumina.effects import list_effects
from lumina.palettes import list_palettes


def test_list_effects(capsys):
    assert cli.main(["--list-effects"]) == 0
    out = capsys.readouterr().out.split()
    assert out == list_effects()


def test_list_palettes(capsys):
    assert cli.main(["--list-palettes"]) == 0
    out = capsys.readouterr().out.split()
    assert out == list_palettes()


def test_version():
    # --version is an argparse built-in; it exits(0) rather than returning.
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


def test_unknown_effect_exits_2(capsys):
    assert cli.main(["--effect", "bogus", "--still", "0"]) == 2
    err = capsys.readouterr().err
    assert "unknown effect" in err


def test_unknown_palette_exits_2(capsys):
    assert cli.main(["--effect", "plasma", "--palette", "nope", "--still", "0"]) == 2


def test_alias_resolution_on_cli(capsys):
    # 'hyperspace' is an alias for 'starfield' — must render, not error.
    assert cli.main(["--effect", "hyperspace", "--still", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "\u2580" in out


def test_still_output_is_clean_redirect(capsys):
    """--still must not emit screen-clear or cursor churn (finding #4)."""
    assert cli.main(["--effect", "plasma", "--still", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "\x1b[2J" not in out          # no full clear
    assert "\x1b[?25l" not in out        # no hide-cursor
    assert "\x1b[?25h" not in out        # no show-cursor
    assert "\x1b[0m" in out              # ends cleanly with RESET


def test_broken_pipe_is_swallowed(monkeypatch):
    """main() must return 0 when a downstream pipe closes (finding SIGPIPE)."""
    import os

    class Growly:
        def write(self, _s):
            raise BrokenPipeError()
        def flush(self):
            pass

    # main() does `import os` (same module) then dup2s to /dev/null; patch the
    # global os so the handler can't hijack the real fd 1 during the test.
    monkeypatch.setattr(os, "dup2", lambda *a, **k: None)
    monkeypatch.setattr(os, "open", lambda *a, **k: 999)
    monkeypatch.setattr("sys.stdout", Growly())
    assert cli.main(["--effect", "plasma", "--still", "0.5"]) == 0
