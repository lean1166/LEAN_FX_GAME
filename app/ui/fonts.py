"""Font loading utilities."""

import pygame

_FONT_FAMILIES = ("segoeui", "Segoe UI", "arial", "helvetica", "sans-serif")


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load a clean sans-serif font with sensible fallbacks."""
    return pygame.font.SysFont(_FONT_FAMILIES, size, bold=bold)
