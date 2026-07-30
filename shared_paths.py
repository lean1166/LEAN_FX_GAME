"""
Rutas compartidas entre todos los procesos de LEAN FX GAME
(main.py, window_streamer.py, window_ranking.py, tiktok_chat.py, launcher.py)

Antes de la arquitectura multi-ventana, cada archivo calculaba BASE_DIR/AVATARS_DIR
por su cuenta. tiktok_chat.py incluso lo hacía mal: no contemplaba el caso de
ejecutable empaquetado (PyInstaller / sys.frozen), a diferencia de main.py.
Este módulo es la única fuente de verdad para que los 3 procesos coincidan
siempre en las mismas carpetas, sin importar cómo se ejecute el juego.
"""
import sys
import os

# Detectar si estamos corriendo desde un ejecutable empaquetado (PyInstaller)
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SOUND_DIR = os.path.join(ASSETS_DIR, "sound")
PROFILE_DIR = os.path.join(ASSETS_DIR, "profile")  # Foto del streamer (LEAN FX)
AVATARS_DIR = os.path.join(ASSETS_DIR, "avatars")  # Avatares descargados de viewers TikTok

# Asegurar que existan las carpetas que se escriben en tiempo de ejecución
os.makedirs(AVATARS_DIR, exist_ok=True)


def find_asset(*candidates):
    """
    Devuelve la ruta completa al primer archivo que exista dentro de assets/,
    probando cada nombre candidato en orden (útil para 'panel_top5.png' vs
    'panel_top5.jpg', o 'icon.png' vs 'icon.ico').
    Devuelve None si ninguno existe.
    """
    for name in candidates:
        path = os.path.join(ASSETS_DIR, name)
        if os.path.exists(path):
            return path
    return None


def find_profile_image():
    """Busca la primera imagen dentro de assets/profile/ (foto del streamer)."""
    if not os.path.exists(PROFILE_DIR):
        return None
    for f in sorted(os.listdir(PROFILE_DIR)):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(PROFILE_DIR, f)
    return None
