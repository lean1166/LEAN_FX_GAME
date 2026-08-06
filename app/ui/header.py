"""Header UI component for high-contrast application title."""

import pygame


class HeaderView:
    """Renders a sharp, high-contrast, professional title."""

    def __init__(self, width: int) -> None:
        self._width = width
        pygame.font.init()
        
        # Usamos Arial Black o Impact para que las letras sean gruesas,
        # firmes y resalten con muchísima fuerza en resoluciones altas.
        self._title_font = pygame.font.SysFont("Arial Black", 36)

    def draw(self, target: pygame.Surface) -> None:
        text_str = "LEAN FX LIVE"
        
        # 1. Crear la SOMBRA NEGRA (para dar profundidad y despegarlo del fondo)
        shadow_surface = self._title_font.render(text_str, True, (10, 10, 15))
        shadow_width = shadow_surface.get_width()
        x_shadow = (self._width - shadow_width) // 2
        
        # Dibujamos la sombra desplazada 3 píxeles hacia abajo y la derecha
        target.blit(shadow_surface, (x_shadow + 3, 33))

        # 2. Crear el TEXTO PRINCIPAL (Blanco puro brillante)
        core_surface = self._title_font.render(text_str, True, (255, 255, 255))
        core_width = core_surface.get_width()
        x_core = (self._width - core_width) // 2
        
        # Dibujamos el texto principal arriba de todo
        target.blit(core_surface, (x_core, 30))
