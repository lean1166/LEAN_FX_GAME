import pygame
from app.ui.screens.home_screen import HomeScreen


class Application:
    def __init__(self):
        # Configuración de la ventana principal
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("LEAN FX LIVE")

        # Pantalla inicial (HomeScreen)
        self.home_screen = HomeScreen(self.width, self.height)

    def update(self):
        """Lógica de actualización del juego (inputs, timers, etc)."""
        # Por ahora no hace nada, pero acá podés manejar eventos de juego
        pass

    def render(self):
        """Renderizado de la pantalla principal."""
        # Fondo gris oscuro
        self.screen.fill((30, 30, 30))

        # Dibujar la pantalla inicial
        self.home_screen.draw(self.screen)
