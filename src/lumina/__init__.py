"""lumina — terminal generative art, zero dependencies."""

from .effects import EFFECTS, list_effects, render_frame
from .palettes import PALETTES, list_palettes

__version__ = "1.0.0"

__all__ = ["EFFECTS", "PALETTES", "__version__", "list_effects", "list_palettes", "render_frame"]
