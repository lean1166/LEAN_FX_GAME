"""
Utilidad compartida para cargar avatares de viewers como circulitos con borde.
Usado por main.py (panel de votación) y window_ranking.py (TOP 5).

Cada proceso mantiene su propio cache en memoria (no se comparte entre
procesos), pero ambos leen del mismo folder en disco (shared_paths.AVATARS_DIR),
donde tiktok_chat.py descarga las fotos de los viewers en tiempo real.
"""
import os
import pygame
from shared_paths import AVATARS_DIR

_cache = {}  # {(username, size): pygame.Surface or None}


def get_viewer_avatar(username, size=24):
    """
    Cargar avatar de viewer recortado en círculo con borde cyan. Retorna Surface o None.

    IMPORTANTE: solo se cachea el resultado cuando SÍ se encuentra la imagen.
    Si todavía no existe el archivo (la descarga en background de
    tiktok_chat.py puede tardar unos milisegundos por la red), se devuelve
    None SIN cachear, para que el próximo frame vuelva a intentar leer el
    disco. Antes se cacheaba None de forma permanente apenas se pedía la
    imagen por primera vez (casi siempre antes de que terminara de
    descargarse), y esa foto ya no se volvía a cargar nunca más aunque el
    archivo apareciera después.
    """
    key = (username, size)
    if key in _cache:
        return _cache[key]
    for ext in [".png", ".jpg", ".jpeg"]:
        filepath = os.path.join(AVATARS_DIR, f"{username}{ext}")
        if os.path.exists(filepath):
            try:
                img = pygame.image.load(filepath).convert_alpha()
                img = pygame.transform.smoothscale(img, (size, size))
                circle_mask = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(circle_mask, (255, 255, 255), (size // 2, size // 2), size // 2)
                final = pygame.Surface((size, size), pygame.SRCALPHA)
                for x in range(size):
                    for y in range(size):
                        if circle_mask.get_at((x, y))[3] > 0:
                            final.set_at((x, y), img.get_at((x, y)))
                pygame.draw.circle(final, (0, 180, 220), (size // 2, size // 2), size // 2, 2)
                _cache[key] = final
                return final
            except Exception as e:
                print(f"[AVATAR] Error cargando {username}: {e}")
                return None
    return None
