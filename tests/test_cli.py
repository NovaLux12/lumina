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


def test_pipe_to_closed_reader_is_silent(tmp_path):
    """Real closed-pipe reproduction (finding A): pipe a ~98KB still into a
    consumer that closes early. The interpreter-shutdown flush previously
    surfaced a BrokenPipeError traceback (exit 120); it must now die silently
    with no traceback — either via conventional SIGPIPE (-13/141) or the
    BrokenPipeError fallback (0)."""
    import os
    import subprocess
    import sys

    errf = tmp_path / "stderr.txt"
    with errf.open("w") as perr:
        r, w = os.pipe()
        proc = subprocess.Popen(
            [sys.executable, "-m", "lumina", "--effect", "plasma", "--still", "0.5"],
            stdout=w,
            stderr=perr,
        )
        os.close(w)
        os.close(r)  # close the reader immediately -> writer hits closed pipe
        rc = proc.wait(timeout=15)
    err = errf.read_text()
    assert "Traceback" not in err
    assert "BrokenPipeError" not in err
    assert rc in (0, -13, 141)  # clean fallback, or conventional SIGPIPE
