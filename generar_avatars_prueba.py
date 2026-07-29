"""
Genera avatares de prueba (circulitos de colores) para testear sin TikTok Live
Ejecutar UNA VEZ: python generar_avatars_prueba.py
"""
import os
import pygame

pygame.init()

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "avatars")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Nombres de prueba con colores
test_avatars = [
    ("crypto_wolf", (255, 100, 50)),
    ("bull_master", (50, 200, 100)),
    ("sniper_pro", (100, 50, 255)),
    ("gold_trader", (255, 200, 0)),
    ("fx_queen", (255, 50, 150)),
    ("trader_mike", (50, 150, 255)),
    ("pip_hunter", (200, 100, 255)),
    ("chart_ninja", (0, 200, 200)),
    ("forex_ace", (255, 150, 0)),
    ("scalp_king", (150, 255, 50)),
]

SIZE = 100  # 100x100 px

for name, color in test_avatars:
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    # Circulo de color
    pygame.draw.circle(surface, color, (SIZE // 2, SIZE // 2), SIZE // 2)
    # Inicial del nombre en el centro
    font = pygame.font.SysFont("Arial", 40, bold=True)
    letter = font.render(name[0].upper(), True, (255, 255, 255))
    rect = letter.get_rect(center=(SIZE // 2, SIZE // 2))
    surface.blit(letter, rect)
    # Guardar
    filepath = os.path.join(OUTPUT_DIR, f"{name}.png")
    pygame.image.save(surface, filepath)
    print(f"  ✓ {filepath}")

print(f"\n¡Listo! {len(test_avatars)} avatares de prueba generados en assets/avatars/")
pygame.quit()
