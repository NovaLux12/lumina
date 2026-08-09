import pytest

from lumina.ansi import BLOCK_HALF, RESET, bg_rgb, fg_rgb


@pytest.mark.parametrize(
    "r,g,b,expected",
    [
        (0, 0, 0, "\x1b[38;2;0;0;0m"),
        (255, 128, 0, "\x1b[38;2;255;128;0m"),
        (1000, -5, 50, "\x1b[38;2;255;0;50m"),  # clamped
    ],
)
def test_fg_rgb(r, g, b, expected):
    assert fg_rgb(r, g, b) == expected


def test_bg_rgb_prefix():
    assert bg_rgb(1, 2, 3).startswith("\x1b[48;2;")


def test_block_and_reset_constants():
    assert BLOCK_HALF == "\u2580"
    assert RESET == "\x1b[0m"
