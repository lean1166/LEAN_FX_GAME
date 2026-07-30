"""
LEAN FX GAME - Ventana del PANEL STREAMER (V2, arquitectura multi-ventana)

Proceso pygame independiente. Se puede capturar como "Captura de ventana"
en OBS por separado del gráfico principal (main.py) y del ranking
(window_ranking.py).

No maneja audio (main.py es el único dueño del mixer) ni la conexión a
TikTok. Solo lee la base de datos (database.py) periódicamente y dibuja.

El tamaño de la ventana (480x240) coincide 1:1 con el tamaño que tenía el
panel del streamer dentro del gráfico en V1, cuando la pantalla completa
era 1920x1080 (sp_w = 1920*0.25 = 480, sp_h = 480*887/1774 ≈ 240). Por eso
las posiciones internas calibradas por el usuario (avatar, nombre, cajitas
de stats) se reusan tal cual, como fracciones de este mismo tamaño de
ventana. Si el usuario quiere verlo más grande en OBS, simplemente escala
la fuente de captura de ventana desde OBS - no hace falta tocar este código.
"""
import os
import sys
import pygame

from shared_paths import find_asset, find_profile_image
from database import get_streamer_stats, get_recent_results

WINDOW_W = 480
WINDOW_H = 240
REFRESH_INTERVAL_MS = 1000  # Cada cuánto se vuelve a consultar la DB

STREAMER_NAME = "LEAN FX"

# --- Posicionar la ventana (arriba a la derecha del escritorio) ---
pygame.init()
_info = pygame.display.Info()
_desktop_w, _desktop_h = _info.current_w, _info.current_h
_pos_x = max(0, _desktop_w - WINDOW_W - 20)
_pos_y = 20
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{_pos_x},{_pos_y}"

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.NOFRAME)
pygame.display.set_caption("LEAN FX - PANEL STREAMER")

icon_path = find_asset("icon.png", "icon.ico")
if icon_path:
    try:
        pygame.display.set_icon(pygame.image.load(icon_path))
    except Exception:
        pass

pygame.font.init()
font_name = pygame.font.SysFont("Arial", 18, bold=True)
font_stat = pygame.font.SysFont("Arial", max(8, int(WINDOW_H * 0.08)), bold=True)
font_fallback_label = pygame.font.SysFont("Arial", 12, bold=True)
font_fallback_val = pygame.font.SysFont("Arial", 20, bold=True)

# --- Cargar assets ---
panel_path = find_asset("panel_streamer.png")
panel_img = None
if panel_path:
    panel_img = pygame.image.load(panel_path).convert_alpha()
    panel_img = pygame.transform.smoothscale(panel_img, (WINDOW_W, WINDOW_H))

avatar_img = None
_profile_path = find_profile_image()
if _profile_path:
    avatar_img = pygame.image.load(_profile_path).convert_alpha()

# Posiciones calibradas en V1 (idénticas, expresadas como fracción de este panel)
AV_CX_FRAC, AV_CY_FRAC = 0.1396, 0.4250
AV_SIZE_FRAC = 0.35  # relativo a WINDOW_H
NAME_X_FRAC, NAME_Y_FRAC = 0.5917, 0.2917
STATS_X_FRACS = [0.3521, 0.5229, 0.6896, 0.8625]
STATS_Y_FRAC = 0.5708
STATS_COLORS = [(0, 220, 255), (38, 166, 154), (255, 180, 0), (200, 200, 200)]


def compute_streak(results):
    """results: lista de 'WIN'/'LOSS', más reciente primero."""
    streak = 0
    for r in results:
        if r == "WIN":
            streak += 1
        else:
            break
    return streak


clock = pygame.time.Clock()
last_refresh = -REFRESH_INTERVAL_MS
stats = {"balance": 10000, "wins": 0, "losses": 0}
streak = 0

running = True
while running:
    clock.tick(30)  # Ventana estática, no necesita 60fps
    current_time = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    if current_time - last_refresh >= REFRESH_INTERVAL_MS:
        try:
            stats = get_streamer_stats()
            streak = compute_streak(get_recent_results(STREAMER_NAME, limit=20))
        except Exception as e:
            print(f"[window_streamer] Error leyendo DB: {e}")
        last_refresh = current_time

    total_trades = stats["wins"] + stats["losses"]
    win_rate = (stats["wins"] / total_trades * 100) if total_trades > 0 else 0

    screen.fill((10, 12, 20))

    if panel_img is not None:
        screen.blit(panel_img, (0, 0))

        if avatar_img is not None:
            av_size = int(WINDOW_H * AV_SIZE_FRAC)
            av_scaled = pygame.transform.smoothscale(avatar_img, (av_size, av_size))
            av_cx = int(WINDOW_W * AV_CX_FRAC)
            av_cy = int(WINDOW_H * AV_CY_FRAC)
            screen.blit(av_scaled, (av_cx - av_size // 2, av_cy - av_size // 2))

        name_txt = font_name.render(STREAMER_NAME, True, (0, 220, 255))
        name_rect = name_txt.get_rect(center=(int(WINDOW_W * NAME_X_FRAC), int(WINDOW_H * NAME_Y_FRAC)))
        screen.blit(name_txt, name_rect)

        stats_values = [f"{int(stats['balance'])}", f"{win_rate:.0f}%", f"{streak}", f"{total_trades}"]
        for i, val in enumerate(stats_values):
            sx = int(WINDOW_W * STATS_X_FRACS[i])
            sy = int(WINDOW_H * STATS_Y_FRAC)
            s_txt = font_stat.render(val, True, STATS_COLORS[i])
            screen.blit(s_txt, s_txt.get_rect(center=(sx, sy)))
    else:
        # Fallback sin imagen: panel simple para poder probar/depurar igual
        pygame.draw.rect(screen, (0, 120, 150), (0, 0, WINDOW_W, WINDOW_H), 2)
        if avatar_img is not None:
            av_size = int(WINDOW_H * 0.5)
            av_scaled = pygame.transform.smoothscale(avatar_img, (av_size, av_size))
            screen.blit(av_scaled, (15, (WINDOW_H - av_size) // 2))
            text_x = 15 + av_size + 15
        else:
            text_x = 20
        name_txt = font_fallback_val.render(STREAMER_NAME, True, (0, 220, 255))
        screen.blit(name_txt, (text_x, 15))
        labels = ["BALANCE", "WIN RATE", "RACHA", "TRADES"]
        values = [f"{int(stats['balance'])} FXP", f"{win_rate:.0f}%", str(streak), str(total_trades)]
        for i, (lbl, val) in enumerate(zip(labels, values)):
            ly = 55 + i * 40
            lbl_txt = font_fallback_label.render(lbl, True, (120, 140, 160))
            val_txt = font_fallback_val.render(val, True, STATS_COLORS[i])
            screen.blit(lbl_txt, (text_x, ly))
            screen.blit(val_txt, (text_x, ly + 16))
        avviso = font_fallback_label.render("(panel_streamer.png no encontrado)", True, (100, 60, 60))
        screen.blit(avviso, (10, WINDOW_H - 18))

    pygame.display.flip()

pygame.quit()
sys.exit(0)
