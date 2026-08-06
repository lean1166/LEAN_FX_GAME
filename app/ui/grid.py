"""TradingView-style background grid."""

import pygame

from app.ui import theme


class GridView:
    """Pre-rendered subtle grid overlay."""

    def __init__(self, width: int, height: int) -> None:
        self._surface = pygame.Surface((width, height))
        self._surface.fill(theme.BACKGROUND)
        self._draw_grid(width, height)

    def _draw_grid(self, width: int, height: int) -> None:
        cell = theme.GRID_CELL_SIZE

        for x in range(0, width + 1, cell):
            pygame.draw.line(self._surface, theme.GRID_LINE, (x, 0), (x, height), 1)

        for y in range(0, height + 1, cell):
            pygame.draw.line(self._surface, theme.GRID_LINE, (0, y), (width, y), 1)

    def draw(self, target: pygame.Surface) -> None:
        target.blit(self._surface, (0, 0))
